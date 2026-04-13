# 邏輯審計紀錄

本文件記錄對系統邏輯設計的審計結果，供日後維護參考。

> 最後審計：2026-04-14（涵蓋 accounts / events / assets / finance / scores）

---

## 審計範圍

對以下所有 views.py 和 models.py 進行人工邏輯審查：

- `apps/accounts/`
- `apps/events/`
- `apps/assets/`
- `apps/finance/`
- `apps/scores/`

審查重點：存取控制、狀態轉換邏輯、型別一致性、查詢邊界、重複操作防護。

---

## 已修正的問題（2026-04-14）

### 1. Open Redirect — `accounts/views.py`

**問題：** `login_view` 直接 `redirect(request.GET.get('next', '/'))` 沒有驗證 URL，
攻擊者可以構造 `?next=https://evil.com` 讓使用者登入後被導到外部網站。

**修正：** 改用 Django 內建的 `url_has_allowed_host_and_scheme()` 驗證：

```python
next_url = request.GET.get('next', '/')
if not url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
    next_url = '/'
return redirect(next_url)
```

---

### 2. 請假審核缺少 PENDING 守衛 — `events/views.py`

**問題：** `leave_review_list` 收到 POST 後直接覆寫 `leave.status`，沒有先確認狀態是否仍為
PENDING。若幹部對已核准的申請重複送出（例如瀏覽器上一頁），可能把 REJECTED 翻為 APPROVED
並建立重複出席紀錄。

對比 `registration_review()` 有正確的 `if reg.status == PENDING:` 守衛，此處漏掉了。

**修正：** 在處理 action 前先檢查狀態：

```python
if leave.status != LeaveRequest.Status.PENDING:
    messages.error(request, '此申請已審核，無法重複操作。')
    return redirect('events:leave_review_list')
```

---

### 3. Setlist 可重複加入同一首曲目 — `events/views.py`

**問題：** `setlist_manage` 新增曲目時只擋重複「演出順序號碼」，未擋重複「曲目」。
同一首曲子可以用不同順序號碼被加入兩次。

**修正：** 額外加一道曲目重複檢查：

```python
elif Setlist.objects.filter(event=event, score_id=score_id).exists():
    messages.error(request, '此曲目已在曲目單中。')
```

---

### 4. `leave_stats` 使用硬字串比對 status — `events/views.py`

**問題：** `defaultdict` 的 key 和 `sum(1 for l if l.status == 'approved')` 直接用
硬字串，與 `LeaveRequest.Status.APPROVED` 等 TextChoices 常數脫鉤。
目前值恰好一致，但 Status 值若未來異動會靜默出錯。

**修正：** 改用 `S = LeaveRequest.Status` 後統一用 `S.PENDING / S.APPROVED / S.REJECTED`。

---

## 審計後確認無問題的項目

| 疑似問題 | 實際情況 |
|---------|---------|
| `member_directory` instrument=None 會 500 | 已有 `if member.instrument else '未分類'` 守衛 |
| `rehearsal.date` 與 `timezone.now()` 型別不符 | `date` 是 `DateTimeField`，比較正確 |
| `finance/views.py` 空期別時 `periods[0]` IndexError | `if not selected_period and periods:` 空 queryset 為 falsy |
| `setlist_manage` order 傳字串給 IntegerField | Django ORM 自動轉型，正常運作 |
| `leave_stats` 字串比對邏輯 | TextChoices 值本身是小寫字串，與硬字串一致 |
| QR 簽到任何人都可以簽 | 刻意設計：有 token URL 才能進入，不需角色限制 |

---

## 已知的設計選擇（非 bug，但值得記錄）

- **`leave_stats` 按事件篩選**：只顯示有申請記錄的團員，沒有申請過的人不出現在列表中。這是刻意的設計（避免空資料行）。
- **出席報表包含 ADMIN role**：`attendance_report` 的 members query 排除 `role=ADMIN`，幹部本身（OFFICER）仍包含在內，這是正確的。
- **`borrow_status_report` 逾期判斷**：`due_date < today`（不含當天），即到期當天不算逾期，符合一般直覺。

---

## 建議的後續審計項目

以下問題屬於 Model 層資料完整性，目前沒有 view 層會觸發，暫不修改，但可考慮加入 Model 的 `clean()` 或 migration constraint：

| 位置 | 問題描述 |
|------|---------|
| `AssetBorrow` | 無限制 `returned_at >= borrowed_at`，可建立時序不合理的記錄 |
| `MembershipFee` | `amount` 無正數驗證，可存入 0 或負數 |
| `FinanceRecord` | `amount` 無正數驗證 |
| `Score` | `parent_score` self-FK 無防循環參照機制 |
| `PartAssignment` | member / guest_member 互斥驗證只在 `clean()`，ORM 直接建立可繞過 |
