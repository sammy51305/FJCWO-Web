# FJCWO-Web

輔仁大學百韻管樂團內部管理系統。取代原本的 Hugo 靜態網站，提供真正的身份驗證與角色權限控制。

## 技術棧

| 項目 | 選擇 |
|------|------|
| 後端 | Django 6.x + PostgreSQL 16 |
| 前端 | Bootstrap 5（無 JS 框架）|
| 部署目標 | Nginx + Gunicorn + Ubuntu Server |
| 通知 | LINE Bot（開發中）|
| AI | OpenAI Whisper + Claude API（Phase 3）|

## 快速開始

環境需求：Python 3.12、PostgreSQL 16。

```bash
# 1. 建立並啟動虛擬環境
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 2. 安裝套件
pip install -r requirements.txt

# 3. 建立 .env（參考 .env.example）
# 4. 建立資料庫並執行 migration
python manage.py migrate

# 5. 載入基礎資料
python manage.py loaddata fixtures/instruments.json
python manage.py loaddata fixtures/sections.json
python manage.py loaddata fixtures/venues.json

# 6. 建立管理員帳號
python manage.py createsuperuser

# 7. 啟動開發伺服器
python manage.py runserver
```

完整的環境建置步驟（PostgreSQL 設定、常見錯誤排除）→ [`_notes/SETUP.md`](_notes/SETUP.md)

## 執行測試

```bash
python manage.py test                          # 全部（312 個）
python manage.py test apps.events              # 單一 app
python manage.py test --verbosity=2            # 詳細輸出
```

## 文件

| 文件 | 說明 |
|------|------|
| [`_notes/GUIDE.md`](_notes/GUIDE.md) | 文件導覽，不知道查哪份文件時從這裡找 |
| [`_notes/Architecture.md`](_notes/Architecture.md) | 技術決策、Model 欄位、頁面權限結構、開發階段規劃 |
| [`_notes/DESIGN.md`](_notes/DESIGN.md) | FK 關聯圖、各系統設計邏輯與決策；附錄含設計選擇備忘與待評估項目 |
| [`_notes/TESTING.md`](_notes/TESTING.md) | 測試覆蓋範圍、執行方式、新增測試的慣例 |
| [`_notes/SETUP.md`](_notes/SETUP.md) | 從零建環境的完整步驟 |
| [`_notes/OVERVIEW.md`](_notes/OVERVIEW.md) | 功能總覽與操作流程（非技術人員版）|
| [`_notes/WORKFLOW.md`](_notes/WORKFLOW.md) | 開發標準流程、commit 前 checklist |

## 開發進度

| Phase | 說明 | 狀態 |
|-------|------|------|
| Phase 1 | Django 基礎、登入、公開頁面 | 完成 |
| Phase 2 | 演出、排練、QR 簽到、請假、樂譜、財務、公告等核心功能 | 完成（LINE Bot 除外）|
| Phase 3 | 會議紀錄 AI 摘要、演出手冊自動生成、手機版 UI | 待開發 |
| Phase 4 | django-tenants 多租戶 SaaS 擴充 | 未來規劃 |

## 開發流程

```
開發 → 測試通過 → Review → 更新文件 → git commit → git push
```

文件必須在 commit 之前更新完畢。Commit 前 checklist → [`_notes/WORKFLOW.md`](_notes/WORKFLOW.md)
