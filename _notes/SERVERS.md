# 伺服器機器紀錄

> 用途：記錄**每一台**曾用來當 server 的機器的規格、授權、決定與現況。
> 部署步驟本身（與機器無關）在 [DEPLOY-WINDOWS.md](DEPLOY-WINDOWS.md)；換機時新增一節即可，舊的保留當歷史。
> 機密（密碼、金鑰、序號）**不寫在這裡**。

## 目錄

1. [現役：ASUS Z170-E 桌機（2026-11 起）](#現役asus-z170-e-桌機2026-11-起)
2. [已退役：ASUS ZenBook UX533FD（2026-11-10，未部署即由桌機取代）](#已退役asus-zenbook-ux533fd2026-11-10未部署即由桌機取代)

---

## 現役：ASUS Z170-E 桌機（2026-11 起）

### 規格（2026-11-10 實測）

| 項目 | 結果 |
|------|------|
| 主機板 | ASUS Z170-E（組裝桌機，電腦名稱 `DESKTOP-HM3J980`）|
| CPU | Intel Core i7-6700（第 6 代，**不在 Windows 11 官方支援清單**）|
| RAM | 約 32 GB |
| 硬碟 | Crucial MX500 500 GB SATA SSD，GPT（UEFI 開機）|
| TPM | `Get-Tpm`：`TpmPresent=False`；BIOS 找不到可開的韌體 TPM（2026-11-10）。無 TPM ＝ BitLocker 無法開機自動解鎖 |
| Secure Boot | `Confirm-SecureBootUEFI`：`True`（2026-11-10 於 BIOS 開啟）|
| 結論 | 效能足以跑 PostgreSQL ＋ 本網站；無法正規升級 Windows 11 |

### 系統與授權

| 項目 | 結果 |
|------|------|
| 系統 | Windows 10 專業版 22H2（19045）|
| 授權 | `RETAIL` 零售版，已啟用 |
| 網域管理 | `AzureAdJoined=NO`、`DomainJoined=NO`（沒有被組織管理）|
| 支援 | Windows 10 一般支援 2025-10 結束，消費者 ESU 至 2026-10 也已結束：**系統不再有安全性更新** |

### 已定案的決定

- **留在 Windows 10 專業版**，走 DEPLOY-WINDOWS.md 第 3～9 節（Windows 原生），不重灌、不用 VM、不以繞過檢查的方式裝 Windows 11。
- 因系統無安全性更新，補強：不開任何對外 port（只走 Tunnel／Funnel）、PostgreSQL 只聽 localhost、Defender 保持開啟、瀏覽器與其他軟體不在這台日常使用；長期仍應換到有支援的系統（Ubuntu 或支援 Win11 的硬體）。
- 2026-11-10：取代 ZenBook 成為正式站；**專用 server，不是日常開發機**。正式站程式碼照 DEPLOY 放 `C:\FJCWO-Web`。
- **不開 BitLocker**（無 TPM；不用開機密碼，以免停電／更新後卡在解鎖畫面、網站無法自動恢復）。DEPLOY 第 11 節「BitLocker 已開」為**有意接受的例外**。補強：Windows 強密碼＋自動鎖定、備份檔一律加密後才存（外接硬碟與雲端皆同）、`.env` 另存密碼管理器。之後可加裝實體 TPM 模組再開。
- 異地備份：**Google Drive**（加密後上傳）。
- 對外連線：**Tailscale Funnel**（免費、免網域；2026-11-10 由 Cloudflare Tunnel 改定）。日後想要自訂網址再換 Tunnel，只需改 `.env` 網域設定。Tailscale 同時當遠端維護通道。
- 本地備份：**USB 外接硬碟**（常插不拔）。

### 待使用者回答

| # | 問題 | 影響 |
|---|------|------|
| 1 | 是否接「系統寫入紀錄」到試算表？ | DEPLOY 第 10 節，上線穩定後再決定 |

### 部署進度

| 步驟 | 狀態 |
|------|------|
| 硬體預檢 | ✅ 完成（Secure Boot 已開；無 TPM → 不開 BitLocker）|
| 第 0 步 系統設定 | 🟡 進行中：BIOS Restore AC Power Loss＝Power On ✅、插電永不睡眠／休眠 ✅（2026-11-10）；路由器（UniFi UDM Pro）固定 IP ⬜（目前 DHCP 拿到 `192.168.10.21`）；Windows Update 使用時間：系統已無每月更新、Defender 定義檔更新不需重開機，**略過**（Windows Update 保持開啟，不要停用）|
| 本地備份碟 | ✅ 2026-11-10 接上 TOSHIBA 4 TB USB（`D:`，標籤 `EXTERNAL_USB`，NTFS，已有其他資料、剩約 1.2 TB）|
| Email（Gmail SMTP）| ✅ 2026-11-10 23:14 換成 16 碼應用程式密碼並重啟服務，SMTP 登入測試通過。原問題：❌ 2026-11-10 核准入團申請時寄信失敗（`Connection unexpectedly closed`）。網路與 STARTTLS 正常，**在 login 階段被 Gmail 斷線**；`.env` 的 `EMAIL_HOST_PASSWORD` 長度 13，不是 16 碼應用程式密碼 → 待重新產生並填入 |
| Tailscale 安裝登入（第 5 步前置，兼遠端維護）| ✅ 2026-11-10：v1.104.5、機器名 `fjcwo`、Run unattended ✅、key expiry 已停用 ✅。對外網址將是 `https://fjcwo.tail064d2b.ts.net`；HTTPS 憑證與 Funnel 尚未開（第 5 步）|
| 第 1 步 PostgreSQL | 🟡 2026-11-10 已裝 17（服務 `postgresql-x64-17`，自動啟動）；`listen_addresses` 已改 `localhost`（實測只聽 127.0.0.1／::1）✅；`fjcwo` 資料庫與帳號已建 ✅ |
| 第 2～4 步 程式碼、`.env`、試跑、NSSM 服務 | 🟡 2026-11-10：Python 3.13（machine scope）、clone 到 `C:\FJCWO-Web`、venv＋套件、`.env`（金鑰新產生、直接寫檔）、collectstatic ✅；`.env` 機密已填、金鑰重產 ✅；migrate、三個 fixtures、git hook ✅；Waitress 試跑首頁／登入頁／static 皆 200 ✅。`check --deploy` 剩 W004（HSTS，同測試站）與 W008/W012/W016（SSL／cookie 旗標，Funnel 接好後改 True 即消失）。createsuperuser ✅。NSSM 2.24（winget，machine scope）服務 `FJCWO-Web` ✅：LocalSystem、自動啟動、相依 `postgresql-x64-17`、log `C:\FJCWO-Web\logs\web.log`（服務啟動時輪替；`AppRotateOnline` 已關，見第 5 步）；實測只聽 127.0.0.1:8000、首頁／登入／static 皆 200。重開機驗證 ✅（2026-11-10 22:41 開機，17 秒後網站已服務；PostgreSQL、Tailscale 亦自動恢復）。待：`.env` 存密碼管理器（👤）|
| 第 5 步 對外連線 | ✅ 2026-11-10 Funnel 已開（`tailscale funnel --bg 8000`，HTTPS 憑證與 Funnel policy 已同意）；本機經 tailnet 連 `https://fjcwo.tail064d2b.ts.net` 首頁／登入／static 200。`.env` 兩個 SECURE 旗標改 True 並重啟 ✅：外部 https 200、本機 http 301、cookie 帶 Secure（Funnel 有送 X-Forwarded-Proto）；手機行動網路登入實測（SECURE 旗標生效後）✅。重啟時 NSSM 卡 Stop Pending → 強制結束後關掉 `AppRotateOnline`（設 0）|
| 試算表資料匯入（`import_sheet`）| 🟡 2026-11-10 第一輪 `--commit` 完成：入團申請 32、演出 1、排練 13、出席 2、團費期別 1、收支 8（重跑試跑 0 新增，冪等確認）。待：幹部在「入團申請審核」核准（會寄臨時密碼信）→ 再跑一次補出席／請假／團費 → 刪除 `C:\FJCWO-Import`（含個資的 .xlsx 與報告）|
| 第 6 步 備份與還原演練 | ✅ 2026-11-10：`scripts/backup.py` 寫好；`.env` 加了 `BACKUP_ENCRYPTION_KEY`（直接寫檔，👤 待存密碼管理器）；手動跑 backup → `D:\FJCWO-Backup`、verify（39 個資料表可讀）、offsite → `G:\我的雲端硬碟\FJCWO-Backup` 皆 OK。PR #34 merge 後 `C:\FJCWO-Web` 已 pull ✅；排程 `FJCWO-Backup-Offsite`（danzon、登入時才執行；每日 04:00＋登入後 3 分鐘）已建並試跑 OK ✅。排程 `FJCWO-Backup-Daily`（SYSTEM、每日 03:15）已建，試跑 23:33:57 產生備份 ✅。還原演練 ✅（2026-11-10：`fjcwo_20261110_233356.fjbk` 解密 → pg_restore 到 `fjcwo_restore_test`，39 個資料表共 369 筆與正式庫逐表一致，測試庫已刪）。下次演練：2026-12 |

---

## 已退役：ASUS ZenBook UX533FD（2026-11-10，未部署即由桌機取代）

> 2026-11-10 決定改用上方的 Z170-E 桌機當正式站；這台只做過硬體預檢，未重灌、未部署。以下保留當歷史。

### 規格（2026-11-07 實測）

| 項目 | 結果 |
|------|------|
| 機型 | ASUS ZenBook UX533FD |
| CPU | Intel Core i7-8565U（第 8 代，Windows 11 支援）|
| RAM | 約 16 GB |
| 硬碟 | 約 1.86 TB SATA SSD，GPT（UEFI 開機）|
| TPM | 2.0，可使用 |
| Secure Boot | True |
| 結論 | 符合 Windows 11 條件，效能足以跑 PostgreSQL ＋ 本網站 |

### 系統與授權

| 項目 | 結果 |
|------|------|
| 原有系統 | Windows 10 企業版 22H2 |
| 授權 | `VOLUME_KMSCLIENT`、狀態「通知」、錯誤 `0xC004F00F`：屬某組織的批次授權，已失效未啟用 |
| 支援 | Windows 10 一般支援已於 2025-10 結束 |
| 網域管理 | `AzureAdJoined=NO`、`DomainJoined=NO`（沒有被組織管理）|
| 機器內容 | 空的，沒有資料要保留 |
| 決定 | 重灌 **Windows 11 專業版**（RDP 被連端與完整 BitLocker 需要專業版），用使用者自己合法持有的授權；建立本機帳號。不使用任何啟用工具或破解 |

### 已定案的決定

- 遠端維護：**Tailscale ＋ 內建遠端桌面（RDP）**；不裝 AnyDesk／TeamViewer。
- 這台是 2018 年的筆電，電池老舊：若底部鼓起或觸控板被頂起，就拆掉電池再插電使用（拆掉後停電會直接斷線，備份更要確實）。

### 待使用者回答（Claude 開始前一次問完）

| # | 問題 | 影響 |
|---|------|------|
| 1 | 有沒有 Windows 11 專業版序號？（沒有 → 先未啟用使用，之後補買）| 重灌的序號欄 |
| 2 | 對外連線：Cloudflare Tunnel（需網域）還是 Tailscale Funnel（免網域）？有網域的話是哪個？ | DEPLOY 第 8 節、`.env` 網域 |
| 3 | 異地備份放哪：Cloudflare R2 還是 Google Drive？外接硬碟是否已備妥？ | DEPLOY 第 9 節 |
| 4 | 是否接「系統寫入紀錄」到試算表？ | DEPLOY 第 10 節 |

### 部署進度

| 步驟 | 狀態 |
|------|------|
| 硬體預檢 | ✅ 完成 |
| 重灌 Windows 11 專業版 | ⬜ 未做 |
| 其餘（PostgreSQL、程式碼、服務、對外連線、備份）| ⬜ 未做，照 DEPLOY-WINDOWS.md |

> 進度有變就更新這張表；機器退役時把標題改成「已退役（日期，原因）」。
