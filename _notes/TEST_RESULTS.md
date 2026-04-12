# 測試結果紀錄

執行指令：
```bash
python manage.py test apps.public.tests apps.accounts.tests apps.events.tests --verbosity=2
```

---

## 最新執行結果

| 欄位 | 內容 |
|------|------|
| 執行日期 | 2026-04-12 |
| Django 版本 | 6.0.4 |
| Python 版本 | 3.12.10 |
| 通過 / 總計 | 57 / 57 |
| 結論 | 全部通過 ✓ |

---

## 測試套件總覽

### apps.public — 公開頁面（6 項）

| 測試方法 | 說明 | 結果 |
|----------|------|------|
| `PublicPagesTest.test_index_accessible` | 首頁 200 | PASS |
| `PublicPagesTest.test_index_no_login_required` | 首頁不需登入 | PASS |
| `PublicPagesTest.test_about_accessible` | 關於頁 200 | PASS |
| `PublicPagesTest.test_about_no_login_required` | 關於頁不需登入 | PASS |
| `PublicPagesTest.test_rules_accessible` | 章程頁 200 | PASS |
| `PublicPagesTest.test_rules_no_login_required` | 章程頁不需登入 | PASS |

### apps.accounts — 登入 / 登出 / 個人資料 / 通訊錄（17 項）

| 測試方法 | 說明 | 結果 |
|----------|------|------|
| `LoginLogoutTest.test_login_page_accessible` | 登入頁 200 | PASS |
| `LoginLogoutTest.test_login_page_shows_form` | 登入頁含表單欄位 | PASS |
| `LoginLogoutTest.test_already_authenticated_redirects` | 已登入再訪登入頁導向首頁 | PASS |
| `LoginLogoutTest.test_valid_login_redirects` | 正確帳密登入後導向首頁 | PASS |
| `LoginLogoutTest.test_valid_login_with_next` | 登入後導向 next 參數頁面 | PASS |
| `LoginLogoutTest.test_invalid_login_shows_error` | 錯誤密碼停留在登入頁 | PASS |
| `LoginLogoutTest.test_invalid_login_no_session` | 錯誤密碼不建立 session | PASS |
| `LoginLogoutTest.test_logout_redirects_to_home` | 登出後導向首頁 | PASS |
| `LoginLogoutTest.test_logout_clears_session` | 登出後 session 清除 | PASS |
| `ProfileTest.test_unauthenticated_redirects` | 未登入個人資料導向登入頁 | PASS |
| `ProfileTest.test_authenticated_can_view` | 登入後可看到個人資料頁 | PASS |
| `ProfileTest.test_profile_shows_current_name` | 頁面顯示現有姓名 | PASS |
| `ProfileTest.test_valid_profile_update` | POST 儲存資料並導回個人資料頁 | PASS |
| `MemberDirectoryTest.test_unauthenticated_redirects` | 未登入通訊錄導向登入頁 | PASS |
| `MemberDirectoryTest.test_member_can_view_directory` | 一般 member 可進入通訊錄 | PASS |
| `MemberDirectoryTest.test_member_sees_names` | 所有登入者可看到姓名 | PASS |
| `MemberDirectoryTest.test_member_cannot_see_phone` | 一般 member 看不到電話 | PASS |
| `MemberDirectoryTest.test_officer_can_see_phone` | 幹部可看到電話 | PASS |
| `MemberDirectoryTest.test_officer_can_see_email` | 幹部可看到 email | PASS |
| `MemberDirectoryTest.test_admin_excluded_from_directory` | 管理員不出現在通訊錄 | PASS |

### apps.events — 演出活動 / 排練 / 請假申請（31 項）

| 測試方法 | 說明 | 結果 |
|----------|------|------|
| `EventViewsTest.test_event_list_requires_login` | 未登入活動列表導向登入頁 | PASS |
| `EventViewsTest.test_event_list_accessible` | 登入後可看到活動列表 | PASS |
| `EventViewsTest.test_event_list_shows_upcoming` | 列表顯示即將到來活動 | PASS |
| `EventViewsTest.test_event_list_shows_past` | 列表顯示已結束活動 | PASS |
| `EventViewsTest.test_event_detail_requires_login` | 未登入活動詳情導向登入頁 | PASS |
| `EventViewsTest.test_event_detail_accessible` | 登入後可看到活動詳情 | PASS |
| `EventViewsTest.test_event_detail_shows_name` | 活動詳情顯示活動名稱 | PASS |
| `EventViewsTest.test_event_detail_shows_rehearsals` | 活動詳情顯示排練列表 | PASS |
| `EventViewsTest.test_event_detail_404_on_invalid_pk` | 不存在的活動 pk 回 404 | PASS |
| `EventViewsTest.test_rehearsal_detail_requires_login` | 未登入排練詳情導向登入頁 | PASS |
| `EventViewsTest.test_rehearsal_detail_accessible` | 登入後可看到排練詳情 | PASS |
| `EventViewsTest.test_rehearsal_detail_shows_summary` | 排練詳情顯示摘要內容 | PASS |
| `EventViewsTest.test_rehearsal_detail_shows_notes` | 排練詳情顯示給團員備註 | PASS |
| `EventViewsTest.test_rehearsal_detail_has_leave_button` | 排練詳情含申請請假按鈕 | PASS |
| `EventViewsTest.test_rehearsal_detail_404_on_invalid_pk` | 不存在的排練 pk 回 404 | PASS |
| `LeaveRequestTestCase.test_unauthenticated_redirects_to_login` | 未登入請假申請導向登入頁 | PASS |
| `LeaveRequestTestCase.test_unauthenticated_mine_redirects` | 未登入我的請假導向登入頁 | PASS |
| `LeaveRequestTestCase.test_member_can_view_leave_form` | member 可看到申請表單 | PASS |
| `LeaveRequestTestCase.test_form_shows_rehearsal_info` | 表單顯示排練資訊 | PASS |
| `LeaveRequestTestCase.test_empty_reason_is_rejected` | 空白原因不建立資料 | PASS |
| `LeaveRequestTestCase.test_whitespace_reason_is_rejected` | 純空白原因不建立資料 | PASS |
| `LeaveRequestTestCase.test_valid_leave_request_created` | 正常送出建立 LeaveRequest | PASS |
| `LeaveRequestTestCase.test_duplicate_request_blocked` | 重複申請被擋 | PASS |
| `LeaveRequestTestCase.test_my_leave_requests_shows_own_records` | 我的請假顯示自己的紀錄 | PASS |
| `LeaveRequestTestCase.test_my_leave_requests_empty_state` | 無申請時顯示空狀態 | PASS |
| `LeaveRequestTestCase.test_member_cannot_access_review_page` | member 無法進審核頁 | PASS |
| `LeaveRequestTestCase.test_officer_can_view_review_page` | 幹部可進入審核頁 | PASS |
| `LeaveRequestTestCase.test_review_page_shows_pending_requests` | 審核頁顯示待審核申請 | PASS |
| `LeaveRequestTestCase.test_officer_can_approve` | 幹部核准，狀態變 approved | PASS |
| `LeaveRequestTestCase.test_officer_can_reject` | 幹部拒絕，狀態變 rejected | PASS |
| `LeaveRequestTestCase.test_reviewed_section_shows_after_action` | 已審核區顯示核准/拒絕標籤 | PASS |

---

## 歷史紀錄

| 日期 | 通過 | 總計 | 備註 |
|------|------|------|------|
| 2026-04-12 | 16 | 16 | 初版，僅請假申請 |
| 2026-04-12 | 57 | 57 | 新增 public / accounts / events views 測試 |
