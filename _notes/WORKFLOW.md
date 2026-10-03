# 開發工作流程、協作與 Commit 前 Checklist

> 本文件定義三件事：**單人開發的標準流程**、**多人協作（branch / PR / 審核）規則**、
> 以及 **git commit 前必須完成的文件確認清單**。
> 目標：每個 commit 乾淨完整、每次合併都經過把關、`main` 永遠跑得起來。

---

## 目錄

1. [開始前](#開始前)
2. [標準流程](#標準流程)
3. [Commit Message 規範](#commit-message-規範)
4. [標記慣例（P / S / Phase）](#標記慣例p--s--phase)
5. [協作與 Branch 流程](#協作與-branch-流程)
6. [測試策略](#測試策略)
7. [Commit 前 Checklist](#commit-前-checklist)
8. [協作注意事項（容易踩的雷）](#協作注意事項容易踩的雷)
9. [各文件的職責](#各文件的職責)

---

## 開始前

動手寫程式之前，先確認這次變動會影響哪些 checklist 項目，避免開發完才發現遺漏：

- 這次會動到 Model 嗎？→ 需要 migration + 更新 Architecture/DESIGN
- 這次會新增 View / URL 嗎？→ 需要更新頁面權限結構 + DESIGN 設計說明
- 這次需要新增測試嗎？→ 幾乎每次都需要，提前想好要測什麼
- 這次功能是否夠大，適合開 feature branch？→ 見下方「協作與 Branch 流程」

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
git push（feature branch → PR → merge；擁有者瑣事可直接 push main）
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

## 標記慣例（P / S / Phase）

專案裡有三個容易混淆的概念，**各自用不同符號，不可混用**：

| 概念 | 標記 | 範圍 | 記在哪 | 例子 |
|------|:---:|------|--------|------|
| **優先權** | `P0`–`P2` | 待辦之間「先做哪個」 | [DESIGN.md](DESIGN.md) 附錄四、五 | `— P0` |
| **實作階段** | `S1`–`S4` | 單一功能內部的施工順序 | [DESIGN.md](DESIGN.md) 該功能該節 | `S1–S4 已完成` |
| **開發階段** | `Phase 1`–`4` | 整個專案的大階段 | [Architecture.md](Architecture.md) 七 | `Phase 3` |

**為什麼這樣分**：`P` 保留給優先權，因為 `P0/P1/P2` 是業界通用寫法，一看就懂；
功能內的階段改用 `S`（Stage）避開；專案級的 `Phase` 一律寫全字不縮寫，
同時形成層級直覺——**寫全字的 `Phase` 最大，縮寫的 `S` 是功能內部的小階段**。

> 2026-08-12 訂定此慣例。DESIGN.md #9（會費系統重構）原本寫 `P1–P4`，已一併改為 `S1–S4`。

### 優先權 P0 / P1 / P2

待辦與構想中的功能一律標優先權，決定先做哪個。`P0` 最高、`P2` 最低。

| 標記 | 意義 | 判斷基準 |
|:---:|------|---------|
| **P0** | 擋上線的 | 不做就無法上線、或會卡住其他人的工作 |
| **P1** | 上線後要補的 | 上線可以先不做，但缺了會讓使用體驗或流程不完整 |
| **P2** | 有空再說的 | 明確有需求，但沒做也不影響現有運作 |

**標記方式**：直接寫在項目標題結尾，例如 `### 8. 補請假 — P1 待與幹部討論`。
待辦項目本身記在 [DESIGN.md](DESIGN.md) 附錄五（構想中功能）與附錄四（待評估的資料完整性問題）。

### 實作階段 S1 / S2 / …

單一功能大到需要分批施工時才用（要動 Model、要搬遷既有資料、或一次做完無法測），
**每個階段必須獨立可測、可單獨 commit**。範例見 [DESIGN.md](DESIGN.md) 附錄五 #9：
會費系統重構因為要把自由文字欄位換成 FK 又不能弄丟舊資料，拆成 S1–S4 分四批做。

沒有分批必要的功能就不要標階段，直接做完即可。

---

## 協作與 Branch 流程

> 多人協作（2026-10-04 起）的完整規則。單人小改動也沿用同一套流程，只是擁有者有 bypass 捷徑。

### 核心規則（先記這三條）

1. **一個功能開一條 `Feature/<簡短描述>` 分支**，不在 `main` 上直接開發。
2. 分支完成 → 開 **GitHub Pull Request** → 經**審核通過** → 才 merge 進 `main`。
3. **`main` 永遠保持「跑得起來、測試全過」的乾淨狀態。**

**誰適用：**

| 角色 | 規則 |
|------|------|
| 協作者 | **所有變動**都走 branch + PR，不直接 push `main`（main 的 branch protection 會擋）|
| 專案擁有者（目前 `sammy51305`）| 功能一樣走 branch + PR；純瑣事（文件小修、單行 fix）可透過 branch protection 的 **bypass list** 直接 push `main` |

> ⚠️ 擁有者用 bypass 直推時，下方的「機敏檔 CI 檢查」對該次 **不生效**，只剩本機 `pre-commit` hook 擋。所以擁有者直推 main 前務必已啟用本機 hook（見「第一次設定」）。

### 第一次設定（新協作者）

1. 向擁有者取得 repo 協作權限（GitHub 會寄邀請）。
2. Clone：`git clone https://github.com/sammy51305/FJCWO-Web.git`
3. 建開發環境：照 [SETUP.md](SETUP.md) 步驟一～九走完。
4. **啟用 git hook（必做，防機敏檔外洩）：**
   ```bash
   git config core.hooksPath .githooks
   ```
   這會讓 `.githooks/pre-commit` 在每次 commit 時掃描檔案，命中機敏清單就中止 commit（細節見「協作注意事項」）。**沒設定就沒有這道保護**。
5. 設定 git 身分：
   ```bash
   git config user.name "你的名字"
   git config user.email "你的 GitHub email"
   ```
6. 確認機敏檔不會進 git：`.gitignore` 已排除 `.env`、`venv/`、`db.sqlite3`、`media/`、`*.csv`、`*.xlsx` 等，**不要用 `git add -f` 硬加這些**。

### 分支規則

**命名：** `Feature/<簡短描述>`，描述用小寫、連字號分隔，一看就知道在做什麼。

| 用途 | 命名 | 範例 |
|------|------|------|
| 新功能 | `Feature/<描述>` | `Feature/meeting-minutes`、`Feature/guest-member` |
| 修 bug（需要開分支時）| `Fix/<描述>` | `Fix/leave-report-count` |

**一定從最新的 main 開分支：**
```bash
git checkout main
git pull
git checkout -b Feature/xxxxx
```

**原則：**
- 一條分支只做一件事——範圍越小越好審、越不容易衝突。
- 分支要**短命**：盡快做完就 merge，不要長期並行。放越久跟 main 差越多，最後合併越痛。
- 分支活著期間若 main 有更新，定期把 main 併進你的分支（見下方「衝突處理」）。
- 在分支上開發，完全沿用上方「標準流程」，不另設一套。

### 開 Pull Request

1. 推分支到遠端：`git push -u origin Feature/xxxxx`
2. 到 GitHub 開 PR：**base = `main`**，compare = 你的分支。
3. PR 說明會**自動帶出範本**（`.github/pull_request_template.md`），照欄位填即可：
   - **做了什麼、為什麼**
   - 影響的 app / Model / 頁面、有無 migration
   - **測試結果**（哪些 app 測試通過；動到多個 app 或 Model 時附全站測試結果）
   - 有沒有要特別注意的（資料遷移、權限邊界、相依關係）
4. 指定 reviewer（目前為擁有者）。

**PR 前自檢清單：**
- [ ] 該 app 測試全過（動到多個 app 或 Model 時跑全站 `manage.py test`）
- [ ] 文件已更新（照下方「Commit 前 Checklist」逐項確認）
- [ ] `git diff` 自我 review 過，無殘留 debug 輸出、註解掉的程式、多餘檔案
- [ ] 沒把 `venv` / `.env` / `db.sqlite3` / 匯出的 csv·xlsx 等機敏或產物 commit 進去
- [ ] 一個 PR 只包含一件事，沒夾帶無關改動

### 審核與 merge

**Reviewer 重點看（對照 CLAUDE.md 重要慣例）：**
- 權限雙層：`@login_required` + `if not request.user.is_officer`
- N+1 防護：跨 FK 查詢有無 `select_related` / `prefetch_related`
- 測試有沒有跟著新增、是否通過
- 文件有沒有更新到位
- 資安：新的 role / 權限邊界、機敏資料流向有無漏洞

**流程：**
- 審核通過才 merge。有意見就在 PR 上留 comment，作者改完 push（同分支會自動更新 PR），再請求複審。
- **Merge 方式預設用 GitHub 的「Create a merge commit」**（保留分支歷史）；若分支內 commit 很雜，可改用「Squash and merge」收斂成一筆。
- Merge 後收尾：
  ```bash
  # GitHub 上按 Delete branch 刪遠端分支，然後本地：
  git checkout main
  git pull
  git branch -d Feature/xxxxx    # 刪本地分支
  ```

### main 的 branch protection 與機敏檔防線（server 端）

上述規則由 GitHub 強制，不靠自律。擁有者在 **Settings → Rules → Rulesets** 對 `main` 設（Enforcement = Active、Target = `main`）：

- ☑ **Require a pull request before merging** → **Required approvals: 1**
  ＋ Dismiss stale approvals、Require conversation resolution
- ☑ **Require status checks to pass** → 加入「機敏檔檢查」
- ☑ **Block force pushes**、☑ **Restrict deletions**
- **Bypass list**：加入擁有者（Always）→ 保留擁有者瑣事直推 main（代價見「核心規則」⚠️）

**機敏檔防線是兩步：**
1. **CI 檢查（`.github/workflows/secret-file-guard.yml`）**：PR 觸發，掃描合併後的檔案樹是否含 `.env`、`*.csv`、`*.xlsx`、`db.sqlite3`、憑證金鑰、`private/` 等，命中就讓 check 失敗（紅叉）。
2. **Branch protection 綁定**：「Require status checks to pass」把紅叉接到 merge 按鈕——檢查沒過就 merge 不了。

> 這兩步跟本機 `.githooks/pre-commit` 是同一組 pattern：本機 hook 快速回饋、CI 無法被 `--no-verify` 或「忘了設 hook」繞過。改機敏檔清單時，`.githooks/pre-commit` 與 `secret-file-guard.yml` 兩邊要同步更新。
>
> **首次設定順序**：先把 Action 檔 push → 開一個 PR 讓它跑過一次 → 回設定頁 Require status checks → Add checks 搜「機敏檔檢查」加入 → Save。（check 要先回報過一次才搜得到。）

### 衝突處理

把衝突壓到最小的兩個習慣：

1. **開分支前先 `git pull`**——永遠從最新的 main 開。
2. **分支活著期間，main 有進展就把 main 併進分支：**
   ```bash
   git checkout main
   git pull
   git checkout Feature/xxxxx
   git merge main           # 解完衝突後，把該 app 測試再跑一次
   ```

這樣處理，最後 PR merge 回 main 時幾乎不會再有衝突。

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

## 協作注意事項（容易踩的雷）

- **協作者不要直接 push main**——一律經 PR。
- **不要 force push 到共用分支**（main，或別人正在看的分支）；force push 只用在自己尚未開 PR 的私有分支。
- `.env`、`venv`、`db.sqlite3`、匯出的 csv·xlsx 一律不進 git。兩道防線：`.gitignore`（一般情況）＋ `.githooks/pre-commit`（連 `git add -f` 也擋）。後者需先 `git config core.hooksPath .githooks` 啟用，**別繞過**。若規則誤判某個該進版控的檔案，改 `.githooks/pre-commit` 的清單，不要停用整個 hook。
- **migration**：pull 後若遇 `relation does not exist` 或欄位不存在 → 跑 `migrate`；**不要手改已經 commit 的 migration 檔**（見 SETUP.md 情境 F）。
- 不要在一個 PR 裡混多個不相關功能——審核困難、出事難回溯。
- commit / PR 描述用中文，scope 用 app 名，跟現有慣例一致。

---

## 各文件的職責

各文件記錄什麼、不記錄什麼，見 `GUIDE.md`（文件職責索引的唯一來源），此處不重複維護。
