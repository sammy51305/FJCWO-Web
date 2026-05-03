# 開發工作流程與 Commit 前 Checklist

> 本文件定義每次開發的標準流程，以及 git commit 前必須完成的文件確認清單。
> 目標：讓每個 commit 都是乾淨、完整、不需事後 amend 的狀態。

---

## 標準流程

```
開發（寫程式）
    ↓
測試（python manage.py test，確認全部通過）
    ↓
自我 Review（git diff，確認邏輯正確、無安全漏洞）
    ↓
更新文件（依下方 checklist，對照本次變動類型）
    ↓
確認無缺漏（再過一遍 checklist）
    ↓
git commit
    ↓
git push
```

**原則：文件更新必須在 commit 之前完成。不要 commit 後再補文件再 amend。**

---

## Commit 前文件 Checklist

依本次變動類型勾選需要確認的項目。同一次變動可能同時涵蓋多種類型。

---

### 新增或修改 Model

| 確認項目 | 位置 |
|---------|------|
| Model 欄位表格是否反映最新欄位 | `Architecture.md` 第三節對應 Model 段落 |
| 關聯圖是否加入新的 FK 連線（包含方向與 on_delete 類型）| `DESIGN.md` 三、關聯圖 |
| ForeignKey on_delete 表格是否有新的使用案例 | `DESIGN.md` 三、ForeignKey 刪除行為 |
| 對應系統的設計說明（4.x 節）是否更新 | `DESIGN.md` 四、各系統運作邏輯 |
| 是否有新的設計選擇需要備忘（避免日後被誤當 bug）| `DESIGN.md` 附錄三、設計選擇備忘 |
| 是否有新的資料完整性問題（clean() 未涵蓋、無 DB constraint）| `DESIGN.md` 附錄四、待評估項目 |

---

### 新增或修改 View / URL

| 確認項目 | 位置 |
|---------|------|
| 頁面是否出現在頁面與權限結構圖中（幹部 / 團員 / 公開）| `Architecture.md` 四、頁面與權限結構 |
| 對應系統的設計說明（4.x 節）是否更新或新增 | `DESIGN.md` 四、各系統運作邏輯 |

---

### 新增 Fixture

| 確認項目 | 位置 |
|---------|------|
| 專案目錄結構 `fixtures/` 區塊是否列出新檔案 | `Architecture.md` 六、專案目錄結構 |
| 步驟六「載入基礎資料」是否加入 `loaddata` 指令與說明 | `SETUP.md` 步驟六 |

---

### 新增或修改 Test

| 確認項目 | 位置 |
|---------|------|
| 全站測試總數是否更新 | `TESTING.md` 目前測試總覽（標題與第一行）|
| 對應 app 的測試數量是否更新 | `TESTING.md` 對應 app 段落 |
| 新增的 Test class 是否加入說明表格 | `TESTING.md` 對應 app 段落 |
| 「尚未覆蓋」表格是否移除已補上的項目、或新增已知缺口 | `TESTING.md` 尚未覆蓋的功能 |

---

### 新增開發階段功能（Phase 推進）

| 確認項目 | 位置 |
|---------|------|
| 系統清單對應項目是否標記 ✅ | `Architecture.md` 二、系統清單 |
| Phase 開發階段清單是否勾選 | `Architecture.md` 七、開發階段規劃 |

---

## 文件說明（各文件的職責）

| 文件 | 記錄什麼 | 不記錄什麼 |
|------|---------|-----------|
| `Architecture.md` | 系統清單、Model 欄位、頁面權限、目錄結構、開發階段 | 設計邏輯、實作細節 |
| `DESIGN.md` | 關聯圖、每個系統的運作邏輯與設計決策 | 欄位清單（在 Architecture）|
| `TESTING.md` | 測試總數、各 class 說明、執行方式、未覆蓋功能 | 測試的具體程式碼 |
| `SETUP.md` | 從零建環境的步驟（含 fixtures 載入順序）| 架構設計 |
| `AUDIT.md` | 已修正的邏輯問題、確認無誤的疑似問題、設計選擇備忘、待評估項目 | 正常功能的設計說明 |
