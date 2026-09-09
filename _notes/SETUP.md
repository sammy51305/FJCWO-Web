# 開發環境建置指南

本文件讓你（或 Claude）在新機器上從零重建開發環境。

---

## 目錄

1. [系統需求](#系統需求)
2. [步驟一：Clone 專案](#步驟一clone-專案)
3. [步驟二：建立虛擬環境](#步驟二建立虛擬環境)
4. [步驟三：建立 PostgreSQL 資料庫與使用者](#步驟三建立-postgresql-資料庫與使用者)
5. [步驟四：建立 .env](#步驟四建立-env)
6. [機密設定 SOP（LINE Bot / Email）](#機密設定-sopline-bot--email)
   - [情境 E：Render ＋ Neon 免費測試站](#情境-erender--neon-免費測試站2026-09-07-建置)
   - [情境 F：`git pull` 之後要跑什麼](#情境-fgit-pull-之後要跑什麼)
7. [步驟五：執行 Migration](#步驟五執行-migration)
8. [步驟六：載入基礎資料（Fixtures）](#步驟六載入基礎資料fixtures)
9. [步驟七：建立 Superuser](#步驟七建立-superuser)
10. [步驟八：啟動開發伺服器](#步驟八啟動開發伺服器)
11. [步驟九：執行測試](#步驟九執行測試)
12. [常見問題](#常見問題)

---

## 系統需求

| 軟體 | 版本 | 用途 |
|------|------|------|
| Python | 3.12+（開發機實測 3.14） | 執行 Django |
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

在專案根目錄建立 `.env`（此檔案不進 git）。最快的方式是複製專案內的 `.env.example` 再改，範本已含分區註解與各變數用途；本機開發填入下列值即可：

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

## 機密設定 SOP（LINE Bot / Email）

這一節把所有機敏值的申請、填寫、驗證、換電腦攜帶、正式環境差異集中寫成可照抄的步驟。

### 機密值一覽

`.env` 裡跟機密有關的變數，以及**沒填時的 fallback 行為**：

| 變數 | 用途 | 沒填時的行為 | 對應程式 |
|------|------|------------|---------|
| `LINE_CHANNEL_ACCESS_TOKEN` | LINE Bot 推播 | 跳過推播、記一筆 log，不噴錯 | [utils.py](../apps/notifications/utils.py) |
| `LINE_GROUP_ID` | 推播的目標群組 | 同上（缺任一就跳過）| [utils.py](../apps/notifications/utils.py) |
| `EMAIL_HOST_USER` | SMTP 帳號 | 自動改用 console backend，信印在終端機 | [settings.py](../config/settings.py) |
| `EMAIL_HOST_PASSWORD` | SMTP 密碼 | 同上（缺任一就走 console）| [settings.py](../config/settings.py) |

> 兩組 fallback 的判斷都是「兩個值都要有」才啟用真功能，缺一即退回安全預設。
> LINE 的 silent fail 設計見 [DESIGN.md](DESIGN.md) §4.18；Email backend 切換邏輯見 [config/settings.py](../config/settings.py) `EMAIL_BACKEND` 那段。

**先判斷你屬於哪個情境，再往下看對應段落：**

- **情境 A — 平常本機開發**：什麼都不用設定，直接跳到步驟五。
- **情境 B — 想在本機親眼驗證真的推播 / 真的收到信**：看下方 B。
- **情境 C — 換一台電腦繼續開發**：看下方 C。
- **情境 D — 建立正式（production）環境**：看下方 D。

---

### 情境 A：本機開發（預設，免設定）

不需要任何真憑證。邏輯正確性已被自動化測試覆蓋（`apps/notifications/tests.py` 用假 token 測 LINE 推播；Django 測試會把 email 攔到記憶體），`python manage.py test` 在任何電腦上都能驗證，不必申請真帳號。直接進行步驟五即可。

---

### 情境 B：本機端到端測試（真的推播 / 真的寄信）

只有當你想親眼確認「LINE 真的跳到手機」「Email 真的寄到信箱」時才需要做。

#### B-1　申請 LINE Bot 憑證

1. **取得 `LINE_CHANNEL_ACCESS_TOKEN`**
   - 前往 [LINE Developers Console](https://developers.line.biz/) 登入
   - 建立一個 Provider（若尚未有）
   - 在該 Provider 下建立一個 **Messaging API** channel
   - 進入該 channel 設定頁的「Messaging API」分頁，簽發 **Channel access token（long-lived）**

2. **取得 `LINE_GROUP_ID`**
   - 用該 channel 的 QR Code 把 Bot 加為好友，並邀請進目標 LINE 群組
   - LINE 沒有介面可直接查群組 ID，需暫時架一個 webhook 端點（如 [ngrok](https://ngrok.com/) 轉發），在該 channel 設定 webhook URL 並開啟
   - 在群組裡發一則訊息觸發 webhook，從 payload 讀出 `events[0].source.groupId`
   - 取得後可關閉 webhook，設定值本身長期有效

3. **填入 `.env`**：
   ```
   LINE_CHANNEL_ACCESS_TOKEN=<你的 token>
   LINE_GROUP_ID=<你的群組 ID>
   ```

4. **驗證**（重啟 runserver 後執行，會實際推一則測試訊息）：
   ```bash
   venv\Scripts\python.exe manage.py shell -c "from apps.notifications.utils import push_line_message; push_line_message('FJCWO 測試訊息')"
   ```
   手機收到訊息＝成功；若跳過或失敗，log 會印 `LINE notification skipped/failed`，代表值沒填對。

#### B-2　申請 Email SMTP 憑證（以 Gmail 為例）

1. **產生 Gmail 應用程式密碼**（不是你的登入密碼）
   - Gmail 帳號需先開啟「兩步驟驗證」，否則沒有應用程式密碼選項
   - 前往 Google 帳號 →「安全性」→「應用程式密碼」，產生一組 16 碼密碼
   - 這 16 碼就是 `EMAIL_HOST_PASSWORD`

2. **填入 `.env`**：
   ```
   EMAIL_HOST=smtp.gmail.com
   EMAIL_PORT=587
   EMAIL_HOST_USER=<你的 Gmail 位址>
   EMAIL_HOST_PASSWORD=<16 碼應用程式密碼，去掉空格>
   EMAIL_USE_TLS=True
   DEFAULT_FROM_EMAIL=noreply@fjcwo.local
   ```
   > `EMAIL_USE_TLS` 的判斷是字串比對 `== 'True'`（大小寫敏感），必須寫 `True`，寫 `true` 或 `1` 都會被當成關閉 TLS。

3. **驗證**（重啟 runserver 後執行）：
   ```bash
   venv\Scripts\python.exe manage.py shell -c "from django.conf import settings; print(settings.EMAIL_BACKEND)"
   ```
   顯示 `...smtp.EmailBackend` 代表已切到真寄信（顯示 `console.EmailBackend` 代表 USER/PASSWORD 至少一個沒填成功）。接著實際寄一封：
   ```bash
   venv\Scripts\python.exe manage.py sendtestemail 你的收件信箱@example.com
   ```

> **注意**：B-1、B-2 的所有值都屬機密，只存在本機 `.env`（不進 git），不要寫進任何 `_notes/` 文件或 commit 訊息。

---

### 情境 C：換一台電腦繼續開發

`.env` 不進 git，換電腦時 `LINE_CHANNEL_ACCESS_TOKEN`、`LINE_GROUP_ID`、`EMAIL_HOST_USER`、`EMAIL_HOST_PASSWORD` 都會不見。**多數情況不用煩惱**：平常開發（情境 A）不需要真憑證，`python manage.py test` 照樣能跑。

只有你想「在新電腦上也能隨時做端到端驗證」或「未來交接給下一屆幹部」時，才需要攜帶這些值。做法：

1. 在密碼管理工具（推薦 [Bitwarden](https://bitwarden.com/)，免費版即可）建立一則安全筆記，命名如「FJCWO .env 機密值」。
2. 把上述 4 個變數連同值貼進去（建議連整段 `.env` 一起存，換電腦最省事）。
3. 新電腦完成步驟四建立 `.env` 後，從安全筆記複製貼上，覆蓋對應變數即可。

> 比起只存在單一個人電腦裡，密碼管理工具更容易交接，也不會因換人換電腦而遺失。

---

### 情境 F：`git pull` 之後要跑什麼

拉了別人（或自己在另一台）推的新程式碼後，**程式碼更新了但你的環境沒有**，
兩種東西可能落後：

| 症狀 | 原因 | 解法 |
|------|------|------|
| `ModuleNotFoundError: No module named 'xxx'` | `requirements.txt` 加了新套件 | `pip install -r requirements.txt` |
| `relation "xxx" does not exist`、欄位不存在 | 有新的 migration 沒套用 | `python manage.py migrate` |

保險起見，**每次 pull 完順手跑這兩行**（已裝的套件會跳過、已套用的 migration 不會重跑，很快）：

```bash
venv\Scripts\python.exe -m pip install -r requirements.txt
venv\Scripts\python.exe manage.py migrate
```

> **不需要跑 `makemigrations`**——遷移檔是跟著程式碼進 repo 的，`pull` 就拿到了。
> 在自己機器上 `makemigrations` 只會在「你改了 model」時才該做；沒改卻跑出新檔案，
> 通常代表你的分支跟別人的 model 有分歧，要先確認而不是直接產生。

---

### 情境 D：建立正式（production）環境

正式環境與本機開發的差別，**主要是 `.env` 的填法**。

> 想先用免費方案架一個給幹部試用的測試站 → 看 **情境 E**（Render ＋ Neon），那裡有完整步驟。
> 本情境談的是正式環境該注意什麼，兩者的檢查清單可以互相對照。

#### D-1　`.env` 與本機的差異

| 變數 | 本機開發 | 正式環境 |
|------|---------|---------|
| `DJANGO_SECRET_KEY` | 沿用範例值即可 | **必須換成新的隨機值**，且只放正式機的 `.env` |
| `DJANGO_DEBUG` | `True` | **`False`**（否則錯誤頁會外洩程式碼與設定）|
| `DJANGO_ALLOWED_HOSTS` | `localhost 127.0.0.1` | 填正式網域，如 `fjcwo.example.com`（多個以空格分隔）|
| `EMAIL_HOST_USER` / `PASSWORD` | 可留空走 console | **必須填真憑證**，否則系統寄不出帳號密碼信 |
| `LINE_CHANNEL_ACCESS_TOKEN` / `GROUP_ID` | 可留空 | 要通知就填真值 |
| 資料庫 `DB_*` | 本機 PostgreSQL | 正式機的資料庫連線資訊 |

產生新的 `DJANGO_SECRET_KEY`：
```bash
venv\Scripts\python.exe -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

#### D-2　上線前檢查（每次部署都對一遍）

- [ ] `DJANGO_DEBUG=False`
- [ ] `DJANGO_SECRET_KEY` 已換成新值，且沒有出現在 git 或任何文件裡
- [ ] `DJANGO_ALLOWED_HOSTS` 已填正式網域
- [ ] Email 真憑證已填、`sendtestemail` 實測寄得出去
- [ ] 已跑 `python manage.py migrate`（正式資料庫）
- [ ] 已載入步驟六的三個 fixtures（否則分譜上傳無樂器可選）
- [ ] `python manage.py collectstatic`（正式環境需自行提供靜態檔）
- [ ] 資料庫已排定備份機制
- [ ] `python manage.py check --deploy` 無重大警告

> 正式環境的所有機密值同樣只放正式機 `.env`，不進 git、不寫進 `_notes/`、不放 commit 訊息。

### 情境 E：Render ＋ Neon 免費測試站（2026-09-07 建置）

給幹部連線試用的測試站，全程免費、不需要信用卡。對應 DESIGN 附錄五 #10 的**路線 A**。
路線 B（家機自架）要重灌機器，兩者不衝突——測試站先跑 A，之後要搬 B 再說。

**分工**：Render 跑網站（免費方案）、Neon 存資料庫（永久免費）。
不用 Render 自家的免費 Postgres——它 30 天會過期，資料整包不見。

#### E-1　repo 裡已經準備好的東西

| 檔案 | 作用 |
|------|------|
| `render.yaml` | Render Blueprint，一次建好服務與環境變數骨架 |
| `build.sh` | 每次部署跑的建置指令（安裝套件 → collectstatic → migrate）|
| `.python-version` | 釘住 Python 3.13.1（Django 6 需要 3.12 以上）|
| `requirements.txt` | 已含 `gunicorn`／`whitenoise`／`dj-database-url` |

`config/settings.py` 也已就緒：設了 `DATABASE_URL` 就走雲端資料庫、沒設就用本機的 `DB_*`；
static 由 WhiteNoise 供應；強制 https 與 secure cookie 由環境變數開關（預設關，不影響本機與測試）。

#### E-2　建立 Neon 資料庫（約 3 分鐘）

1. 到 [neon.tech](https://neon.tech) 用 GitHub 帳號註冊。
2. 建 project，region 選 **Singapore** 或 **Tokyo**（離台灣最近）。
3. 複製 **Connection string**，長得像
   `postgresql://user:pass@ep-xxx.ap-southeast-1.aws.neon.tech/neondb?sslmode=require`。
   **這串是機密**，等一下貼進 Render，不要寫進 git 或任何文件。

#### E-3　建立 Render 服務（約 5 分鐘）

1. 到 [render.com](https://render.com) 用 GitHub 帳號註冊、授權讀取 `FJCWO-Web`。
2. **New → Blueprint** → 選這個 repo，Render 會讀 `render.yaml` 自動帶出設定。
3. 建立時它會問幾個 `sync: false` 的變數，照下表填：

| 變數 | 填什麼 |
|------|--------|
| `DATABASE_URL` | E-2 複製的 Neon 連線字串 |
| `DJANGO_ALLOWED_HOSTS` | Render 給的網域，**不含** `https://`，例如 `fjcwo-web.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | 同一個網域，**要含** `https://`，例如 `https://fjcwo-web.onrender.com` |
| `DEMO_PASSWORD` | 自己想一組，**不可以用 `demo1234`**（那組寫在 DEMO.md 裡等於公開）|
| `DJANGO_ROBOTS_NOINDEX` | `True` —— 測試站不讓搜尋引擎收錄（見下方 E-7）|
| `DJANGO_FIELD_ENCRYPTION_KEY` | 任意隨機字串（Blueprint 會自動產生）。敏感個資的加密金鑰，**設定後不要再改**——換掉會讓既有密文解不開 |

> 網域要等第一次部署後才知道。可以先隨便填、部署完再回設定頁改成正確的，改完會自動重新部署。
> 填錯的症狀很好認：`ALLOWED_HOSTS` 不對 → 整站 400；`CSRF_TRUSTED_ORIGINS` 不對 → 頁面打得開但一送出表單就 403。

#### E-4　灌基礎資料與 demo 資料

部署成功後，在 Render 該服務的 **Shell** 分頁執行（`migrate` 已由 `build.sh` 跑過）：

```bash
python manage.py loaddata fixtures/instruments.json fixtures/sections.json fixtures/venues.json
python manage.py seed_demo          # demo 密碼自動吃 DEMO_PASSWORD 環境變數
python manage.py createsuperuser    # 自己的管理員帳號
```

**測試站一律用假資料**，不要匯入真團員個資（DESIGN #10「共通事項」已定）。

#### E-5　免費方案的三個限制（測試可接受，正式上線前要解）

1. **會休眠**：15 分鐘沒人用就睡著，下一個請求要等約 1 分鐘喚醒。第一次點會覺得很慢，是正常的。
2. **磁碟是暫時的**：**重新部署會清空上傳的檔案**——樂譜 PDF、分譜、收據會不見（QR 圖可重新產生）。
   測試階段接受即可；要持久保存得接 Cloudflare R2 之類的物件儲存（見 DESIGN #10 路線 A 的「媒體」）。
3. **Email 仍是 console backend**：沒填 `EMAIL_HOST_USER`／`PASSWORD` 的話，
   系統寄的臨時密碼信只會印在 Render 的 log 裡、收件人收不到。
   要測「校友報到 → 收密碼信」整條流程（#11）就得填真的 SMTP。

#### E-7　不讓搜尋引擎收錄測試站

測試站網址是公開的，可能被搜尋引擎爬到。設 `DJANGO_ROBOTS_NOINDEX=True` 會同時做兩件事：

| 機制 | 擋什麼 |
|------|--------|
| `/robots.txt` 回 `Disallow: /` | 擋「爬取」——守規矩的爬蟲不會來抓內容 |
| 每個回應加 `X-Robots-Tag: noindex, nofollow` | 擋「收錄」——即使有人把網址貼在別處被爬到，也不會進搜尋結果 |

兩個都要，因為 **robots.txt 只擋爬取、不擋收錄**：搜尋引擎若從別的網頁發現這個網址，
仍可能把網址本身列進結果（只是不顯示內容）。

**正式站不要設這個變數**（或設 `False`）。那時 `/robots.txt` 會改成只擋內部路徑
（`/admin/`、`/accounts/`、`/events/`、`/scores/`、`/assets/`、`/finance/`），
公開頁（首頁、關於百韻、組織章程、公開公告）仍可被搜尋到——那對樂團是好事。

> 這是刻意做成環境變數而非寫死：同一份程式碼會同時部署到測試站與正式站，
> 寫死「全站禁止」會讓正式站的公開頁也搜尋不到。

#### E-8　接真的 SMTP（Gmail 應用程式密碼）

測試站預設是 console backend——信只印在 Render 的 log 裡，收件人收不到。
**#11 校友批次匯入靠「核准 → 寄臨時密碼信」收尾，那條流程沒有真 SMTP 就是斷的**，
所以這是 #10「上線前必須處理的兩件事」的第 2 點。

**用哪個帳號**：建議樂團公用帳號而非個人帳號——校友看到的寄件人是樂團，日後交接也不用重設。

**產生應用程式密碼**（不是帳號登入密碼）：

1. 該 Google 帳號必須先開啟**兩步驟驗證**，否則沒有這個選項
2. 到 <https://myaccount.google.com/apppasswords>（或：安全性 → 兩步驟驗證 → 最下方「應用程式密碼」）
3. 取名如 `FJCWO-Web` → 建立 → 得到 16 碼密碼
4. **視窗關掉就再也看不到**，馬上複製；填進 Render 時把空格拿掉

**Render 環境變數**：

| 變數 | 值 |
|------|-----|
| `EMAIL_HOST` | `smtp.gmail.com`（Blueprint 已填）|
| `EMAIL_PORT` | `587`（已填）|
| `EMAIL_USE_TLS` | `True`（已填，**大小寫敏感**）|
| `EMAIL_HOST_USER` | 該 Gmail 完整位址 |
| `EMAIL_HOST_PASSWORD` | 上面那 16 碼應用程式密碼 |
| `DEFAULT_FROM_EMAIL` | 如 `輔仁百韻管樂團 <fujencwo@gmail.com>` |

> **`DEFAULT_FROM_EMAIL` 的信箱必須與 `EMAIL_HOST_USER` 相同**，否則 Gmail 會把寄件人
> 改寫成驗證過的那個位址（或直接被收件端判為偽冒）。預設值 `noreply@fjcwo.local`
> 是本機用的假位址，上線一定要換掉。

`settings.py` 的切換是**四個都要有才生效**：`EMAIL_HOST_USER` 與 `EMAIL_HOST_PASSWORD`
任一為空就退回 console backend。所以「填了一半」的症狀是**安靜地沒寄出去**，不會報錯。

**驗證**（本機連測試站設定，或在 Render Shell）：

```bash
python manage.py sendtestemail 你的信箱@example.com
```

收到就成了。沒收到先看垃圾郵件匣，再看 Render 的 Logs 有沒有 SMTP 錯誤。

> ⚠️ **寄送額度**：一般 Gmail 帳號每日約數百封上限。#11 要一次核准三百位校友時
> 很可能撞到限流，屆時要分批核准（DESIGN #11 風險表已列）。

#### E-6　上線檢查

- [ ] `DJANGO_DEBUG=False`（`render.yaml` 已寫死，確認沒被改掉）
- [ ] `DEMO_PASSWORD` 不是 `demo1234`
- [ ] 網站打得開、能登入、表單送得出去（送不出去看 `CSRF_TRUSTED_ORIGINS`）
- [ ] 沒有匯入任何真實團員個資
- [ ] 幹部拿到的網址是 `https://`（`DJANGO_SECURE_SSL_REDIRECT=True` 會自動轉）
- [ ] `DJANGO_ROBOTS_NOINDEX=True`，且 `https://<網域>/robots.txt` 顯示 `Disallow: /`
- [ ] `DJANGO_FIELD_ENCRYPTION_KEY` 已設（沒設的話 `build.sh` 會直接讓部署失敗）
- [ ] Email 已接真 SMTP，且 `sendtestemail` 實測收得到（見 E-8）

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

### 想要有東西可以點？再灌一份假資料

fixtures 只有主檔（樂器、聲部、場地），載完系統仍是空的——沒有演出、沒有排練、沒有樂譜，
畫面幾乎每一頁都是「目前沒有資料」。要實際操作或看功能長什麼樣，再跑：

```bash
python manage.py seed_demo
```

會建立團員帳號、演出與排練、樂譜、財產、財務會費、公告等一整套展示資料。
**可重複執行、不會產生重複資料**；清除用 `clear_demo`。
資料內容、demo 動線與注意事項見 [DEMO.md](DEMO.md)。

> ⚠️ demo 帳號的預設密碼寫在 DEMO.md 裡（等於公開），**任何連得到外面的環境**
> 都要用 `DEMO_PASSWORD` 環境變數蓋掉，見情境 E。

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
