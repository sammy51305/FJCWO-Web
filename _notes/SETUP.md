# 開發環境建置指南

本文件讓你（或 Claude）在新機器上從零重建開發環境。

---

## 系統需求

| 軟體 | 版本 | 用途 |
|------|------|------|
| Python | 3.12 | 執行 Django |
| PostgreSQL | 16 | 資料庫 |
| Git | 任意 | 版本控制 |

---

## 步驟一：Clone 專案

```bash
git clone <repo-url> FJCWO-Web
cd FJCWO-Web
```

---

## 步驟二：建立虛擬環境

```bash
python -m venv venv
```

啟動（Windows）：
```bash
venv\Scripts\activate
```

啟動（macOS / Linux）：
```bash
source venv/bin/activate
```

安裝套件：
```bash
pip install -r requirements.txt
```

---

## 步驟三：建立 PostgreSQL 資料庫與使用者

以 postgres 超級使用者身份執行（Windows 路徑範例）：

```bash
"C:\Program Files\PostgreSQL\16\bin\psql.exe" -U postgres
```

在 psql 裡執行：

```sql
CREATE USER fjcwo_user WITH PASSWORD 'fjcwo';
CREATE DATABASE fjcwo OWNER fjcwo_user;
ALTER USER fjcwo_user CREATEDB;   -- 讓 fjcwo_user 可建測試 DB
\q
```

> `CREATEDB` 權限只為了讓 `manage.py test` 能自動建立測試資料庫。

---

## 步驟四：建立 .env

在專案根目錄建立 `.env`（此檔案不進 git）：

```
DJANGO_SECRET_KEY=django-insecure-)fcwve=n7xb1cg26twc!(#wlz2xv0z#)4bl6hh91%61mzdigp6
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost 127.0.0.1

DB_NAME=fjcwo
DB_USER=fjcwo_user
DB_PASSWORD=fjcwo
DB_HOST=127.0.0.1
DB_PORT=5432
```

> 正式部署時請換掉 `DJANGO_SECRET_KEY` 並將 `DJANGO_DEBUG` 設為 `False`。

---

## 選用：設定 LINE Bot 通知

`.env` 的 `LINE_CHANNEL_ACCESS_TOKEN` 與 `LINE_GROUP_ID` 兩個變數本機開發**可以留空**：
[apps/notifications/utils.py](../apps/notifications/utils.py) 在缺少任一值時會直接跳過推播並記 log，不會噴錯（見 [DESIGN.md](DESIGN.md) §4.18 silent fail 設計）。

若需要實際測試推播效果，才需要申請以下兩個值：

1. **取得 `LINE_CHANNEL_ACCESS_TOKEN`**
   - 前往 [LINE Developers Console](https://developers.line.biz/) 登入
   - 建立一個 Provider（若尚未有）
   - 在該 Provider 下建立一個 **Messaging API** channel
   - 進入該 channel 設定頁的「Messaging API」分頁，簽發 **Channel access token（long-lived）**

2. **取得 `LINE_GROUP_ID`**
   - 用該 channel 的 QR Code 把 Bot 加為好友，並邀請進目標 LINE 群組
   - LINE 沒有介面可直接查詢群組 ID，需暫時架一個 webhook 端點（如 [ngrok](https://ngrok.com/) 轉發），在該 channel 設定 webhook URL 並開啟
   - 在群組裡發一則訊息，觸發 webhook，從收到的 payload 裡讀出 `events[0].source.groupId`
   - 取得後可關閉 webhook，設定值本身長期有效

3. 把兩個值填入 `.env`：
   ```
   LINE_CHANNEL_ACCESS_TOKEN=<你的 token>
   LINE_GROUP_ID=<你的群組 ID>
   ```

> **注意**：這兩個值屬於機密資訊，只存在本機 `.env`（不進 git），不要寫進任何 `_notes/` 文件或 commit 訊息。

---

## 選用：設定寄信（Email）

幹部核准校友報到申請、或手動新增團員時，系統會寄送帳號與臨時密碼給本人。
`.env` 的 `EMAIL_HOST_USER` / `EMAIL_HOST_PASSWORD` **本機開發可以留空**：
[config/settings.py](../config/settings.py) 偵測到沒填時會自動改用 console backend，
信件內容直接印在終端機，不需要申請真的 SMTP 帳號。

若要在本機實際測試寄信效果，才需要申請 SMTP 帳密（例如 Gmail 應用程式密碼），填入：

```
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=<你的 email>
EMAIL_HOST_PASSWORD=<應用程式密碼，不是登入密碼>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=noreply@fjcwo.local
```

> 同樣屬於機密資訊，只存在本機 `.env`，不要寫進任何 `_notes/` 文件或 commit 訊息。

---

## 選用：機密值怎麼在多台電腦間攜帶

`.env` 不進 git，所以換一台電腦開發，`LINE_CHANNEL_ACCESS_TOKEN`、`LINE_GROUP_ID`、
`EMAIL_HOST_USER`、`EMAIL_HOST_PASSWORD` 這些值都要重新設定。多數情況下**不需要真的去煩惱這件事**：

- 平常開發不需要真憑證。兩者的邏輯正確性已經有自動化測試覆蓋（`apps/notifications/tests.py`
  用假 token 測試 LINE 推播；Django 測試框架會自動把 email 攔截到記憶體，不會真的寄送），
  `python manage.py test` 在任何一台電腦上都能驗證邏輯，不需要真憑證。
- 真的需要真憑證的情境，只有你想親眼驗證「LINE 真的推播到手機」「Email 真的收到信」這種
  端到端測試，而這種驗證做過一次確認沒問題後，不需要每次換電腦都重做。

如果你就是想要能隨時在任何電腦上做端到端驗證，或考慮到未來系統交接給下一屆幹部，
建議把這幾個值存進密碼管理工具（例如 [Bitwarden](https://bitwarden.com/)，免費版即可），
存一份「FJCWO .env 機密值」的安全筆記，換電腦時複製貼上到新的 `.env` 即可。
比起機密值只存在單一個人的電腦裡，密碼管理工具更容易交接、也更不會因為換人換電腦就遺失。

---

## 步驟五：執行 Migration

```bash
python manage.py migrate
```

---

## 步驟六：載入基礎資料（Fixtures）

```bash
python manage.py loaddata fixtures/instruments.json
python manage.py loaddata fixtures/sections.json
python manage.py loaddata fixtures/venues.json
```

內含：
- `instruments.json`：12 個樂器族群（豎笛、薩克斯風、長笛等）+ 24 種樂器（Eb 豎笛、Bb 豎笛、中音薩克斯風等）
- `sections.json`：5 個聲部（第一部〜第四部、Solo）
- `venues.json`：排練場地世韻藝術有限公司（含 3 個時段）、演出場地輔仁大學野聲堂等 4 處

> `instruments.json` 和 `sections.json` 必須在 `score_parts_manage` 分譜上傳功能使用前載入，否則 UI 不會有任何樂器可選。

---

## 步驟七：建立 Superuser

```bash
python manage.py createsuperuser
```

建議使用：
- Username: `admin`
- Email: `fujencwo@gmail.com`
- Password: 自訂（本機開發用 `Fjcwo@2026`）

---

## 步驟八：啟動開發伺服器

```bash
python manage.py runserver
```

開啟瀏覽器：
- 前台：`http://127.0.0.1:8000/`
- 後台：`http://127.0.0.1:8000/admin/`

---

## 步驟九：執行測試

```bash
python manage.py test
```

預期輸出：所有測試通過，最後顯示 `OK`。

測試覆蓋範圍、執行選項、新增測試的慣例，詳見 [TESTING.md](TESTING.md)。

---

## 常見問題

**`permission denied to create database`**
→ `fjcwo_user` 缺少 `CREATEDB`，執行：
```sql
ALTER USER fjcwo_user CREATEDB;
```

**`FATAL: password authentication failed`**
→ `.env` 裡的 `DB_PASSWORD` 與 PostgreSQL 設定不符，確認兩邊一致。

**`ModuleNotFoundError: No module named 'django'`**
→ 虛擬環境未啟動，先跑 `venv\Scripts\activate`。

**`django.db.utils.OperationalError: could not connect to server`**
→ PostgreSQL 服務未啟動。Windows 可在「服務」裡啟動 `postgresql-x64-16`。
