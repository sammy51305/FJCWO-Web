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

## 步驟五：執行 Migration

```bash
python manage.py migrate
```

---

## 步驟六：載入基礎資料（Fixtures）

```bash
python manage.py loaddata fixtures/venues.json
```

內含：
- 排練場地：世韻藝術有限公司（含 3 個時段）
- 演出場地：輔仁大學野聲堂、台北國家音樂廳、台北中山堂、新北市藝文中心演藝廳

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
