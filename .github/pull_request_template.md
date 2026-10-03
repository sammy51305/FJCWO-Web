## 做了什麼 / 為什麼
<!-- 一兩句講清楚這個 PR 解決什麼、為什麼要做 -->


## 影響範圍
- App / Model / 頁面：
- 有無 migration：否 /（是 → 說明改了什麼）


## 測試結果
- [ ] 該 app 測試通過（`manage.py test apps.<app>`）
- [ ] 動到多個 app 或 Model → 全站測試通過（`manage.py test`）


## 特別注意
<!-- 資料遷移、權限邊界、相依關係、需手動操作的步驟；沒有就寫「無」 -->


---
### 送出前自檢
- [ ] 文件已更新（照 `_notes/WORKFLOW.md` Commit 前 Checklist）。常見對照：
  - [ ] 改了 **view 行為／新增 view** → 對應 `DESIGN.md §4.x` 與 `Architecture.md` 頁面權限結構已更新
  - [ ] 改了 **Model** → `Architecture.md` 欄位表、`DESIGN.md` 關聯圖與 §4.x 已更新
  - [ ] 改了 **測試** → `TESTING.md` 測試數與 class 說明已更新
- [ ] `git diff` 自我 review 過，無殘留 debug／註解掉的程式／多餘檔案
- [ ] 沒把 `.env` / `venv` / `db.sqlite3` / csv·xlsx 等機敏檔 commit 進去
- [ ] 這個 PR 只做一件事
