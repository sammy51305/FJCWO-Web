# _notes 文件導覽

開發時不知道要查哪份文件，從這裡找。

---

## 我想知道…

| 我想知道… | 去看這份 |
|----------|---------|
| 系統有哪些功能、操作流程怎麼走 | [OVERVIEW.md](OVERVIEW.md) |
| 某個 Model 有哪些欄位 | [Architecture.md](Architecture.md) 三、資料庫設計 |
| 某個頁面需要什麼權限才能進 | [Architecture.md](Architecture.md) 四、頁面與權限結構 |
| 目前做到哪個 Phase | [Architecture.md](Architecture.md) 七、開發階段規劃 |
| 某個系統的設計邏輯是什麼 | [DESIGN.md](DESIGN.md) 四、各系統運作邏輯 |
| 這段程式「為什麼這樣寫」，是設計選擇還是 bug | [DESIGN.md](DESIGN.md) 附錄三 |
| 有哪些已知的資料完整性問題還沒修 | [DESIGN.md](DESIGN.md) 附錄四 |
| 目前有幾個測試、測了什麼 | [TESTING.md](TESTING.md) |
| 要新增測試，慣例是什麼 | [TESTING.md](TESTING.md) 新增測試的慣例 |
| 第一次建立開發環境 | [SETUP.md](SETUP.md) |
| commit 前要確認哪些文件 | [WORKFLOW.md](WORKFLOW.md) |

---

## 各文件的職責

| 文件 | 記錄什麼 | 不記錄什麼 |
|------|---------|-----------|
| [Architecture.md](Architecture.md) | Model 欄位表、頁面權限、系統清單、目錄結構、Phase 進度 | 設計邏輯、實作細節 |
| [DESIGN.md](DESIGN.md) | FK 關聯圖、各系統設計邏輯與決策、設計選擇備忘、待評估項目 | 欄位清單（在 Architecture）|
| [TESTING.md](TESTING.md) | 測試總數、各 class 說明、執行方式、未覆蓋功能 | 測試的具體程式碼 |
| [SETUP.md](SETUP.md) | 從零建環境的步驟（含 fixtures 載入順序）| 架構設計 |
| [OVERVIEW.md](OVERVIEW.md) | 功能總覽與操作流程（非技術人員版）| 技術實作細節 |
| [WORKFLOW.md](WORKFLOW.md) | 開發標準流程、commit 前 checklist、commit message 規範 | 各文件內部的細節內容 |
