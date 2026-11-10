"""
FJCWO 正式站備份工具（Windows 主機用，見 _notes/DEPLOY-WINDOWS.md 第 6 步）
=======================================================================

用正式站 venv 的 Python 執行（需要 venv 裡的 cryptography、python-dotenv）：

    venv\\Scripts\\python.exe scripts\\backup.py backup  --dest D:\\FJCWO-Backup
    venv\\Scripts\\python.exe scripts\\backup.py offsite --src D:\\FJCWO-Backup --dest "G:\\我的雲端硬碟\\FJCWO-Backup"
    venv\\Scripts\\python.exe scripts\\backup.py verify  D:\\FJCWO-Backup\\fjcwo_20261110_031500.fjbk
    venv\\Scripts\\python.exe scripts\\backup.py decrypt D:\\FJCWO-Backup\\fjcwo_20261110_031500.fjbk C:\\restore

backup   pg_dump（custom 格式）＋ media/ 打包成 zip，用 .env 的 BACKUP_ENCRYPTION_KEY 以 AES-256-GCM
         加密成一個 .fjbk 檔，刪掉超過保留天數的舊檔。失敗時 exit code 非 0，並嘗試寄信通知。
offsite  把 .fjbk 鏡像到雲端同步資料夾（Google Drive 電腦版的 G:）。只動 .fjbk，來源沒有的就刪掉，
         所以雲端的保留天數跟本地一致。G: 只在使用者登入時存在，要用「該使用者、登入時才執行」的排程。
verify   解密並用 pg_restore --list 檢查資料庫備份可讀、列出內容摘要（不碰任何資料庫）。
decrypt  解密並解壓到指定資料夾（還原用：裡面有 db.dump、media/、manifest.json）。

機密一律從 .env 讀（DB_PASSWORD 以環境變數交給 pg_dump，不出現在指令列）。
**遺失 BACKUP_ENCRYPTION_KEY ＝ 所有備份都解不開**：它跟 .env 一起存進密碼管理器，不要和備份放在一起。
"""

import argparse
import base64
import datetime as dt
import glob
import io
import json
import os
import shutil
import smtplib
import subprocess
import sys
import tempfile
import zipfile
from email.message import EmailMessage
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import dotenv_values

MAGIC = b'FJCWOBK1'      # 檔頭：格式版本，之後改格式就換這個
NONCE_LEN = 12
EXT = '.fjbk'
PREFIX = 'fjcwo_'


def load_env(base: Path) -> dict:
    env_path = base / '.env'
    if not env_path.exists():
        sys.exit(f'找不到 {env_path}')
    return dotenv_values(env_path)


def get_key(env: dict) -> bytes:
    raw = env.get('BACKUP_ENCRYPTION_KEY') or ''
    try:
        key = base64.urlsafe_b64decode(raw + '=' * (-len(raw) % 4))
    except ValueError:
        key = b''
    if len(key) != 32:
        sys.exit('.env 的 BACKUP_ENCRYPTION_KEY 沒設或格式不對（應為 32 bytes 的 base64url）')
    return key


def pg_bin(name: str) -> str:
    """找 PostgreSQL 安裝目錄裡的工具，多版本時取最新。"""
    found = sorted(
        glob.glob(rf'C:\Program Files\PostgreSQL\*\bin\{name}.exe'),
        key=lambda p: int(Path(p).parts[-3]) if Path(p).parts[-3].isdigit() else 0,
    )
    if found:
        return found[-1]
    exe = shutil.which(name)
    if exe:
        return exe
    sys.exit(f'找不到 {name}（PostgreSQL 有裝嗎？）')


def pg_env(env: dict) -> dict:
    e = os.environ.copy()
    e['PGPASSWORD'] = env.get('DB_PASSWORD') or ''
    return e


def log(dest: Path, msg: str) -> None:
    line = f'[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}'
    print(line)
    try:
        dest.mkdir(parents=True, exist_ok=True)
        with open(dest / 'backup.log', 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError:
        pass


def notify_failure(env: dict, subject: str, body: str) -> None:
    """用 .env 的 Gmail 設定寄失敗通知給樂團信箱；寄不出去也不影響 exit code。"""
    user, pwd = env.get('EMAIL_HOST_USER'), env.get('EMAIL_HOST_PASSWORD')
    if not (user and pwd):
        return
    try:
        msg = EmailMessage()
        msg['Subject'] = subject
        msg['From'] = env.get('DEFAULT_FROM_EMAIL') or user
        msg['To'] = user
        msg.set_content(body)
        with smtplib.SMTP(env.get('EMAIL_HOST') or 'smtp.gmail.com',
                          int(env.get('EMAIL_PORT') or 587), timeout=30) as s:
            s.starttls()
            s.login(user, pwd)
            s.send_message(msg)
    except Exception as e:  # noqa: BLE001 — 通知失敗只記錄，不能蓋掉原本的錯誤
        print(f'失敗通知寄不出去：{e}')


def encrypt(key: bytes, data: bytes) -> bytes:
    nonce = os.urandom(NONCE_LEN)
    return MAGIC + nonce + AESGCM(key).encrypt(nonce, data, MAGIC)


def decrypt(key: bytes, blob: bytes) -> bytes:
    if not blob.startswith(MAGIC):
        sys.exit('不是 FJCWO 備份檔（檔頭不符）')
    nonce = blob[len(MAGIC):len(MAGIC) + NONCE_LEN]
    try:
        return AESGCM(key).decrypt(nonce, blob[len(MAGIC) + NONCE_LEN:], MAGIC)
    except Exception:  # noqa: BLE001
        sys.exit('解密失敗：金鑰不對，或檔案已損毀')


def cmd_backup(args, base: Path, env: dict) -> int:
    dest = Path(args.dest)
    key = get_key(env)
    stamp = dt.datetime.now().strftime('%Y%m%d_%H%M%S')
    try:
        dest.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory() as tmp:
            dump = Path(tmp) / 'db.dump'
            subprocess.run(
                [pg_bin('pg_dump'), '-Fc',
                 '-h', env.get('DB_HOST') or 'localhost',
                 '-p', env.get('DB_PORT') or '5432',
                 '-U', env.get('DB_USER') or 'fjcwo',
                 '-d', env.get('DB_NAME') or 'fjcwo',
                 '-f', str(dump)],
                env=pg_env(env), check=True, capture_output=True, text=True,
            )
            buf = io.BytesIO()
            media = base / 'media'
            n_media = 0
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
                z.write(dump, 'db.dump')
                if media.is_dir():
                    for p in media.rglob('*'):
                        if p.is_file():
                            z.write(p, Path('media') / p.relative_to(media))
                            n_media += 1
                z.writestr('manifest.json', json.dumps({
                    'created': dt.datetime.now().isoformat(timespec='seconds'),
                    'db_name': env.get('DB_NAME') or 'fjcwo',
                    'db_dump_bytes': dump.stat().st_size,
                    'media_files': n_media,
                }, ensure_ascii=False, indent=2))
        out = dest / f'{PREFIX}{stamp}{EXT}'
        part = out.with_suffix(EXT + '.part')
        part.write_bytes(encrypt(key, buf.getvalue()))
        part.replace(out)   # 寫完才改名，排程中斷不會留下半個檔被當成好備份
        log(dest, f'OK {out.name} {out.stat().st_size:,} bytes（media {n_media} 個檔）')

        cutoff = dt.datetime.now() - dt.timedelta(days=args.keep_days)
        for old in dest.glob(f'{PREFIX}*{EXT}'):
            if dt.datetime.fromtimestamp(old.stat().st_mtime) < cutoff:
                old.unlink()
                log(dest, f'刪除超過 {args.keep_days} 天的舊備份 {old.name}')
        for stale in dest.glob(f'{PREFIX}*{EXT}.part'):
            stale.unlink()
        return 0
    except subprocess.CalledProcessError as e:
        err = f'pg_dump 失敗（exit {e.returncode}）：{(e.stderr or "").strip()[:500]}'
    except Exception as e:  # noqa: BLE001
        err = f'{type(e).__name__}: {e}'
    log(dest, f'FAIL {err}')
    notify_failure(env, '[FJCWO] 每日備份失敗', f'{dt.datetime.now():%Y-%m-%d %H:%M}\n\n{err}\n\n主機：{os.environ.get("COMPUTERNAME")}')
    return 1


def cmd_offsite(args, base: Path, env: dict) -> int:
    src, dest = Path(args.src), Path(args.dest)
    if not dest.parent.exists():
        log(src, f'OFFSITE SKIP 找不到 {dest.parent}（雲端硬碟沒掛載？使用者沒登入？）')
        return 1
    dest.mkdir(exist_ok=True)
    have = {p.name for p in src.glob(f'{PREFIX}*{EXT}')}
    copied = removed = 0
    for name in sorted(have):
        target = dest / name
        if not target.exists() or target.stat().st_size != (src / name).stat().st_size:
            shutil.copy2(src / name, target)
            copied += 1
    for p in dest.glob(f'{PREFIX}*{EXT}'):
        if p.name not in have:
            p.unlink()
            removed += 1
    log(src, f'OFFSITE OK 複製 {copied}、刪除 {removed}、雲端現有 {len(have)} 份')
    return 0


def _decrypt_zip(path: Path, env: dict) -> zipfile.ZipFile:
    return zipfile.ZipFile(io.BytesIO(decrypt(get_key(env), path.read_bytes())))


def cmd_verify(args, base: Path, env: dict) -> int:
    path = Path(args.file)
    with _decrypt_zip(path, env) as z, tempfile.TemporaryDirectory() as tmp:
        manifest = json.loads(z.read('manifest.json'))
        z.extract('db.dump', tmp)
        r = subprocess.run([pg_bin('pg_restore'), '--list', str(Path(tmp) / 'db.dump')],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f'pg_restore 讀不了：{r.stderr.strip()[:500]}')
            return 1
        tables = [l for l in r.stdout.splitlines() if ' TABLE DATA ' in l]
    print(f'{path.name}：解密 OK、資料庫備份可讀')
    print(f'  建立時間 {manifest["created"]}、資料表 {len(tables)} 個、media {manifest["media_files"]} 個檔')
    return 0


def cmd_decrypt(args, base: Path, env: dict) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with _decrypt_zip(Path(args.file), env) as z:
        z.extractall(out)
    print(f'已解到 {out}（db.dump 用 pg_restore 還原，media\\ 複製回網站目錄）')
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description='FJCWO 正式站備份工具')
    ap.add_argument('--base', default=str(Path(__file__).resolve().parent.parent),
                    help='網站目錄（讀它的 .env 與 media/），預設為本腳本的上一層')
    sub = ap.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('backup')
    b.add_argument('--dest', required=True)
    b.add_argument('--keep-days', type=int, default=30)
    o = sub.add_parser('offsite')
    o.add_argument('--src', required=True)
    o.add_argument('--dest', required=True)
    v = sub.add_parser('verify')
    v.add_argument('file')
    d = sub.add_parser('decrypt')
    d.add_argument('file')
    d.add_argument('out')
    args = ap.parse_args()
    base = Path(args.base)
    env = load_env(base)
    return {'backup': cmd_backup, 'offsite': cmd_offsite,
            'verify': cmd_verify, 'decrypt': cmd_decrypt}[args.cmd](args, base, env)


if __name__ == '__main__':
    sys.exit(main())
