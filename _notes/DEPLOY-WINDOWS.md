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
| 5 | 部署方式：Windows 原生（預設）還是 Hyper-V ＋ Ubuntu VM（同機還要當 NAS 時考慮）？ | 走第 3～7 節，或走附錄 A |

**Claude 的執行順序：**

1. 讀本文件、[SERVERS.md](SERVERS.md)、`_notes/GUIDE.md`。
2. 問上表 4 題；跑預檢指令確認機器合格。
3. 依第 3～9 節照序進行；標 👤 的步驟交給使用者，機密一律不貼進對話。
4. 每完成一節就更新 SERVERS.md 的進度與第 11 節檢查清單；最後 commit（走 Feature 分支＋PR，見 `WORKFLOW.md`）。

## 事前準備清單（開工前備齊，可省下大量來回）

> Claude 開始前請先對照本清單，**逐項問使用者「備好了嗎」**，缺的先補，不要做到一半才發現。
> 機密（密碼、金鑰、token、序號）一律由 👤 使用者自己存進**密碼管理器**，之後自己貼進 `.env` 或設定畫面，**不貼進對話**。

### 一、要先決定的事

| # | 項目 | 備註 |
|---|------|------|
| 1 | Windows 原生還是 Hyper-V ＋ Ubuntu VM | 同機還要當 NAS 才考慮 VM（附錄 A）|
| 2 | 對外連線：Cloudflare Tunnel 還是 Tailscale Funnel | Tunnel 需要網域 |
| 3 | 網域名稱（若用 Tunnel） | 例如 `fjcwo.你的網域` |
| 4 | 異地備份放哪：Cloudflare R2 或 Google Drive | 影片等大檔不建議備份到雲端，只備份資料庫與上傳檔 |
| 5 | 要不要接「系統寫入紀錄」到試算表 | 第 10 節，可以上線後再做 |
| 6 | 資料搬遷：要不要把試算表的團練紀錄用 `import_sheet` 匯入 | 要的話先備好最新的 `.xlsx`（不進 git）|

### 二、要先備好的帳號與硬體

| 項目 | 用途 | 狀態 |
|------|------|------|
| Windows 11 專業版序號（或決定先未啟用）| 重灌 | ☐ |
| 8 GB 以上隨身碟 | 製作 Windows 安裝碟（VM 版另需 Ubuntu ISO）| ☐ |
| 外接硬碟（容量夠放 30 天資料庫備份）| 本地備份 | ☐ |
| GitHub 帳號可 clone 專案 | 取得程式碼 | ☐ |
| 密碼管理器 | 存所有機密 | ☐ |
| Cloudflare 帳號＋網域（選 Tunnel）或 Tailscale 帳號（選 Funnel）| 對外連線 | ☐ |
| Gmail 應用程式密碼（16 碼）| 寄臨時密碼信（沿用測試站那組即可）| ☐ |
| 雲端備份的存取金鑰（R2 或 Google）| 異地備份 | ☐ |
| Google 服務帳號金鑰（若接試算表寫入紀錄）| 第 10 節 | ☐ |

### 三、要先產生並存好的機密（👤 自己做）

| 項目 | 注意 |
|------|------|
| `DJANGO_SECRET_KEY` | 新產生，不要沿用本機或測試站那把 |
| `DJANGO_FIELD_ENCRYPTION_KEY` | **遺失 ＝ 敏感個資永遠解不開**，存進密碼管理器並**另備一份**。正式站若要沿用測試站已加密的資料，要用同一把；全新資料庫則新產生 |
| 資料庫密碼 | 建 `fjcwo` 資料庫帳號時用 |
| Windows 本機帳號密碼、（VM 版）Ubuntu 帳號密碼與 SSH passphrase | 強密碼 |
| BitLocker 還原金鑰 | 開啟 BitLocker 時產生，**不要只存在這台機器上** |
| 超級管理員（幹部）帳號密碼 | `createsuperuser` 時自己輸入 |

### 四、跟 Claude 合作的方式

1. **一次做一節**：照第 3～9 節（或附錄 A）的順序，做完一節、驗證一節，再往下。不要叫它「全部做完」。
2. **每節結束，要 Claude 更新 [SERVERS.md](SERVERS.md) 的進度表**，下一個 session 才接得上。
3. **遇到需要重開機的步驟**（啟用 Hyper-V、Windows 更新）：Claude 的對話會中斷，重開後直接說「繼續，先讀 SERVERS.md 的進度」。
4. **Claude 遇到標 👤 的步驟會停下來說明要你做什麼**，做完回報即可。
5. **指令沒在實機驗證過的部分**（尤其附錄 A、Tailscale Funnel 的 header 行為）：Claude 要先看輸出再繼續，失敗時回報原文錯誤訊息，不要硬往下。
6. **改動文件或程式**一律走 Feature 分支＋PR，見 `WORKFLOW.md`。

### 五、預計要重開機或會中斷的步驟

| 步驟 | 原因 |
|------|------|
| 0-a 重灌 Windows | 整台重裝，Claude 要重新安裝 |
| 啟用 Hyper-V（附錄 A-1）| 要重開機 |
| 電源設定、BitLocker | 部分設定需重開才生效 |
| 重灌 Windows 後的第一次更新 | 可能連續重開幾次，先把更新跑完再往下 |

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
10. [第 7 步：試算表寫入紀錄（後續）](#10-第-7-步試算表寫入紀錄後續)（含 [10-b 選用：Google 帳號登入](#10-b選用google-帳號登入)）
11. [上線前檢查清單](#11-上線前檢查清單)
12. [日常維運](#12-日常維運)
13. [附錄 A：改用 Hyper-V 跑 Ubuntu（進階）](#附錄-a改用-hyper-v-跑-ubuntu進階非上線前提)

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
同一台機器還要當 NAS、想把網站隔開時，改走 [附錄 A](#附錄-a改用-hyper-v-跑-ubuntu進階非上線前提)（Hyper-V ＋ Ubuntu VM）。附錄 A 取代第 3～7 節，不是疊加。

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

4. **只聽 `localhost`，不要對外開 5432**。注意：EDB 安裝版預設是 `listen_addresses = '*'`（聽所有網卡），
   要改 `C:\Program Files\PostgreSQL\<版本>\data\postgresql.conf` 成 `listen_addresses = 'localhost'` 再重啟服務
   （`pg_hba.conf` 預設只允許 127.0.0.1／::1 登入，是第二道防線）。驗證：`Get-NetTCPConnection -LocalPort 5432 -State Listen`
   只應看到 `127.0.0.1`／`::1`。存檔要用**無 BOM** 的 UTF-8，PowerShell 5.1 的 `Set-Content -Encoding utf8` 會加 BOM，可能讓 PostgreSQL 讀設定檔失敗。

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
   或用系統管理員 PowerShell `winget install NSSM.NSSM --scope machine`（重開 PowerShell 後直接打 `nssm`，下文的 `C:\nssm\nssm.exe` 都換成 `nssm`），
   再用 `nssm install／set` 指令一次設好（不開視窗）：`AppDirectory`、`AppStdout`／`AppStderr`、`AppRotateFiles 1`（每次服務啟動時輪替 log）、
   **不要開 `AppRotateOnline`**（2026-11-10 實測：NSSM 2.24 開了它，停止服務時會卡在 Stop Pending，只能強制結束 nssm 行程）、
   `Start SERVICE_AUTO_START`、`DependOnService postgresql-x64-<版本>`（資料庫先起來）。實際指令與設定值見 SERVERS.md 該機器的進度。
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

1. 👤 在 server 安裝 Tailscale（tailscale.com/download）並登入。可以提早做，順便當遠端維護通道。
2. 👤 **Server 必做的三項設定**（漏了會在重開機或半年後突然斷線）：
   - 系統匣 Tailscale 圖示 → Preferences → 勾 **Run unattended**：沒登入 Windows 也保持連線（停電重開後不會有人登入）。
   - 管理後台 Machines → 這台 → `…` → **Disable key expiry**：否則預設 180 天後金鑰過期、網站斷線。
   - 同一選單 **Edit machine name** 改成好記的名字（如 `fjcwo`），網址會變 `https://fjcwo.tailnet名.ts.net`。**改名要在設定 `.env` 網域之前**。
3. 網站在 8000 跑起來後（第 4 步完成），系統管理員 PowerShell 執行 `tailscale funnel --bg 8000`。
   第一次執行若提示要在後台開啟 HTTPS 憑證或 Funnel 權限，👤 照它給的連結點同意。`--bg` ＝ 背景常駐、重開機後保留；`tailscale funnel status` 查狀態。
4. 同樣要把這個網址填進 `DJANGO_ALLOWED_HOSTS` 與 `DJANGO_CSRF_TRUSTED_ORIGINS`。
5. 接好後用 `curl -I https://機器名.tailnet名.ts.net/` 確認回 200 而不是一直 301 轉址。
   （2026-11-10 實測：Funnel 會送 `X-Forwarded-Proto: https`，搭配第 3 步的 Waitress 參數，`DJANGO_SECURE_SSL_REDIRECT=True` 下外部 https 回 200、本機 http 回 301，cookie 帶 `Secure`。）
6. `.env` 的兩個 SECURE 旗標改完要**重啟服務才生效**（系統管理員 PowerShell `Restart-Service FJCWO-Web`）；驗證方式：`http://127.0.0.1:8000/` 應回 301。

## 9. 第 6 步：備份（最重要）

三層缺一不可，全部由 `scripts/backup.py` 處理（用法見檔頭）：

| 子指令 | 做什麼 |
|--------|--------|
| `backup --dest D:\FJCWO-Backup` | `pg_dump -Fc` ＋ `media/` 打包，以 `.env` 的 `BACKUP_ENCRYPTION_KEY` 用 AES-256-GCM 加密成 `fjcwo_日期_時間.fjbk`；保留 30 天；失敗時 exit≠0 並寄信到樂團信箱 |
| `offsite --src D:\FJCWO-Backup --dest "G:\我的雲端硬碟\FJCWO-Backup"` | 把 `.fjbk` 鏡像到 Google Drive 電腦版的同步資料夾（雲端保留天數跟本地一致）|
| `verify 檔案` | 解密＋`pg_restore --list`，確認備份可讀（不碰資料庫）|
| `decrypt 檔案 輸出資料夾` | 解出 `db.dump`、`media\`、`manifest.json`，還原用 |

1. **每日備份到外接硬碟**：工作排程器以 **SYSTEM** 身分每天凌晨跑 `backup`（沒人登入也會跑）。
   資料庫密碼由腳本從 `.env` 讀、以環境變數交給 `pg_dump`，**不寫在排程指令裡**。
2. **異地一份**：Google Drive 電腦版是**每位使用者各自掛載** `G:`，SYSTEM 看不到、沒登入時也不存在，
   所以 `offsite` 要另排一個**以該使用者身分、登入時才執行**的排程（每日＋登入時各觸發一次）。
   → server 的 Windows 帳號要**保持登入（鎖定畫面即可）**；重開機後記得登入一次，異地備份才會追上。
3. **還原演練**（上線前一次，之後每月一次）：在另一個空資料庫還原，確認資料真的回得來。沒驗證過的備份等於沒有備份。

```powershell
# 👤 建空資料庫要 postgres 超級使用者密碼；fjcwo 是擁有者，之後的還原與刪除都用 fjcwo
& "C:\Program Files\PostgreSQL\17\bin\createdb.exe" -U postgres -O fjcwo fjcwo_restore_test
venv\Scripts\python.exe scripts\backup.py decrypt D:\FJCWO-Backup\<最新>.fjbk C:\FJCWO-RestoreTest
& "C:\Program Files\PostgreSQL\17\bin\pg_restore.exe" -U fjcwo -d fjcwo_restore_test --no-owner C:\FJCWO-RestoreTest\db.dump
# 比對幾個資料表的筆數與正式庫一致後：
& "C:\Program Files\PostgreSQL\17\bin\dropdb.exe" -U fjcwo fjcwo_restore_test
Remove-Item -Recurse C:\FJCWO-RestoreTest
```

`.env`（含 `DJANGO_FIELD_ENCRYPTION_KEY` 與 `BACKUP_ENCRYPTION_KEY`）存進密碼管理器，**不要和備份放在同一處**：
金鑰遺失 ＝ 備份解不開；金鑰和備份放一起 ＝ 加密沒有意義。

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

### 10-b　選用：Google 帳號登入

不設定也完全不影響網站，登入頁只是不顯示 Google 按鈕。運作規則見 DESIGN「Google 帳號登入」。

1. 👤 [Google Cloud Console](https://console.cloud.google.com/) 建一個專案（例如 `fjcwo-web`）。
2. 👤「API 和服務 → OAuth 同意畫面」：使用者類型選**外部**，應用程式名稱填樂團名稱，
   範圍只要預設的 `openid`、`email`（不需送審）。填完後按**發布應用程式**——停在「測試」狀態時
   只有手動加入的測試使用者能登入。
3. 👤「憑證 → 建立憑證 → OAuth 用戶端 ID」，類型選**網頁應用程式**，「已授權的重新導向 URI」填：
   - 正式站：`https://<對外網址>/accounts/login/google/callback/`
     （目前為 `https://fjcwo.tail064d2b.ts.net/accounts/login/google/callback/`）
   - 本機開發（選填）：`http://localhost:8000/accounts/login/google/callback/`
   要逐字相同，含結尾斜線；換對外網址時這裡也要跟著改。
4. 把用戶端 ID 與密鑰寫進 `.env` 的 `GOOGLE_OAUTH_CLIENT_ID` / `GOOGLE_OAUTH_CLIENT_SECRET`，
   **另存密碼管理器**，然後重啟服務（`nssm restart FJCWO-Web`）。
5. 驗證：登入頁出現「使用 Google 帳號登入」；用一個 email 與團員資料相同的 Gmail 試登入成功；
   用一個不在名單內的 Gmail 試，應被擋下且不會產生新帳號。

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

更新程式：**server 不會自動抓新版**，push 到 GitHub（merge 進 `main`）之後，要在 server 上手動更新。
用系統管理員 PowerShell 跑一鍵更新腳本：

```powershell
powershell -ExecutionPolicy Bypass -File C:\FJCWO-Web\scripts\update.ps1
```

它依序做：先備份 → `git pull --ff-only` → `pip install` → `migrate` → `collectstatic` → 重啟服務 → 確認網站有回應；
任何一步失敗就停下、不重啟服務。最後的「確認網站」用 `curl.exe` 打本機 `http://127.0.0.1:8000/`，最多重試 30 秒；
開了 SSL 旗標後本機 http 回 **301 是正常的**（200／301／302 都算通過，`000` 代表連不上）。
若只有這一步報錯、前面全部 OK，先用手機開對外網址確認，多半是服務還在啟動。
刻意**不排程自動更新**：merge 不等於可以上線（例如需要先填 `.env` 的功能），且沒人看著時 migrate 失敗不易察覺。
server 上的 `C:\FJCWO-Web` **不要直接改程式**（`pull --ff-only` 會因此失敗），改動一律在開發機做、走 PR。

出問題時先看：

| 症狀 | 看哪裡 |
|------|--------|
| 網站打不開 | `C:\FJCWO-Web\logs\web.log`、服務是否在跑（`nssm status FJCWO-Web`）|
| 外網連不上、內網正常 | `cloudflared`／Tailscale 服務狀態 |
| `relation does not exist` | 跑 `migrate` |
| `ModuleNotFoundError` | 跑 `pip install -r requirements.txt` |
| 重開機後起不來 | PostgreSQL 服務是否先啟動、NSSM 服務是否設為自動 |

**每次大改動前先手動跑一次備份**（`update.ps1` 已內建）。查備份狀況：`D:\FJCWO-Backup\backup.log`。

---

## 附錄 A：改用 Hyper-V 跑 Ubuntu（進階，非上線前提）

> 在 Windows 主機上用 Hyper-V 開一台 Ubuntu 虛擬機，網站與資料庫都裝在 Ubuntu 裡；Windows 本身只負責 NAS 與管理。
> **這是替代第 3～7 節的另一條路，不是疊加**：選了 VM，就不要再在 Windows 上裝 PostgreSQL 與 Waitress 服務。
> 第 0 步（Windows 重灌與電源設定）、第 8 節對外連線的觀念、第 9 節備份的原則、第 10 節、第 11 節仍適用，只是指令改成 Linux 版（本附錄已列出）。
> 本附錄的指令尚未在實機驗證，Claude 執行時請先看輸出再繼續，遇到版本差異以官方文件為準。

### A-0　何時用、何時不用

| 適合用 VM | 不需要 VM |
|-----------|-----------|
| 同一台 Windows 還要當 NAS，想把網站隔開 | 這台只跑網站 |
| 想讓環境與長期規劃的 Ubuntu 正式站一致，以後好搬家 | 想最快上線、不想多管一個 Linux |
| 願意維護 Linux（更新、SSH、備份）| — |

```
Windows 主機（實體）
├── 影片共用資料夾（NAS，SMB，只開給內網／Tailscale）
└── Hyper-V 虛擬機：Ubuntu Server 24.04
    ├── PostgreSQL（只聽 localhost）
    ├── Gunicorn（systemd 服務，聽 127.0.0.1:8000）
    └── cloudflared 或 Tailscale（對外連線）
```

**與 Windows 原生版的差異：**

| 項目 | Windows 原生 | Ubuntu VM |
|------|-------------|-----------|
| WSGI 伺服器 | Waitress | Gunicorn（`requirements.txt` 已有）|
| 開機自動啟動 | NSSM 服務 | systemd 服務 |
| 資料庫 | PostgreSQL Windows 安裝版 | `apt install postgresql` |
| 備份排程 | 工作排程器＋`pg_dump` | systemd timer／cron＋`pg_dump` |
| 代理 header | Waitress 要加 `--trusted-proxy…` | Gunicorn 預設信任 127.0.0.1，不用加 |
| 隔離 | 靠帳號權限與防火牆 | 網站被入侵也困在 VM 內 |

### A-1　啟用 Hyper-V（需 Windows 11 專業版）

👤 以**系統管理員 PowerShell** 執行，完成後重開機：

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
```

| 片段 | 用途 |
|------|------|
| `Enable-WindowsOptionalFeature` | 開啟一項 Windows 選用功能 |
| `-Online` | 對目前正在跑的系統操作（不是對離線映像）|
| `-FeatureName Microsoft-Hyper-V` | 要開的功能：Hyper-V |
| `-All` | 連它相依的子功能一起開 |

另外要在 BIOS 開啟虛擬化（Intel VT-x／AMD-V，常叫 Virtualization Technology）。
驗證：`Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V` 的 `State` 為 `Enabled`。

### A-2　建立虛擬機

1. 👤 下載 **Ubuntu Server 24.04 LTS** 的 ISO（ubuntu.com/download/server）。
2. 開「Hyper-V 管理員」→ 動作 → 新增 → 虛擬機器，照下表設定：

| 項目 | 建議值 | 理由 |
|------|--------|------|
| 名稱 | `fjcwo` | 好認 |
| 世代 | **第 2 代** | UEFI 開機，Ubuntu 24.04 支援 |
| 啟動記憶體 | 4096 MB | 資料庫＋網站綽綽有餘；至少 2048 MB |
| 網路 | **Default Switch** | NAT：VM 能上網、不直接暴露在家中區網；主機可用 `fjcwo.mshome.net` 連到 VM |
| 虛擬硬碟 | 40 GB，**放在 SSD** | 資料庫要快；不要放在存影片的 HDD |
| 安裝媒體 | 剛下載的 ISO | |

3. 👤 **第 2 代 VM 要改安全開機範本**，否則 Ubuntu 開不了機（先別啟動 VM）：

```powershell
Set-VMFirmware -VMName fjcwo -SecureBootTemplate MicrosoftUEFICertificateAuthority
Set-VM -Name fjcwo -AutomaticStartAction Start -AutomaticStopAction ShutDown -CheckpointType Disabled
```

| 指令／參數 | 用途 |
|-----------|------|
| `Set-VMFirmware -SecureBootTemplate MicrosoftUEFICertificateAuthority` | 改用適合 Linux 的安全開機憑證範本（預設是給 Windows 的）|
| `-AutomaticStartAction Start` | Windows 開機時 VM 自動啟動 |
| `-AutomaticStopAction ShutDown` | Windows 關機時 VM 正常關機（不是直接斷電），保護資料庫 |
| `-CheckpointType Disabled` | 關掉檢查點。**檢查點不是備份**，回溯舊檢查點會讓資料庫回到過去，造成掉資料 |

### A-3　安裝 Ubuntu Server

啟動 VM、連線後，安裝程式依序選：

1. 語言 English；鍵盤照實際。
2. 安裝類型：**Ubuntu Server**（標準，不選 minimized）。
3. 網路：維持 DHCP。
4. 磁碟：整顆使用（Use an entire disk），其餘預設。
5. 👤 設定使用者名稱、主機名 `fjcwo`、**強密碼**（存密碼管理器）。
6. **勾選 Install OpenSSH server**（之後從 Windows 用 SSH 操作）。
7. 不選任何 Featured Server Snaps。
8. 安裝完成後重開機，退出 ISO。

### A-4　SSH 登入與基本防護

在 **Windows 主機**的 PowerShell：

```powershell
ssh 你的使用者名稱@fjcwo.mshome.net
```

進到 Ubuntu 後：

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y ufw unattended-upgrades
sudo ufw allow OpenSSH
sudo ufw enable
```

| 指令／參數 | 用途 |
|-----------|------|
| `apt update` | 更新套件清單 |
| `apt full-upgrade -y` | 升級全部套件；`-y` ＝ 自動回答 yes |
| `ufw allow OpenSSH` | 防火牆放行 SSH（**先放行再啟用**，否則會把自己鎖在外面）|
| `ufw enable` | 啟用防火牆；之後除了 SSH，預設全部擋掉 |
| `unattended-upgrades` | 自動安裝安全性更新 |

之後**改用金鑰登入並關掉密碼登入**：

```powershell
# 在 Windows：產生金鑰（一路 Enter，建議設一組 passphrase）
ssh-keygen -t ed25519
# 把公鑰放到 VM
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh 你的使用者名稱@fjcwo.mshome.net "mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys"
```

先**開新視窗確認金鑰登入成功**，再到 VM 編輯 `/etc/ssh/sshd_config.d/99-hardening.conf`，寫入 `PasswordAuthentication no`，然後 `sudo systemctl restart ssh`。

> 若 `fjcwo.mshome.net` 連不上，在 Windows 跑 `Get-VM fjcwo | Get-VMNetworkAdapter | Select IPAddresses` 取得 VM 的 IP 直接用。

### A-5　安裝 PostgreSQL

```bash
sudo apt install -y postgresql
sudo -u postgres psql
```

在 `psql` 裡（密碼 👤 由使用者自己決定，不要貼進對話）：

```sql
CREATE USER fjcwo WITH PASSWORD '換成強密碼';
CREATE DATABASE fjcwo OWNER fjcwo;
\q
```

| 片段 | 用途 |
|------|------|
| `sudo -u postgres psql` | 用系統帳號 `postgres` 進資料庫管理介面 |
| `\q` | 離開 `psql` |

Ubuntu 的 PostgreSQL 預設只聽 localhost，**不要改成對外**，`ufw` 也不要放行 5432。

### A-6　放程式碼與 .env

```bash
sudo apt install -y git python3-venv
sudo adduser --system --group --home /opt/fjcwo fjcwo
sudo -u fjcwo git clone https://github.com/sammy51305/FJCWO-Web.git /opt/fjcwo/app
cd /opt/fjcwo/app
sudo -u fjcwo python3 -m venv venv
sudo -u fjcwo venv/bin/pip install -r requirements.txt
```

| 片段 | 用途 |
|------|------|
| `adduser --system --group --home /opt/fjcwo fjcwo` | 建立一個**不能登入**的專用系統帳號 `fjcwo`，網站用它跑，被入侵時權限最小 |
| `sudo -u fjcwo …` | 用這個帳號執行指令，確保檔案擁有者正確 |
| `python3 -m venv venv` | 建專案專用的 Python 環境（Ubuntu 24.04 內建 Python 3.12，Django 6 支援）|

建立 `/opt/fjcwo/app/.env`（**不進 git**），變數與第 5 節相同：資料庫用 `DB_NAME`、`DB_USER`、`DB_PASSWORD`、`DB_HOST=localhost`、`DB_PORT=5432`（**不要設 `DATABASE_URL`**，原因見第 5 節），再加上 `DJANGO_SECRET_KEY`、`DJANGO_DEBUG=False`、`DJANGO_ALLOWED_HOSTS`、`DJANGO_CSRF_TRUSTED_ORIGINS`、`DJANGO_FIELD_ENCRYPTION_KEY`、Gmail SMTP、`DJANGO_SECURE_SSL_REDIRECT=True`、`DJANGO_SECURE_COOKIES=True`。

```bash
sudo chown fjcwo:fjcwo /opt/fjcwo/app/.env
sudo chmod 600 /opt/fjcwo/app/.env
cd /opt/fjcwo/app
sudo -u fjcwo venv/bin/python manage.py collectstatic --noinput
sudo -u fjcwo venv/bin/python manage.py migrate
```

`chmod 600` ＝ 只有檔案擁有者能讀寫，其他帳號看不到金鑰。
基礎資料（fixtures）、`import_sheet`、`createsuperuser` 同第 5 節，只是指令改成 `sudo -u fjcwo venv/bin/python manage.py …`；`createsuperuser` 的密碼 👤 由使用者自己輸入。

### A-7　Gunicorn 開機服務（systemd）

建立 `/etc/systemd/system/fjcwo.service`：

```ini
[Unit]
Description=FJCWO Web (Gunicorn)
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=fjcwo
Group=fjcwo
WorkingDirectory=/opt/fjcwo/app
ExecStart=/opt/fjcwo/app/venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000 --workers 3
Restart=on-failure
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

| 設定 | 用途 |
|------|------|
| `After`／`Requires=postgresql.service` | 資料庫起來之後才啟動網站 |
| `User=fjcwo` | 用低權限專用帳號跑 |
| `--bind 127.0.0.1:8000` | 只聽本機，外部一律經 Tunnel 進來 |
| `--workers 3` | 工作行程數，小站 2～3 個即可 |
| `Restart=on-failure` | 當掉自動重啟 |
| `NoNewPrivileges`／`PrivateTmp` | 禁止提權、獨立暫存目錄，降低被入侵後的影響 |
| `WantedBy=multi-user.target` | 開機自動啟動 |

> Gunicorn 預設信任來自 127.0.0.1 的 `X-Forwarded-Proto`，cloudflared／Tailscale 都在 VM 內連本機，所以**不需要**像 Waitress 那樣另加 `--trusted-proxy` 參數。

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fjcwo
sudo systemctl status fjcwo
curl -I http://127.0.0.1:8000/
```

`enable --now` ＝ 設為開機自動啟動並立刻啟動。`DJANGO_SECURE_SSL_REDIRECT=True` 下，本機 `curl` 看到 301 轉 https 是正常的；對外連線接好後再用外部網址驗證。
看 log：`sudo journalctl -u fjcwo -f`（`-u` ＝ 指定服務，`-f` ＝ 持續追蹤）。

### A-8　對外連線（在 VM 裡裝）

**不要在 ufw 開 80／443，也不要在路由器 port forward。** 兩種做法擇一，不要兩個都開：

- **Cloudflare Tunnel**：👤 在 Cloudflare Zero Trust 建 Tunnel 時，選作業系統 **Debian／Ubuntu**，照畫面給的指令在 VM 安裝並註冊成服務（指令含一次性 token，不要貼進對話）。Public Hostname 指向 `http://localhost:8000`。
- **Tailscale Funnel**：👤 `curl -fsSL https://tailscale.com/install.sh | sh` 安裝後 `sudo tailscale up` 登入，再依 Tailscale 官方文件啟用 Funnel 指向 8000。

接好後驗證 https 網址回 200 而不是一直 301（同第 8 節）。

### A-9　備份（VM 版）

**VM 內的備份會隨 VM 一起消失，一定要把備份複製到 VM 之外。**

`/usr/local/bin/fjcwo-backup.sh`（`chmod 750`，擁有者 root）：

```bash
#!/usr/bin/env bash
set -o errexit
DEST=/var/backups/fjcwo
mkdir -p "$DEST"
sudo -u postgres pg_dump -Fc fjcwo > "$DEST/fjcwo_$(date +%F).dump"
tar -czf "$DEST/media_$(date +%F).tar.gz" -C /opt/fjcwo/app media 2>/dev/null || true
find "$DEST" -type f -mtime +30 -delete
```

| 片段 | 用途 |
|------|------|
| `set -o errexit` | 任何一步失敗就中止 |
| `pg_dump -Fc` | custom 壓縮格式，可用 `pg_restore` 還原 |
| `tar -czf … media` | 備份使用者上傳的檔案（收據等）；`-c` 建立、`-z` 壓縮、`-f` 檔名、`-C` 先切到該目錄 |
| `find … -mtime +30 -delete` | 刪除超過 30 天的舊備份 |

排程：`sudo systemctl edit --force --full fjcwo-backup.timer` 設每天凌晨執行，或用 `sudo crontab -e` 加一行 `15 3 * * * /usr/local/bin/fjcwo-backup.sh`（每天 03:15）。

**搬出 VM：**
1. 在 Windows 排程用 `scp 使用者@fjcwo.mshome.net:/var/backups/fjcwo/* E:\backup\`，把備份拉到外接硬碟。
2. 同第 9 節，再加密上傳一份到雲端。
3. 另外偶爾 `Export-VM -Name fjcwo -Path E:\vm-export`（匯出整台 VM，需先關機）當整機保險。
4. 每月做還原演練：`sudo -u postgres createdb fjcwo_restore_test` 後 `sudo -u postgres pg_restore -d fjcwo_restore_test 備份檔`，確認後 `dropdb` 刪掉。
5. `.env` 另存密碼管理器，不與備份放一起。

### A-10　與 NAS 隔離的注意事項

- VM 用 **Default Switch（NAT）**，不橋接到區網，**不要**把 Windows 的影片共用資料夾掛進 VM。
- Windows 的 SMB（445 埠）只開給內網或 Tailscale，**絕不 port forward、不經 Tunnel**。
- VM 虛擬硬碟（`.vhdx`）放在 SSD；影片放另一顆 HDD。
- 開 BitLocker 加密存放 `.vhdx` 的磁碟，機器被偷時 VM 內的個資不會外洩。

### A-11　日常維運（VM 版）

```bash
cd /opt/fjcwo/app
sudo -u fjcwo git pull
sudo -u fjcwo venv/bin/pip install -r requirements.txt
sudo -u fjcwo venv/bin/python manage.py migrate
sudo -u fjcwo venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart fjcwo
```

系統更新：`sudo apt update && sudo apt full-upgrade -y`，核心更新後 `sudo reboot`。

| 症狀 | 看哪裡 |
|------|--------|
| 網站打不開 | `sudo journalctl -u fjcwo -n 100`（`-n` ＝ 最後幾行）、`systemctl status fjcwo` |
| 外網連不上、VM 內正常 | `systemctl status cloudflared`（或 `tailscale status`）|
| `relation does not exist` | 跑 `migrate` |
| `ModuleNotFoundError` | 跑 `pip install -r requirements.txt` |
| 重開機後沒起來 | Hyper-V 的自動啟動設定（A-2）、`systemctl status postgresql fjcwo` |
| SSH 連不上 | Windows 上 `Get-VM fjcwo` 看狀態；改用 IP 連（A-4 備註）|

### A-12　上線前檢查清單（VM 版）

- [ ] Hyper-V 已啟用；VM 設為 Windows 開機自動啟動、關機正常關閉、檢查點已停用
- [ ] VM 使用 Default Switch；Windows 的影片共用沒有掛進 VM
- [ ] `ufw` 已啟用，只放行 SSH；SSH 已改金鑰登入、關閉密碼登入
- [ ] PostgreSQL 只聽 localhost；網站用 `fjcwo` 低權限帳號跑；`.env` 權限為 600
- [ ] `DJANGO_DEBUG=False`，`DJANGO_SECRET_KEY` 是新的，`DJANGO_FIELD_ENCRYPTION_KEY` 已另存密碼管理器
- [ ] 重開 Windows 後，VM、PostgreSQL、`fjcwo` 服務與 Tunnel 都自動恢復
- [ ] 對外網址 https 可連，登入、幹部頁、static 正常，Email 寄得出去
- [ ] 每日備份有跑，**已複製到 VM 之外**（外接硬碟＋雲端）
- [ ] **已做過一次還原演練**
