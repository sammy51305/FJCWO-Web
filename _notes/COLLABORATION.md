# 協作指南（多人開發流程）

> 對象：加入 FJCWO-Web 的協作者。
> 本檔說明「**一個功能一條 branch、透過 GitHub PR 審核後才 merge**」的協作規則。
> 開發本身的細節（測試、文件、commit message）仍以 [WORKFLOW.md](WORKFLOW.md) 為準，
> 本檔只補「多人協作」這一層，不重複 WORKFLOW 的內容。

---

## 目錄

1. [核心規則（先記這三條）](#一核心規則先記這三條)
2. [第一次設定](#二第一次設定)
3. [分支規則](#三分支規則)
4. [在分支上開發](#四在分支上開發)
5. [開 Pull Request](#五開-pull-request)
6. [審核與 merge](#六審核與-merge)
7. [衝突處理](#七衝突處理)
8. [注意事項（容易踩的雷）](#八注意事項容易踩的雷)

---

## 一、核心規則（先記這三條）

1. **一個功能開一條 `Feature/<簡短描述>` 分支**，不在 main 上直接開發。
2. 分支完成 → 開 **GitHub Pull Request** → 經**審核通過** → 才 merge 進 main。
3. **main 永遠保持「跑得起來、測試全過」的乾淨狀態。**

**誰適用：**

| 角色 | 規則 |
|------|------|
| 協作者 | **所有變動**都走 branch + PR，不直接 push main（main 的 branch protection 會擋）|
| 專案擁有者（目前 `sammy51305`）| 功能一樣走 branch + PR；純瑣事（文件小修、單行 fix）可透過 branch protection 的 **bypass list** 直接 push main |

> ⚠️ 擁有者被 bypass 時，下方的「機敏檔 CI 檢查」對該次直推 **不生效**，只剩本機 `pre-commit` hook 擋。所以擁有者直推 main 前務必已啟用本機 hook（第二節）。

---

## 二、第一次設定

1. 向擁有者取得 repo 協作權限（GitHub 會寄邀請）。
2. Clone：
   ```bash
   git clone https://github.com/sammy51305/FJCWO-Web.git
   ```
3. 建開發環境：照 [SETUP.md](SETUP.md) 步驟一～九走完。
4. **啟用 git hook（必做，防機敏檔外洩）：**
   ```bash
   git config core.hooksPath .githooks
   ```
   這會讓 `.githooks/pre-commit` 在每次 commit 時掃描檔案，命中機敏清單就中止 commit（細節見[第八節](#八注意事項容易踩的雷)）。**沒設定就沒有這道保護**。
5. 設定 git 身分（讓 commit 掛到正確的人）：
   ```bash
   git config user.name "你的名字"
   git config user.email "你的 GitHub email"
   ```
6. 確認機敏檔不會進 git：`.gitignore` 已排除 `.env`、`venv/`、`db.sqlite3`、`media/`、`*.csv`、`*.xlsx` 等，**不要用 `git add -f` 硬加這些**。

---

## 三、分支規則

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
- 分支活著期間若 main 有更新，定期把 main 併進你的分支（見[第七節](#七衝突處理)）。

---

## 四、在分支上開發

完全沿用 [WORKFLOW.md](WORKFLOW.md) 的標準流程，不另設一套：

```
開發 → 同步寫測試 → 跑該 app 測試 → git diff 自我 review → 更新文件 → commit
```

幾個跟協作特別相關的提醒：
- **文件必須在 commit 之前更新完**（CLAUDE.md / WORKFLOW.md 的鐵則，不事後 amend）。
- commit message 格式 `type(scope): 中文說明`，完整規範見 [WORKFLOW.md](WORKFLOW.md)。
- 改了 Model，**migration 檔要跟程式碼同一批 commit**，不可漏（別人 pull 後要靠它 `migrate`）。

---

## 五、開 Pull Request

1. 推分支到遠端：
   ```bash
   git push -u origin Feature/xxxxx
   ```
2. 到 GitHub 開 PR：**base = `main`**，compare = 你的分支。
3. PR 說明要讓審核的人不用猜，至少寫：
   - **做了什麼、為什麼**
   - 影響的 app / Model / 頁面
   - **測試結果**（哪些 app 測試通過；動到多個 app 或 Model 時附全站測試結果）
   - 有沒有要特別注意的（資料遷移、權限邊界、相依關係）
4. 指定 reviewer（目前為擁有者）。

**PR 前自檢清單：**

- [ ] 該 app 測試全過（動到多個 app 或 Model 時跑全站 `manage.py test`）
- [ ] 文件已更新（照 WORKFLOW.md「Commit 前 Checklist」逐項確認）
- [ ] `git diff` 自我 review 過，無殘留 debug 輸出、註解掉的程式、多餘檔案
- [ ] 沒把 `venv` / `.env` / `db.sqlite3` / 匯出的 csv·xlsx 等機敏或產物 commit 進去
- [ ] 一個 PR 只包含一件事，沒夾帶無關改動

---

## 六、審核與 merge

**Reviewer 重點看（對照 CLAUDE.md 重要慣例）：**
- 權限雙層：`@login_required` + `if not request.user.is_officer`
- N+1 防護：跨 FK 查詢有無 `select_related` / `prefetch_related`
- 測試有沒有跟著新增、是否通過
- 文件有沒有更新到位
- 資安：新的 role / 權限邊界、機敏資料流向有無漏洞

**流程：**
- 審核通過才 merge。有意見就在 PR 上留 comment，作者改完 push（同分支會自動更新 PR），再請求複審。
- **Merge 方式預設用 GitHub 的「Create a merge commit」**（保留分支歷史，與現有 `Merge pull request #15` 的作法一致）；若分支內 commit 很雜，可改用「Squash and merge」收斂成一筆。
- Merge 後收尾：
  ```bash
  # GitHub 上按 Delete branch 刪遠端分支，然後本地：
  git checkout main
  git pull
  git branch -d Feature/xxxxx    # 刪本地分支
  ```

### main 的 branch protection 與機敏檔防線（server 端）

上述規則由 GitHub 強制，不靠自律。擁有者在 **Settings → Branches（或 Rules）** 對 `main` 設：

- ☑ **Require a pull request before merging** → **Required approvals: 1**（互審）
  ＋ Dismiss stale approvals when new commits are pushed、Require conversation resolution before merging
- ☑ **Require status checks to pass** → 加入下方的「機敏檔檢查」
- **Bypass list**：把擁有者加入 → 保留擁有者瑣事直推 main（代價見第一節 ⚠️）

**機敏檔防線是兩步：**
1. **CI 檢查（`.github/workflows/secret-file-guard.yml`）**：PR 觸發，掃描合併後的檔案樹是否含 `.env`、`*.csv`、`*.xlsx`、`db.sqlite3`、憑證金鑰、`private/` 等，命中就讓 check 失敗（紅叉）。
2. **Branch protection 綁定**：上面勾的「Require status checks to pass」把這個紅叉接到 merge 按鈕——檢查沒過就 merge 不了。

> 這兩步跟本機 `.githooks/pre-commit`（第二節）是同一組 pattern：本機 hook 快速回饋、CI 無法被 `--no-verify` 或「忘了設 hook」繞過。改機敏檔清單時，`.githooks/pre-commit` 與 `secret-file-guard.yml` 兩邊要同步更新。
>
> **首次設定順序**：先把 Action 檔 push 上去 → 開一個測試 PR 讓它跑過一次 → 回設定頁 **Require status checks → Add checks** 搜「機敏檔檢查」加入 → Save。（check 要先回報過一次才搜得到。）

---

## 七、衝突處理

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

## 八、注意事項（容易踩的雷）

- **協作者不要直接 push main**——一律經 PR。
- **不要 force push 到共用分支**（main，或別人正在看的分支）；force push 只用在自己尚未開 PR 的私有分支。
- `.env`、`venv`、`db.sqlite3`、匯出的 csv·xlsx 一律不進 git。兩道防線：`.gitignore`（一般情況）＋ `.githooks/pre-commit`（連 `git add -f` 也擋）。後者需先 `git config core.hooksPath .githooks` 啟用（見第二節），**別繞過**。若規則誤判某個該進版控的檔案，改 `.githooks/pre-commit` 的清單，不要停用整個 hook。
- **migration**：pull 後若遇 `relation does not exist` 或欄位不存在 → 跑 `migrate`；**不要手改已經 commit 的 migration 檔**（見 SETUP.md 情境 F）。
- 不要在一個 PR 裡混多個不相關功能——審核困難、出事難回溯。
- commit / PR 描述用中文，scope 用 app 名，跟現有慣例一致。
