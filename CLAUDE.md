# FJCWO-Web — Claude 工作指引

## 專案概述

輔仁大學百韻管樂團（FJCWO）內部管理系統。Django 6.x + PostgreSQL + Bootstrap 5。
Phase 2 功能全部完成（含 LINE Bot 群組通知），Phase 3（會議紀錄 AI、演出手冊）尚未開始。

詳細架構、Model 欄位、頁面權限結構 → `_notes/Architecture.md`
各系統設計邏輯、關聯圖 → `_notes/DESIGN.md`

## 開發環境

```bash
venv\Scripts\python.exe manage.py runserver           # 啟動開發伺服器
venv\Scripts\python.exe manage.py migrate             # 套用資料庫遷移（新拉程式碼、或看到 relation does not exist 錯誤時執行）
venv\Scripts\python.exe manage.py makemigrations      # 改了 Model 後產生新的 migration 檔
venv\Scripts\python.exe manage.py test                # 執行全部測試（預期全部通過）
venv\Scripts\python.exe manage.py test apps.scores --verbosity=2  # 單一 app
```

## 開發流程（每次必須依序執行）

```
開發 → 測試通過 → Review（git diff）→ 更新文件 → 確認 checklist → git commit → git push
```

**文件必須在 commit 之前更新完畢，不事後 amend。**

### Commit 前 Checklist

依本次變動類型對照，詳細說明見 `_notes/WORKFLOW.md`：

| 變動類型 | 必須確認的文件段落 |
|---------|-----------------|
| 新增/修改 Model | Architecture.md Model 表格、DESIGN.md 關聯圖、DESIGN.md 4.x 節 |
| 新增/修改 View | Architecture.md 頁面與權限結構、DESIGN.md 4.x 節 |
| 新增 Fixture | Architecture.md fixtures/ 目錄、SETUP.md 步驟六 |
| 新增/修改 Test | TESTING.md 測試總數、app 測試數、class 描述、未覆蓋表格 |
| Phase 功能完成 | Architecture.md 系統清單、開發階段規劃 |

## 重要慣例

- 權限檢查：`@login_required` + `if not request.user.is_officer` 雙層
- N+1 防護：跨 FK 查詢一律加 `select_related` / `prefetch_related`
- 冪等操作：用 `get_or_create`，不用手動判斷 exist
- 測試結構：每個 app 一支 `tests.py`，class 用中文 docstring 說明目的
- Commit message：`type(scope): 中文說明`（type = feat / fix / docs / refactor…，scope = app 名稱；完整規範見 `_notes/WORKFLOW.md`）

## 文件導覽

`_notes/` 下有多份文件，**入口與動線**如下：

```
CLAUDE.md（你在這 — 工作指引）
    → _notes/GUIDE.md      不知道查哪份文件？從這裡找（唯一的文件職責索引）
    → _notes/WORKFLOW.md   開發流程、commit 前 checklist、commit message 規範
```

各文件記錄什麼、該更新哪一份，一律以 `_notes/GUIDE.md` 為準，不在此重複維護。
