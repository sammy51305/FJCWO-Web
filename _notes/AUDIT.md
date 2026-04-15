# 邏輯審計紀錄

本文件記錄對系統邏輯設計的審計與修正，供日後維護參考。

| 欄位 | 內容 |
|------|------|
| 最後審計 | 2026-04-16 |
| 涵蓋範圍 | accounts / events / assets / finance / scores |
| 審查重點 | 存取控制、狀態轉換、型別一致性、查詢邊界、重複操作防護 |

---

## 一、修正紀錄

### 2026-04-13

| # | 位置 | 問題摘要 |
|---|------|---------|
| 1 | `accounts/models.py` | `is_officer` 未含 superuser |
| 2 | `accounts/models.py` | `is_staff` 未跟 role 同步 |
| 3 | `events/views.py` | `setlist_manage` 未在 server-side 驗證 score_type |
| 4 | `events/views.py` | `leave_request_create` 未在 server-side 阻擋已結束排練 |
| 5 | `events/models.py` | `LeaveRequest` 缺少 `created_at` 欄位 |
| 6 | `events/views.py` | `qr_generate` 初次／重新產生的成功訊息相同 |
| 7 | `scores/models.py` | `Score.clean()` 驗證缺失 |
| 8 | `templates/events/rehearsal_detail.html` | 排練詳情連結只在有摘要時顯示 |

**#1 — `is_officer` 未含 superuser**
`is_officer` 原本只檢查 `role in (OFFICER, ADMIN)`，superuser 被排除。
修正：加入 `or self.is_superuser` 判斷。
（commit `00b95d5`）

**#2 — `is_staff` 未跟 role 同步**
`role=admin` 或 `is_superuser` 的使用者需要 `is_staff=True` 才能進 Django Admin，但 `save()` 未自動同步。
修正：在 `save()` 加入自動設定邏輯。
（commit `3ea90b4`）

**#3 — `setlist_manage` 未驗證 score_type**
前端限制只能選總譜，但 server 端沒有驗證，直接 POST 分譜 pk 可繞過。
修正：改用 `get_object_or_404(Score, pk=score_id, score_type=Score.ScoreType.FULL)`。
（commit `2d41963`）

**#4 — `leave_request_create` 未阻擋已結束排練**
前端會 disable 按鈕，但可透過直接 POST 送出已結束排練的請假。
修正：在 view 加入 `if rehearsal.date <= timezone.now():` 判斷。
（commit `2d41963`）

**#5 — `LeaveRequest` 缺少 `created_at`**
請假申請無法追蹤送出時間。
修正：新增 `created_at = DateTimeField(auto_now_add=True)`（migration 0004）。
（commit `8b8c7c4`）

**#6 — `qr_generate` 成功訊息固定顯示「已產生」**
無論初次或重新產生，訊息皆相同，無法區分操作結果。
修正：依是否已有 token 分別顯示「已產生」或「已重新產生」。
（commit `8b8c7c4`）

**#7 — `Score.clean()` 驗證缺失**
總譜（FULL）不應有樂器/聲部，分譜（PART）必須有樂器，原本無任何驗證。
修正：加入 `clean()` 方法。
（commit `8b8c7c4`）

**#8 — 排練詳情連結只在有摘要時顯示**
若幹部尚未填寫排練摘要，連結消失，使用者無法進入詳情頁。
修正：連結改為永遠顯示，文字依摘要存在與否切換（「排練摘要」／「詳情」）。
（commit `69c5e24`）

---

### 2026-04-14

| # | 位置 | 問題摘要 | 嚴重度 |
|---|------|---------|--------|
| 9 | `accounts/views.py:20` | Open redirect — `next` 參數未驗證 | 中（安全性） |
| 10 | `events/views.py:113` | 請假審核缺少 PENDING 狀態守衛 | 中（邏輯） |
| 11 | `events/views.py:433` | Setlist 可重複加入同一首曲目 | 低（邏輯） |
| 12 | `events/views.py:321` | `leave_stats` 使用硬字串比對 status | 低（維護性） |

**#9 — Open redirect**
`login_view` 直接 `redirect(request.GET.get('next', '/'))` 未驗證 URL，
攻擊者可構造 `?next=https://evil.com` 讓登入後導向外部網站。
修正：改用 `url_has_allowed_host_and_scheme()` 驗證後再 redirect。
（commit `e9242ce`）

**#10 — 請假審核缺少 PENDING 守衛**
`leave_review_list` 收到 POST 後直接覆寫 `leave.status`，未確認狀態是否仍為 PENDING。
若幹部對已核准的申請重複送出（例如瀏覽器上一頁），可能把 REJECTED 翻為 APPROVED 並重建出席紀錄。
對比 `registration_review()` 有正確守衛，此處漏掉了。
修正：處理前加入 `if leave.status != LeaveRequest.Status.PENDING:` 檢查。
（commit `e9242ce`）

**#11 — Setlist 可重複加入同一首曲目**
新增曲目時只擋重複「演出順序號碼」，未擋重複「曲目」，同一首曲子可用不同順序加入兩次。
修正：額外加入 `Setlist.objects.filter(event=event, score_id=score_id).exists()` 檢查。
（commit `e9242ce`）

**#12 — `leave_stats` 使用硬字串比對 status**
`defaultdict` 的 key 與計數邏輯直接使用 `'approved'`、`'pending'`、`'rejected'` 硬字串，
與 `LeaveRequest.Status` TextChoices 常數脫鉤。目前值恰好一致，但 Status 值若異動會靜默出錯。
修正：改用 `S = LeaveRequest.Status`，統一使用 `S.PENDING / S.APPROVED / S.REJECTED`。
（commit `e9242ce`）

---

### 2026-04-16

| # | 位置 | 問題摘要 | 嚴重度 |
|---|------|---------|--------|
| 13 | `events/views.py` | `qr_manage` 硬編碼簽到 URL，應改用 `reverse()` | 低（維護性） |
| 14 | `events/views.py` | 核准請假可蓋掉已 QR 簽到的 PRESENT 出席紀錄 | 中（邏輯） |
| 15 | `events/views.py` | `from collections import defaultdict` 在函式內部 | 低（style） |

**#13 — `qr_manage` 硬編碼 URL**
```python
checkin_url = request.build_absolute_uri(f'/events/checkin/{qr_token.token}/')
```
URL 路徑若異動，QR Code 產生的連結會默默失效且無任何錯誤提示。
修正：改用 `reverse('events:qr_checkin', args=[qr_token.token])`。

**#14 — 核准請假蓋掉 PRESENT 出席紀錄**
`leave_review_list` 核准請假後使用 `get_or_create` + 直接賦值 `status = LEAVE`，
未先判斷是否已有 PRESENT 紀錄（team member 先 QR 簽到、再補交請假，幹部事後核准）。
這種情況下，實際已到場的出席紀錄會被覆寫為請假，導致出席報表失真。
修正：加入 `if attendance.status != RehearsalAttendance.Status.PRESENT:` 判斷，
已簽到者保留 PRESENT，不做覆寫。

**#15 — `defaultdict` import 在函式內部**
`leave_stats` 裡 `from collections import defaultdict` 放在函式 body 內。
修正：移至檔案頂部，與其他 import 統一管理。

---

## 二、確認無問題的項目

審計過程中懷疑但確認正確的項目，避免日後重複誤判。

| 疑似問題 | 確認結果 |
|---------|---------|
| `member_directory` instrument=None 會 500 | 已有 `if member.instrument else '未分類'` 守衛（`views.py:53`） |
| `rehearsal.date` 與 `timezone.now()` 型別不符 | `date` 是 `DateTimeField`，timezone-aware 比較正確 |
| `finance/views.py` 空期別時 `periods[0]` IndexError | `if not selected_period and periods:` 空 queryset 為 falsy，已守衛 |
| `setlist_manage` order 傳字串給 IntegerField | Django ORM 自動轉型，正常運作 |
| QR 簽到任何人都可以簽 | 刻意設計：持有 token URL 才能進入，不需角色限制 |

---

## 三、設計選擇備忘

記錄不直覺但有意為之的設計，避免日後被誤當成 bug 修掉。

- **`leave_stats` 只顯示有申請記錄的團員**：沒有申請過的人不出現，避免空資料行造成誤讀。
- **出席報表包含 OFFICER role**：`attendance_report` 排除 `role=ADMIN`，幹部（OFFICER）仍在列，符合業務需求。
- **`borrow_status_report` 逾期判斷為 `due_date < today`**：到期當天不算逾期，符合一般直覺。

---

## 四、待評估項目（未修正）

以下屬於 Model 層資料完整性問題，目前沒有 view 會主動觸發，暫不修改。
若日後資料出現異常，可優先從這裡找原因，並考慮加入 `clean()` 或 DB constraint。

| 位置 | 問題描述 |
|------|---------|
| `AssetBorrow` | 無限制 `returned_at >= borrowed_at`，可建立時序不合理的記錄 |
| `MembershipFee` | `amount` 無正數驗證，可存入 0 或負數 |
| `FinanceRecord` | `amount` 無正數驗證 |
| `Score` | `parent_score` self-FK 無防循環參照機制 |
| `PartAssignment` | member / guest_member 互斥驗證只在 `clean()`，ORM 直接建立可繞過 |
