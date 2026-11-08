# Windows 主機正式站部署指南

> 建立日期：2026-11-07
> 用途：用一台 Windows 主機（閒置筆電或桌機皆可，可隨時換機）當正式站（BACKLOG #10 路線 B 的落地版本）。
> 讀者：**在那台筆電上開 Claude Code 的人與 Claude 本身**。Claude 請依本文件逐步協助，
> 標「👤 使用者自己做」的步驟（金鑰、密碼、帳號登入）Claude 不代為處理，也不要把機密貼進對話。

## 部署前準備（任何 Windows 主機都適用）

**機器最低需求：**

| 項目 | 需求 |
|------|------|
| 系統 | Windows 11 專業版（RDP 被連端、完整 BitLocker 需要專業版；Win10 已停止一般支援，不建議）|
| 硬體 | TPM 2.0、Secure Boot、UEFI／GPT；RAM ≥ 8 GB；建議 SSD |
| 授權 | 使用者自己合法持有，不使用啟用工具或破解 |
| 管理 | 未被公司／學校網域或 MDM 管理（否則群組原則可能擋遠端桌面與 BitLocker）|
| 狀態 | 空機，或資料已備份（重灌會清掉）|

用下方「預檢指令」逐項驗證。**不合格就先補到合格再往下**（系統不合規 → 做 0-a 重灌）。

**機器專屬資料（規格、授權現況、決定、進度）一律記在 [SERVERS.md](SERVERS.md)，不寫在本文件。**
換 server 時：在 SERVERS.md 新增一節，本文件不用改。

**開始前，Claude 一次問使用者這幾題（答案記進 SERVERS.md）：**

| # | 問題 | 影響 |
|---|------|------|
| 1 | Windows 11 專業版序號？（沒有 → 先未啟用使用，之後補買）| 0-a 重灌 |
| 2 | 對外連線：Cloudflare Tunnel（需網域）還是 Tailscale Funnel（免網域）？網域是哪個？ | 第 8 節、`.env` |
| 3 | 異地備份放哪（Cloudflare R2／Google Drive）？外接硬碟備妥了嗎？ | 第 9 節 |
| 4 | 是否接「系統寫入紀錄」到試算表？ | 第 10 節 |

**Claude 的執行順序：**

1. 讀本文件、[SERVERS.md](SERVERS.md)、`_notes/GUIDE.md`。
2. 問上表 4 題；跑預檢指令確認機器合格。
3. 依第 3～9 節照序進行；標 👤 的步驟交給使用者，機密一律不貼進對話。
4. 每完成一節就更新 SERVERS.md 的進度與第 11 節檢查清單；最後 commit（走 Feature 分支＋PR，見 `WORKFLOW.md`）。

## 預檢指令與參數說明

> 在 server 筆電以**系統管理員 PowerShell** 執行。這些是「唯讀」查詢，不會改動系統。
> 每個參數在查什麼見表；實測結果記在 [SERVERS.md](SERVERS.md)。

| 指令 | 參數／片段的用途 | 在判斷什麼 |
|------|-----------------|-----------|
| `Get-CimInstance Win32_Processor \| Select Name` | `Win32_Processor` ＝ CPU 資訊類別；`Select Name` 只取型號 | 是否第 8 代以上（Win11 支援）|
| `(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory/1GB` | `Win32_ComputerSystem` ＝ 整機資訊；`/1GB` 把位元組換成 GB | RAM 夠不夠跑資料庫＋網站（建議 ≥ 8 GB）|
| `(Get-CimInstance Win32_ComputerSystem).Model` | 取機型名稱 | 查該機型是否 SSD、有無 TPM |
| `Get-Disk \| Select FriendlyName,Size,PartitionStyle` | `Size` ＝ 容量（位元組）；`PartitionStyle` ＝ `GPT` 或 `MBR` | `GPT` 才是 UEFI 開機；`MBR` 要先轉換才能升 Win11 |
| `Get-PhysicalDisk \| Select FriendlyName,MediaType,Size` | `MediaType` ＝ `SSD`／`HDD` | 硬碟是不是機械式（HDD 資料庫較慢、備份要更小心）。部分機器會空白，改用 `Get-Disk` |
| `tpm.msc` | 開啟「TPM 管理」視窗，看「規格版本」 | 是否 TPM 2.0（Win11 必要、BitLocker 需要）|
| `Confirm-SecureBootUEFI` | 回傳 `True`／`False`／錯誤 | `True` 才符合 Win11；`False` 進 BIOS 開啟；錯誤 ＝ 非 UEFI 開機 |
| `slmgr /dli` | `/dli` ＝ 顯示授權資訊（跳出視窗，不改動）| 看「描述」：`RETAIL` ＝ 零售、`OEM` ＝ 隨機、`VOLUME_KMS／MAK` ＝ 組織批次授權；看「授權狀態」是否已啟用 |
| `dsregcmd /status \| Select-String "AzureAdJoined\|DomainJoined\|MDMUrl"` | `/status` ＝ 顯示裝置註冊狀態；`Select-String` 只篩出三個欄位 | 是否被公司／學校網域或 MDM 管理（會有群組原則擋遠端桌面、BitLocker）|

**重灌／設定完成後要驗證的指令：**

| 指令 | 參數用途 | 在判斷什麼 |
|------|---------|-----------|
| `winver` | 開啟版本視窗 | 確認是 Windows 11 專業版 |
| `slmgr /xpr` | `/xpr` ＝ 顯示啟用到期狀態 | 是否永久啟用 |
| `manage-bde -status C:` | `manage-bde` ＝ BitLocker 管理工具；`-status` 查狀態；`C:` 為系統磁碟 | BitLocker 是否已加密、還原金鑰是否備份 |
| `powercfg /requests` | 列出阻止睡眠的項目 | 確認不會自己睡眠 |
| `powercfg /change standby-timeout-ac 0` | `standby-timeout-ac` ＝ 插電時的睡眠逾時；`0` ＝ 永不 | 設成永不睡眠（插電時）|
| `powercfg /change monitor-timeout-ac 0` | 同上，對象是螢幕關閉逾時 | 螢幕不需要也可保持，視使用者偏好 |
| `powercfg /setacvalueindex SCHEME_CURRENT SUB_BUTTONS LIDACTION 0` | `SUB_BUTTONS` ＝ 電源按鈕子群組；`LIDACTION` ＝ 闔蓋動作；`0` ＝ 不採取動作 | 闔蓋不睡眠；之後再跑 `powercfg /setactive SCHEME_CURRENT` 套用 |
| `winget install Python.Python.3.13 Git.Git` | `winget` ＝ Windows 套件管理員；後面是套件 ID | 一次安裝 Python 與 Git |
| `python -m venv venv` | `-m venv` ＝ 執行虛擬環境模組；最後的 `venv` 是資料夾名 | 建專案專用的 Python 環境 |
| `pip install -r requirements.txt waitress` | `-r` ＝ 依檔案安裝；`waitress` ＝ 另外加裝的 WSGI 伺服器 | 安裝依賴與 Windows 用的網站伺服器 |
| `manage.py collectstatic --noinput` | `--noinput` ＝ 不問是否覆蓋 | 把 static 檔集中，WhiteNoise 才找得到 |
| `manage.py migrate` | 套用遷移檔到資料庫 | 建好資料表 |
| `waitress --listen=127.0.0.1:8000 config.wsgi:application` | `--listen` ＝ 位址與埠；`127.0.0.1` ＝ 只讓本機連；最後是 WSGI 入口 | 只對本機開 8000，外部一律經過 Tunnel |
| `nssm install／restart／status FJCWO-Web` | NSSM ＝ 把程式包成 Windows 服務的工具；後面是動作與服務名 | 開機自動啟動、重啟、查狀態 |
| `pg_dump -U fjcwo -Fc fjcwo -f 檔案` | `-U` ＝ 使用者；`-Fc` ＝ custom 壓縮格式（可用 `pg_restore` 還原）；`-f` ＝ 輸出檔 | 每日備份 |
| `pg_restore -U fjcwo -d 測試資料庫 檔案` | `-d` ＝ 還原到哪個資料庫 | 每月還原演練 |

## 目錄

1. [為什麼這樣選、風險在哪](#1-為什麼這樣選風險在哪)
2. [架構總覽](#2-架構總覽)
3. [第 0 步：把筆電設成伺服器](#3-第-0-步把筆電設成伺服器)
4. [第 1 步：安裝 PostgreSQL](#4-第-1-步安裝-postgresql)
5. [第 2 步：放程式碼與 .env](#5-第-2-步放程式碼與-env)
6. [第 3 步：試跑](#6-第-3-步試跑)
7. [第 4 步：包成開機自動啟動的服務](#7-第-4-步包成開機自動啟動的服務)
8. [第 5 步：對外連線](#8-第-5-步對外連線)
9. [第 6 步：備份（最重要）](#9-第-6-步備份最重要)
10. [第 7 步：試算表寫入紀錄（後續）](#10-第-7-步試算表寫入紀錄後續)
11. [上線前檢查清單](#11-上線前檢查清單)
12. [日常維運](#12-日常維運)

---

## 1. 為什麼這樣選、風險在哪

之前用 Render 免費網站＋Neon 免費資料庫，資料庫被清空過一次。免費方案沒有可靠的還原機制，
所以改成自己掌握資料。

**這個方案的結構性風險（務必知道）**：

| 風險 | 後果 | 對策 |
|------|------|------|
| 只有一台機器 | 硬碟壞、被偷、進水，資料全沒 | 第 6 步：外接硬碟＋雲端異地備份 |
| 家裡斷電／斷網 | 網站暫時連不上 | 筆電電池當簡易 UPS；BIOS 設來電自動開機 |
| 加密金鑰遺失 | 敏感個資永遠解不開 | `.env` 另存密碼管理器 |
| 被偷或被入侵 | 個資外洩 | BitLocker、強密碼、不對外開任何 port |

**掉資料的真正防線是「異地備份＋定期還原演練」，不是換主機。**

## 2. 架構總覽

| 元件 | 用什麼 |
|------|--------|
| 資料庫 | PostgreSQL（Windows 安裝版，開機服務），只聽 localhost |
| 網站 | Python venv ＋ Waitress（gunicorn 只能在 Unix 跑），用 NSSM 包成 Windows 服務 |
| 靜態檔 | WhiteNoise（已在專案內） |
| 對外連線 | Cloudflare Tunnel（要網域）**或** Tailscale Funnel（免網域），不開路由器 port |
| 備份 | 每日 `pg_dump` → 外接硬碟 ＋ 加密後上傳雲端 |

不用 Docker、不用 WSL2：筆電上少一層，出問題好排查。

## 3. 第 0 步：把筆電設成伺服器

### 0-a　重灌 Windows 11 專業版（僅在預檢顯示系統或授權不合規時才做）

1. 👤 在另一台電腦下載微軟官方「Windows 11 媒體建立工具」，用 8 GB 以上隨身碟製作安裝碟。
2. 👤 插到 server 筆電，重開機連按 `Esc`（華碩開機選單），選隨身碟開機。
3. 👤 選「自訂安裝」，刪除舊分割區後安裝；版本選**專業版**；沒有序號就選「我沒有產品金鑰」。
4. 👤 建立**本機帳號**（不連 Microsoft 帳號），強密碼。
5. 裝好後跑上方「重灌後要驗證的指令」確認版本、BitLocker、電源設定。

### 0-b　系統設定

👤 以下在 Windows 設定裡做：

1. 一直插著電源。
2. 設定 → 系統 → 電源 → 螢幕與睡眠都設「永不」。
3. 控制台 → 電源選項 → 「關上螢幕時」→ 不採取任何動作。
4. Windows Update 的「使用時間」盡量拉寬，避免半夜自動重開。服務設成自動啟動，重開機也會自己恢復。
5. 進 BIOS，把 **Restore on AC Power Loss**（或 After power failure）設成開機。
6. 路由器替這台筆電保留固定內網 IP。
7. 開 BitLocker，登入用強密碼。

## 4. 第 1 步：安裝 PostgreSQL

1. 👤 從 postgresql.org 下載 Windows 安裝程式（最新穩定大版本），全部用預設值。
2. 👤 安裝時為 `postgres` 超級使用者設密碼，存進密碼管理器。
3. 建立資料庫與專用帳號（密碼由使用者自己決定，不要貼進對話）：

```sql
CREATE USER fjcwo WITH PASSWORD '換成強密碼';
CREATE DATABASE fjcwo OWNER fjcwo;
```

4. 保持預設只聽 `localhost`，**不要對外開 5432**。

## 5. 第 2 步：放程式碼與 .env

```powershell
winget install Python.Python.3.13 Git.Git
git clone https://github.com/sammy51305/FJCWO-Web.git C:\FJCWO-Web
cd C:\FJCWO-Web
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
```

> `waitress` 已列在 `requirements.txt`（Windows 用它取代 gunicorn）。

建立 `C:\FJCWO-Web\.env`（**不進 git**）。變數名稱以 `render.yaml`、[SETUP.md](SETUP.md) 情境 E
與 `config/settings.py` 為準，Claude 請先讀過再協助填，不要憑空猜名稱。需要設定的有：

- 新的 `DJANGO_SECRET_KEY`（不要沿用本機或測試站那把）
- `DJANGO_DEBUG=False`
- 資料庫連線：用 `DB_NAME=fjcwo`、`DB_USER=fjcwo`、`DB_PASSWORD=…`、`DB_HOST=localhost`、`DB_PORT=5432`。
  **不要設 `DATABASE_URL`**：設了它，`settings.py` 會強制 `ssl_require=True`（給 Neon 等託管資料庫用），
  本機 PostgreSQL 預設沒開 SSL，會連不上（`server does not support SSL`）。
- `DJANGO_ALLOWED_HOSTS`（不含 `https://`）與 `DJANGO_CSRF_TRUSTED_ORIGINS`（含 `https://`），填最終對外網域
- `DJANGO_FIELD_ENCRYPTION_KEY`（**遺失就解不開個資，另存密碼管理器**）
- Gmail SMTP 設定，沿用測試站那組
- 強制 https 與 secure cookie：`DJANGO_SECURE_SSL_REDIRECT=True`、`DJANGO_SECURE_COOKIES=True`（同 `render.yaml`）。
  前者也會開啟 `SECURE_PROXY_SSL_HEADER`，靠反向代理送的 `X-Forwarded-Proto` 判斷 https——Waitress 要另外設定才會轉交這個 header，見第 3 步。
- **不要**設 `DJANGO_ROBOTS_NOINDEX=True`（那是測試站用的，正式站要讓公開頁被搜尋到）

初始化：

```powershell
venv\Scripts\python.exe manage.py collectstatic --noinput
venv\Scripts\python.exe manage.py migrate
```

基礎資料（fixtures）照 [SETUP.md](SETUP.md) 步驟六。要搬試算表的團練資料，用現有的
`manage.py import_sheet`（見 DESIGN §4.23，預設試跑、`--commit` 才寫入）。

建立第一個幹部帳號：👤 由使用者自己執行 `manage.py createsuperuser` 並自己輸入密碼。

## 6. 第 3 步：試跑

```powershell
venv\Scripts\python.exe -m waitress --listen=127.0.0.1:8000 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-proto config.wsgi:application
```

在筆電瀏覽器開 `http://127.0.0.1:8000`，確認首頁、登入、一個幹部頁面、static 都正常。
（`config.wsgi` 即專案的 `config/wsgi.py`。）

> ⚠️ `--trusted-proxy`／`--trusted-proxy-headers` 不能省：Waitress 3 預設會**丟掉** `X-Forwarded-Proto`，
> Django 會一直以為是 http，在 `DJANGO_SECURE_SSL_REDIRECT=True` 下無限轉址。Cloudflare Tunnel／Tailscale 都從本機（127.0.0.1）連進來，
> 所以信任 127.0.0.1 即可。（2026-11-07 以 waitress 3.0.2 實測：不加時 header 被清掉，加了才收得到。）
> 本機試跑時直接開 `http://127.0.0.1:8000` 若被轉到 https，是因為已設 `DJANGO_SECURE_SSL_REDIRECT=True`；試跑階段可先設 False，對外連線接好再打開。

## 7. 第 4 步：包成開機自動啟動的服務

1. 下載 NSSM，把 `nssm.exe` 放到 `C:\nssm`。
2. 用系統管理員 PowerShell：

```powershell
C:\nssm\nssm.exe install FJCWO-Web
```

3. 在視窗中填：
   - Path：`C:\FJCWO-Web\venv\Scripts\python.exe`
   - Startup directory：`C:\FJCWO-Web`
   - Arguments：`-m waitress --listen=127.0.0.1:8000 --trusted-proxy=127.0.0.1 --trusted-proxy-headers=x-forwarded-proto config.wsgi:application`
4. I/O 分頁：stdout、stderr 都導到 `C:\FJCWO-Web\logs\web.log`。
5. 啟動類型保持「自動」。
6. 重開機一次，確認網站自己回來。

更新程式的流程見 [第 12 節](#12-日常維運)。

## 8. 第 5 步：對外連線

先決定一個，**不要兩個都開**。

### 選項 A：Cloudflare Tunnel（需要網域，約每年 US$10）

1. 👤 把網域託管到 Cloudflare（免費方案）。
2. 👤 Zero Trust → Networks → Tunnels 建立 Tunnel，照畫面給的指令在筆電安裝 `cloudflared`
   （會註冊成 Windows 服務）。
3. Public Hostname：`fjcwo.你的網域` → `http://localhost:8000`。
4. 家裡 IP 不曝光、路由器不用開 port，HTTPS 由 Cloudflare 處理。
5. Django 靠 `X-Forwarded-Proto` 辨識 https：`.env` 設 `DJANGO_SECURE_SSL_REDIRECT=True`，Waitress 帶 `--trusted-proxy` 參數（第 3 步）。

### 選項 B：Tailscale Funnel（免網域）

1. 👤 在筆電安裝 Tailscale 並登入。
2. 啟用 Funnel，把 8000 port 公開成 `https://機器名.tailnet名.ts.net`。
3. 網址較長，但免費、設定快。
4. 同樣要把這個網址填進 `DJANGO_ALLOWED_HOSTS` 與 `DJANGO_CSRF_TRUSTED_ORIGINS`。
5. 接好後用 `curl -I https://機器名.tailnet名.ts.net/` 確認回 200 而不是一直 301 轉址；
   若一直轉址，代表 Funnel 沒送 `X-Forwarded-Proto`，請 Claude 協助排查（尚未實測過 Funnel 的 header 行為）。

## 9. 第 6 步：備份（最重要）

三層缺一不可：

1. **每日 `pg_dump` 到外接硬碟**：Windows 工作排程器，每天凌晨跑。

```powershell
& "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" -U fjcwo -Fc fjcwo -f "E:\backup\fjcwo_$(Get-Date -Format yyyyMMdd).dump"
```

   版本號 `17` 換成實際安裝的版本。密碼用 `PGPASSWORD` 環境變數或 `pgpass.conf` 帶入，
   **不要寫死在排程指令裡**。保留最近 30 天，舊的自動清掉。
2. **異地一份**：把 dump 加密後傳到雲端（Cloudflare R2 或 Google Drive），保留 30 天。
   雲端的存取金鑰由使用者自己建立、自己放進環境變數。
3. **每月還原演練**：在另一個空資料庫還原一次，確認資料真的回得來。
   沒驗證過的備份等於沒有備份。

另外把 `.env`（尤其加密金鑰）存進密碼管理器，**不要和資料庫備份放在同一處**。

Claude 可協助撰寫 `scripts/backup.ps1`（dump、保留天數、上傳、失敗時通知）與排程設定。

## 10. 第 7 步：試算表寫入紀錄（後續）

網站穩定後再做。這是第二層保險，讓萬一掉資料時能對照、手動補，**不是自動還原**。

- 目標試算表：「輔仁百韻管樂團 團練紀錄（出席・請假・團費）」。
  **不要寫進「收支」分頁**（gid=8，有預算與公式），改在同一份檔案新增「系統寫入紀錄」分頁，只附加。
- 做法：Django `post_save`／`post_delete` signal 攔下重要 Model（財務、團費、出席、請假、入團申請、
  排練、演出），先寫進本地 outbox 資料表，再由背景批次附加到試算表；Google 掛掉或限流時不拖垮網站、也不漏記。
- 每筆內容：時間、操作者、動作、Model、主鍵、變更後欄位值（JSON）。
- **不寫入的欄位**：身分證、地址、生日等加密欄位、密碼。
- 憑證：👤 使用者自己建立 Google 服務帳號、把它加為試算表編輯者，金鑰放環境變數，不貼進對話。
- 實作後需同步更新 Architecture.md、DESIGN.md、TESTING.md（依 CLAUDE.md 的 commit 前 checklist）。

## 11. 上線前檢查清單

- [ ] 筆電：不睡眠、闔蓋不動作、BIOS 來電自動開機、BitLocker 已開
- [ ] `DJANGO_DEBUG=False`，`DJANGO_SECRET_KEY` 是新的
- [ ] `DJANGO_FIELD_ENCRYPTION_KEY` 已設，且另存密碼管理器
- [ ] PostgreSQL 只聽 localhost，5432 沒對外開
- [ ] 重開機後網站、資料庫、`cloudflared`／Tailscale 都自動恢復
- [ ] 對外網址 https 可連，登入、幹部頁、static 正常
- [ ] Email 寄得出去（臨時密碼信）
- [ ] 每日備份有跑，外接硬碟與雲端各有一份
- [ ] **已做過一次還原演練**
- [ ] 測試站（Render）的資料不是真資料，上線後確認舊測試站停用或不再被使用

## 12. 日常維運

更新程式：

```powershell
cd C:\FJCWO-Web
git pull
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe manage.py migrate
venv\Scripts\python.exe manage.py collectstatic --noinput
C:\nssm\nssm.exe restart FJCWO-Web
```

出問題時先看：

| 症狀 | 看哪裡 |
|------|--------|
| 網站打不開 | `C:\FJCWO-Web\logs\web.log`、服務是否在跑（`nssm status FJCWO-Web`）|
| 外網連不上、內網正常 | `cloudflared`／Tailscale 服務狀態 |
| `relation does not exist` | 跑 `migrate` |
| `ModuleNotFoundError` | 跑 `pip install -r requirements.txt` |
| 重開機後起不來 | PostgreSQL 服務是否先啟動、NSSM 服務是否設為自動 |

**每次大改動前先手動跑一次備份。**
