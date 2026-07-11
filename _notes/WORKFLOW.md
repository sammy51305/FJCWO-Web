# 開發工作流程與 Commit 前 Checklist

> 本文件定義每次開發的標準流程，以及 git commit 前必須完成的文件確認清單。
> 目標：讓每個 commit 都是乾淨、完整、不需事後 amend 的狀態。

---

## 開始前

動手寫程式之前，先確認這次變動會影響哪些 checklist 項目，避免開發完才發現遺漏：

- 這次會動到 Model 嗎？→ 需要 migration + 更新 Architecture/DESIGN
- 這次會新增 View / URL 嗎？→ 需要更新頁面權限結構 + DESIGN 設計說明
- 這次需要新增測試嗎？→ 幾乎每次都需要，提前想好要測什麼
- 這次功能是否夠大，適合開 feature branch？→ 見下方 Branch 策略

---

## 標準流程

```
確認 checklist 項目（開始前）
    ↓
開發（寫程式）
    ↓
新增對應測試（與功能同一 commit，不要事後補）
    ↓
執行該 app 的測試（確認新功能通過）
    python manage.py test apps.<app_name>
    ↓
自我 Review（git diff，確認邏輯正確、無安全漏洞）
    ↓
更新文件（逐項確認下方 checklist）
    ↓
git commit（訊息格式見下方規範）
    ↓
git push（feature branch → PR → merge；直接開發則 push main）
```

**原則：文件更新必須在 commit 之前完成。不要 commit 後再補文件再 amend。**

---

## Commit Message 規範

格式：`<type>(<scope>): <中文說明>`

| Type | 使用時機 |
|------|---------|
| `feat` | 新增功能（新 view、新 model、新頁面）|
| `fix` | 修正 bug |
| `test` | 新增或修改測試 |
| `docs` | 只更新文件（`_notes/` 內容）|
| `refactor` | 重構，不影響功能 |
| `chore` | 雜務（依賴更新、設定調整）|

**規則：**
- scope 填 app 名稱，如 `feat(events):`、`fix(accounts):`
- 說明用中文，一行說清楚做了什麼
- 同時包含功能 + 測試 + 文件時，用 `feat`（主要類型優先）
- body 可補充說明背景或設計決策，但不需要解釋「改了哪幾行」

```
# 範例
feat(public): 新增關於百韻可編輯區塊功能
test(events): 新增演出活動與排練管理的測試（共 20 個）
docs(workflow): 更新測試策略
fix(accounts): 修正幹部審核後未正確設定 reviewed_at
```

---

## Branch 策略

| 情境 | 做法 |
|------|------|
| 小修改（文件、單一 bug fix）| 直接 commit `main` |
| 單一功能（一個 view + template）| 直接 commit `main` |
| 較大功能（新 Model + 多個 view + 測試 + 文件）| 開 feature branch |
| Phase 內的多功能開發 | 各自 feature branch，完成後 merge |

**Feature branch 命名：** `feat/<簡短描述>`，例如 `feat/about-sections`、`feat/event-manage`

**Merge 時機：** 該功能完整（程式 + 測試 + 文件），且 app 測試全部通過後才 merge。

---

## 測試策略

- 每次新增功能都要同步新增對應測試，隨功能一起 commit
- 開發中只跑該 app 的測試即可，不用每次都跑全站
- 全站測試（`python manage.py test`）在 **Phase 完成時跑一次**，確認沒有跨 app 的 regression

---

## Commit 前 Checklist

**這是強制清單，每一項都要確認完才能 commit。** 依本次變動類型勾選適用的項目。

---

### 新增或修改 Model

- [ ] Model 欄位表格是否反映最新欄位 → `Architecture.md` 第三節
- [ ] 關聯圖是否加入新的 FK 連線（方向與 on_delete）→ `DESIGN.md` 三、關聯圖
- [ ] ForeignKey on_delete 表格是否有新案例 → `DESIGN.md` 三、ForeignKey 刪除行為
- [ ] 對應系統的設計說明（4.x 節）是否更新 → `DESIGN.md` 四、各系統運作邏輯
- [ ] 是否有新的設計選擇需要備忘 → `DESIGN.md` 附錄三
- [ ] 是否有新的資料完整性問題 → `DESIGN.md` 附錄四

---

### 新增或修改 View / URL

- [ ] 頁面是否出現在頁面與權限結構圖中 → `Architecture.md` 四、頁面與權限結構
- [ ] 對應系統的設計說明（4.x 節）是否更新或新增 → `DESIGN.md` 四、各系統運作邏輯

---

### 新增 Fixture

- [ ] `fixtures/` 區塊是否列出新檔案 → `Architecture.md` 六、專案目錄結構
- [ ] 步驟六「載入基礎資料」是否加入 `loaddata` 指令 → `SETUP.md` 步驟六

---

### 新增或修改 Test

- [ ] 對應 app 的測試數量是否更新 → `TESTING.md` 對應 app 段落
- [ ] 新增的 Test class 是否加入說明表格 → `TESTING.md` 對應 app 段落
- [ ] 「尚未覆蓋」表格是否移除已補上的項目 → `TESTING.md` 尚未覆蓋的功能
- [ ] 全站測試總數（Phase 完成後跑全站再更新）→ `TESTING.md` 目前測試總覽

---

### 新增開發階段功能（Phase 推進）

- [ ] 系統清單對應項目是否標記 ✅ → `Architecture.md` 二、系統清單
- [ ] Phase 開發階段清單是否勾選 → `Architecture.md` 七、開發階段規劃

---

## 文件說明（各文件的職責）

| 文件 | 記錄什麼 | 不記錄什麼 |
|------|---------|-----------|
| `Architecture.md` | 系統清單、Model 欄位、頁面權限、目錄結構、開發階段 | 設計邏輯、實作細節 |
| `DESIGN.md` | 關聯圖、每個系統的運作邏輯與設計決策；附錄含確認無問題項目、設計選擇備忘、待評估項目 | 欄位清單（在 Architecture）|
| `TESTING.md` | 測試總數、各 class 說明、執行方式、未覆蓋功能 | 測試的具體程式碼 |
| `SETUP.md` | 從零建環境的步驟（含 fixtures 載入順序）| 架構設計 |
| `GUIDE.md` | 文件導覽，各文件職責對照 | 文件的具體內容 |
| `OVERVIEW.md` | 功能總覽與操作流程（非技術人員版）| 技術實作細節 |
