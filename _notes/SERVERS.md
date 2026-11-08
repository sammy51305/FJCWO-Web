# 伺服器機器紀錄

> 用途：記錄**每一台**曾用來當 server 的機器的規格、授權、決定與現況。
> 部署步驟本身（與機器無關）在 [DEPLOY-WINDOWS.md](DEPLOY-WINDOWS.md)；換機時新增一節即可，舊的保留當歷史。
> 機密（密碼、金鑰、序號）**不寫在這裡**。

## 目錄

1. [現役：ASUS ZenBook UX533FD（2026-11 起）](#現役asus-zenbook-ux533fd2026-11-起)

---

## 現役：ASUS ZenBook UX533FD（2026-11 起）

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
