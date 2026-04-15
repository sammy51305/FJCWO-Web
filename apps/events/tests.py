from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import User
from apps.public.models import Venue
from .models import LeaveRequest, PerformanceEvent, Rehearsal, RehearsalAttendance


class LeaveRequestTestCase(TestCase):
    """請假申請功能整合測試"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='test_member',
            email='member@test.local',
            password='testpass123',
            name='測試團員',
            role=User.Role.MEMBER,
        )
        self.officer = User.objects.create_user(
            username='test_officer',
            email='officer@test.local',
            password='testpass123',
            name='測試幹部',
            role=User.Role.OFFICER,
        )
        self.venue = Venue.objects.create(name='測試場地', type='rehearsal')
        self.event = PerformanceEvent.objects.create(
            name='測試音樂會',
            type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now() + timedelta(days=30),
            performance_venue=self.venue,
        )
        self.rehearsal = Rehearsal.objects.create(
            event=self.event,
            sequence=1,
            date=timezone.now() + timedelta(days=7),
            venue=self.venue,
        )
        self.leave_url = reverse('events:leave_request_create', args=[self.rehearsal.pk])
        self.mine_url = reverse('events:my_leave_requests')
        self.review_url = reverse('events:leave_review_list')

    # ── T01 存取控制 ────────────────────────────────────────

    def test_unauthenticated_redirects_to_login(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.leave_url)
        self.assertRedirects(r, f'/accounts/login/?next={self.leave_url}', fetch_redirect_response=False)

    def test_unauthenticated_mine_redirects(self):
        """未登入存取我的請假應導向登入頁"""
        r = self.client.get(self.mine_url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    # ── T02 申請表單顯示 ─────────────────────────────────────

    def test_member_can_view_leave_form(self):
        """member 可看到申請表單"""
        self.client.force_login(self.member)
        r = self.client.get(self.leave_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '請假原因')

    def test_form_shows_rehearsal_info(self):
        """申請表單顯示排練資訊"""
        self.client.force_login(self.member)
        r = self.client.get(self.leave_url)
        self.assertContains(r, self.event.name)

    # ── T03 送出空白原因 ─────────────────────────────────────

    def test_empty_reason_is_rejected(self):
        """空白原因不建立資料，停留在表單"""
        self.client.force_login(self.member)
        r = self.client.post(self.leave_url, {'reason': ''})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LeaveRequest.objects.count(), 0)

    def test_whitespace_reason_is_rejected(self):
        """純空白原因不建立資料"""
        self.client.force_login(self.member)
        r = self.client.post(self.leave_url, {'reason': '   '})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LeaveRequest.objects.count(), 0)

    # ── T04 正常送出 ─────────────────────────────────────────

    def test_valid_leave_request_created(self):
        """正常送出建立 LeaveRequest，初始狀態為 pending"""
        self.client.force_login(self.member)
        r = self.client.post(self.leave_url, {'reason': '有考試，無法出席'})
        self.assertRedirects(r, self.mine_url, fetch_redirect_response=False)
        self.assertEqual(LeaveRequest.objects.count(), 1)
        leave = LeaveRequest.objects.get()
        self.assertEqual(leave.member, self.member)
        self.assertEqual(leave.rehearsal, self.rehearsal)
        self.assertEqual(leave.reason, '有考試，無法出席')
        self.assertEqual(leave.status, LeaveRequest.Status.PENDING)

    # ── T05 重複申請 ─────────────────────────────────────────

    def test_duplicate_request_blocked(self):
        """同一排練不能重複申請"""
        self.client.force_login(self.member)
        self.client.post(self.leave_url, {'reason': '第一次申請'})
        r = self.client.post(self.leave_url, {'reason': '重複申請'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LeaveRequest.objects.count(), 1)

    # ── T06 我的請假紀錄 ─────────────────────────────────────

    def test_my_leave_requests_shows_own_records(self):
        """我的請假紀錄只顯示自己的申請"""
        LeaveRequest.objects.create(member=self.member, rehearsal=self.rehearsal, reason='我的請假')
        self.client.force_login(self.member)
        r = self.client.get(self.mine_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '我的請假')

    def test_my_leave_requests_empty_state(self):
        """沒有申請時顯示空狀態提示"""
        self.client.force_login(self.member)
        r = self.client.get(self.mine_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '沒有請假紀錄')

    # ── T07 member 無法進審核頁 ──────────────────────────────

    def test_member_cannot_access_review_page(self):
        """一般 member 存取審核頁應被導向演出活動列表"""
        self.client.force_login(self.member)
        r = self.client.get(self.review_url)
        self.assertRedirects(r, reverse('events:event_list'), fetch_redirect_response=False)

    # ── T08 幹部可進審核頁 ───────────────────────────────────

    def test_officer_can_view_review_page(self):
        """幹部可進入審核頁"""
        self.client.force_login(self.officer)
        r = self.client.get(self.review_url)
        self.assertEqual(r.status_code, 200)

    def test_review_page_shows_pending_requests(self):
        """審核頁顯示待審核申請"""
        LeaveRequest.objects.create(member=self.member, rehearsal=self.rehearsal, reason='待審核測試')
        self.client.force_login(self.officer)
        r = self.client.get(self.review_url)
        self.assertContains(r, '待審核測試')

    # ── T09 幹部核准 ─────────────────────────────────────────

    def test_officer_can_approve(self):
        """幹部核准後狀態變 approved，記錄 reviewed_by 與 reviewed_at"""
        leave = LeaveRequest.objects.create(member=self.member, rehearsal=self.rehearsal, reason='請假')
        self.client.force_login(self.officer)
        r = self.client.post(self.review_url, {'leave_id': leave.pk, 'action': 'approve'})
        self.assertRedirects(r, self.review_url, fetch_redirect_response=False)
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.APPROVED)
        self.assertEqual(leave.reviewed_by, self.officer)
        self.assertIsNotNone(leave.reviewed_at)

    # ── T10 幹部拒絕 ─────────────────────────────────────────

    def test_officer_can_reject(self):
        """幹部拒絕後狀態變 rejected"""
        leave = LeaveRequest.objects.create(member=self.member, rehearsal=self.rehearsal, reason='請假')
        self.client.force_login(self.officer)
        r = self.client.post(self.review_url, {'leave_id': leave.pk, 'action': 'reject'})
        self.assertRedirects(r, self.review_url, fetch_redirect_response=False)
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.REJECTED)
        self.assertEqual(leave.reviewed_by, self.officer)

    # ── T11 核准同步出席紀錄 ──────────────────────────────────

    def test_approve_creates_leave_attendance(self):
        """核准請假後自動建立出席紀錄並標記為請假"""
        leave = LeaveRequest.objects.create(member=self.member, rehearsal=self.rehearsal, reason='請假')
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'leave_id': leave.pk, 'action': 'approve'})
        attendance = RehearsalAttendance.objects.get(rehearsal=self.rehearsal, member=self.member)
        self.assertEqual(attendance.status, RehearsalAttendance.Status.LEAVE)

    def test_approve_updates_existing_attendance_to_leave(self):
        """核准請假時若已有出席紀錄，狀態應更新為請假"""
        RehearsalAttendance.objects.create(
            rehearsal=self.rehearsal, member=self.member,
            status=RehearsalAttendance.Status.ABSENT,
        )
        leave = LeaveRequest.objects.create(member=self.member, rehearsal=self.rehearsal, reason='請假')
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'leave_id': leave.pk, 'action': 'approve'})
        attendance = RehearsalAttendance.objects.get(rehearsal=self.rehearsal, member=self.member)
        self.assertEqual(attendance.status, RehearsalAttendance.Status.LEAVE)

    def test_approve_does_not_overwrite_present_attendance(self):
        """核准請假時若團員已 QR 簽到（PRESENT），出席紀錄不應被覆寫為請假"""
        RehearsalAttendance.objects.create(
            rehearsal=self.rehearsal, member=self.member,
            status=RehearsalAttendance.Status.PRESENT,
        )
        leave = LeaveRequest.objects.create(member=self.member, rehearsal=self.rehearsal, reason='請假')
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'leave_id': leave.pk, 'action': 'approve'})
        attendance = RehearsalAttendance.objects.get(rehearsal=self.rehearsal, member=self.member)
        self.assertEqual(attendance.status, RehearsalAttendance.Status.PRESENT)

    def test_reject_does_not_change_attendance(self):
        """拒絕請假不應影響出席紀錄"""
        leave = LeaveRequest.objects.create(member=self.member, rehearsal=self.rehearsal, reason='請假')
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'leave_id': leave.pk, 'action': 'reject'})
        self.assertFalse(RehearsalAttendance.objects.filter(rehearsal=self.rehearsal, member=self.member).exists())

    # ── T12 已審核區顯示 ─────────────────────────────────────

    def test_reviewed_section_shows_after_action(self):
        """核准/拒絕後已審核區顯示對應標籤"""
        leave = LeaveRequest.objects.create(member=self.member, rehearsal=self.rehearsal, reason='請假')
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'leave_id': leave.pk, 'action': 'approve'})
        r = self.client.get(self.review_url)
        self.assertContains(r, '核准')


class EventViewsTest(TestCase):
    """演出活動 / 排練頁面"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='ev_member',
            email='ev_member@test.local',
            password='testpass123',
            name='活動測試團員',
            role=User.Role.MEMBER,
        )
        self.venue = Venue.objects.create(name='測試場地', type='rehearsal')
        self.event = PerformanceEvent.objects.create(
            name='2026 測試音樂會',
            type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now() + timedelta(days=30),
            performance_venue=self.venue,
            status=PerformanceEvent.Status.CONFIRMED,
        )
        self.past_event = PerformanceEvent.objects.create(
            name='2025 已結束音樂會',
            type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now() - timedelta(days=30),
            performance_venue=self.venue,
            status=PerformanceEvent.Status.FINISHED,
        )
        self.rehearsal = Rehearsal.objects.create(
            event=self.event,
            sequence=1,
            date=timezone.now() + timedelta(days=7),
            venue=self.venue,
            summary_progress='第一樂章進度良好',
            summary_notes='請攜帶樂器',
        )

    # ── T01 演出活動列表 ─────────────────────────────────────

    def test_event_list_requires_login(self):
        """未登入應導向登入頁"""
        r = self.client.get(reverse('events:event_list'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_event_list_accessible(self):
        """登入後可看到活動列表"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:event_list'))
        self.assertEqual(r.status_code, 200)

    def test_event_list_shows_upcoming(self):
        """列表顯示即將到來的活動"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:event_list'))
        self.assertContains(r, '2026 測試音樂會')

    def test_event_list_shows_past(self):
        """列表顯示已結束的活動"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:event_list'))
        self.assertContains(r, '2025 已結束音樂會')

    # ── T02 演出活動詳情 ─────────────────────────────────────

    def test_event_detail_requires_login(self):
        """未登入應導向登入頁"""
        r = self.client.get(reverse('events:event_detail', args=[self.event.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_event_detail_accessible(self):
        """登入後可看到活動詳情"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:event_detail', args=[self.event.pk]))
        self.assertEqual(r.status_code, 200)

    def test_event_detail_shows_name(self):
        """活動詳情顯示活動名稱"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:event_detail', args=[self.event.pk]))
        self.assertContains(r, '2026 測試音樂會')

    def test_event_detail_shows_rehearsals(self):
        """活動詳情顯示排練列表"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:event_detail', args=[self.event.pk]))
        self.assertContains(r, '第 1 次')

    def test_event_detail_404_on_invalid_pk(self):
        """不存在的活動 pk 應回 404"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:event_detail', args=[99999]))
        self.assertEqual(r.status_code, 404)

    # ── T03 排練詳情 ─────────────────────────────────────────

    def test_rehearsal_detail_requires_login(self):
        """未登入應導向登入頁"""
        r = self.client.get(reverse('events:rehearsal_detail', args=[self.rehearsal.pk]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_rehearsal_detail_accessible(self):
        """登入後可看到排練詳情"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:rehearsal_detail', args=[self.rehearsal.pk]))
        self.assertEqual(r.status_code, 200)

    def test_rehearsal_detail_shows_summary(self):
        """排練詳情顯示摘要內容"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:rehearsal_detail', args=[self.rehearsal.pk]))
        self.assertContains(r, '第一樂章進度良好')

    def test_rehearsal_detail_shows_notes(self):
        """排練詳情顯示給團員備註"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:rehearsal_detail', args=[self.rehearsal.pk]))
        self.assertContains(r, '請攜帶樂器')

    def test_rehearsal_detail_has_leave_button(self):
        """排練詳情含申請請假按鈕"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:rehearsal_detail', args=[self.rehearsal.pk]))
        self.assertContains(r, '申請請假')

    def test_rehearsal_detail_404_on_invalid_pk(self):
        """不存在的排練 pk 應回 404"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:rehearsal_detail', args=[99999]))
        self.assertEqual(r.status_code, 404)

    def test_rehearsal_detail_leave_button_disabled_for_past(self):
        """已結束排練的申請請假按鈕應為停用狀態"""
        past_rehearsal = Rehearsal.objects.create(
            event=self.event,
            sequence=99,
            date=timezone.now() - timedelta(days=1),
            venue=self.venue,
        )
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:rehearsal_detail', args=[past_rehearsal.pk]))
        self.assertContains(r, '申請請假')
        self.assertContains(r, 'disabled')

    def test_rehearsal_detail_leave_button_active_for_future(self):
        """未來排練的申請請假按鈕應為可用連結（不含 disabled title）"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:rehearsal_detail', args=[self.rehearsal.pk]))
        self.assertContains(r, '申請請假')
        self.assertNotContains(r, '排練已結束')


class QRCodeTest(TestCase):
    """QR Code 簽到系統"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='qr_member',
            email='qr_member@test.local',
            password='testpass123',
            name='QR 測試團員',
            role=User.Role.MEMBER,
        )
        self.officer = User.objects.create_user(
            username='qr_officer',
            email='qr_officer@test.local',
            password='testpass123',
            name='QR 測試幹部',
            role=User.Role.OFFICER,
        )
        self.venue = Venue.objects.create(name='QR 測試場地', type='rehearsal')
        self.event = PerformanceEvent.objects.create(
            name='QR 測試音樂會',
            type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now() + timedelta(days=30),
            performance_venue=self.venue,
        )
        self.rehearsal = Rehearsal.objects.create(
            event=self.event,
            sequence=1,
            date=timezone.now() + timedelta(days=7),
            venue=self.venue,
        )
        self.manage_url = reverse('events:qr_manage', args=[self.rehearsal.pk])
        self.generate_url = reverse('events:qr_generate', args=[self.rehearsal.pk])

    # ── T01 存取控制 ────────────────────────────────────────

    def test_member_cannot_access_qr_manage(self):
        """一般團員無法進入 QR 管理頁"""
        self.client.force_login(self.member)
        r = self.client.get(self.manage_url)
        self.assertRedirects(r, reverse('events:event_list'), fetch_redirect_response=False)

    def test_officer_can_access_qr_manage(self):
        """幹部可進入 QR 管理頁"""
        self.client.force_login(self.officer)
        r = self.client.get(self.manage_url)
        self.assertEqual(r.status_code, 200)

    def test_unauthenticated_qr_manage_redirects(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.manage_url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    # ── T02 產生 QR Code ─────────────────────────────────────

    def test_qr_generate_invalid_hours_falls_back_to_default(self):
        """傳入非整數的 hours 不應引發 500，應回落為預設值"""
        from .models import RehearsalQRToken
        self.client.force_login(self.officer)
        r = self.client.post(self.generate_url, {'hours': 'abc'})
        self.assertRedirects(r, self.manage_url, fetch_redirect_response=False)
        self.assertTrue(RehearsalQRToken.objects.filter(rehearsal=self.rehearsal).exists())

    def test_qr_generate_hours_clamped_to_max(self):
        """hours 超過 24 應被截斷為 24"""
        from .models import RehearsalQRToken
        from django.utils import timezone as tz
        self.client.force_login(self.officer)
        self.client.post(self.generate_url, {'hours': 999})
        token = RehearsalQRToken.objects.get(rehearsal=self.rehearsal)
        diff = token.expires_at - tz.now()
        self.assertLessEqual(diff.total_seconds(), 24 * 3600 + 5)

    def test_qr_generate_creates_token(self):
        """POST qr_generate 應建立 RehearsalQRToken"""
        from .models import RehearsalQRToken
        self.client.force_login(self.officer)
        self.client.post(self.generate_url, {'hours': 4})
        self.assertTrue(RehearsalQRToken.objects.filter(rehearsal=self.rehearsal).exists())

    def test_qr_generate_token_is_active(self):
        """新產生的 token is_active 為 True"""
        from .models import RehearsalQRToken
        self.client.force_login(self.officer)
        self.client.post(self.generate_url, {'hours': 4})
        token = RehearsalQRToken.objects.get(rehearsal=self.rehearsal)
        self.assertTrue(token.is_active)

    def test_qr_regenerate_changes_uuid(self):
        """重新產生 QR Code 時 UUID 應改變"""
        from .models import RehearsalQRToken
        self.client.force_login(self.officer)
        self.client.post(self.generate_url, {'hours': 4})
        first_token = RehearsalQRToken.objects.get(rehearsal=self.rehearsal).token
        self.client.post(self.generate_url, {'hours': 4})
        second_token = RehearsalQRToken.objects.get(rehearsal=self.rehearsal).token
        self.assertNotEqual(first_token, second_token)

    # ── T03 簽到流程 ─────────────────────────────────────────

    def test_qr_checkin_valid_token_shows_form(self):
        """有效 token 的簽到頁顯示確認按鈕"""
        from .models import RehearsalQRToken
        self.client.force_login(self.officer)
        self.client.post(self.generate_url, {'hours': 4})
        token = RehearsalQRToken.objects.get(rehearsal=self.rehearsal)
        self.client.force_login(self.member)
        r = self.client.get(reverse('events:qr_checkin', args=[token.token]))
        self.assertContains(r, '確認簽到')

    def test_qr_checkin_confirm_creates_attendance(self):
        """POST 簽到後應建立出席紀錄"""
        from .models import RehearsalAttendance, RehearsalQRToken
        self.client.force_login(self.officer)
        self.client.post(self.generate_url, {'hours': 4})
        token = RehearsalQRToken.objects.get(rehearsal=self.rehearsal)
        self.client.force_login(self.member)
        self.client.post(reverse('events:qr_checkin_confirm', args=[token.token]))
        self.assertTrue(
            RehearsalAttendance.objects.filter(
                rehearsal=self.rehearsal,
                member=self.member,
                status=RehearsalAttendance.Status.PRESENT,
            ).exists()
        )

    def test_qr_checkin_already_checked_in_shows_message(self):
        """已簽到的團員再次訪問簽到頁應顯示已完成提示"""
        from .models import RehearsalQRToken
        self.client.force_login(self.officer)
        self.client.post(self.generate_url, {'hours': 4})
        token = RehearsalQRToken.objects.get(rehearsal=self.rehearsal)
        self.client.force_login(self.member)
        # 第一次簽到
        self.client.post(reverse('events:qr_checkin_confirm', args=[token.token]))
        # 再訪簽到頁
        r = self.client.get(reverse('events:qr_checkin', args=[token.token]))
        self.assertContains(r, '已完成簽到')

    # ── T04 停用/啟用 ─────────────────────────────────────────

    def test_qr_toggle_disables_active_token(self):
        """對啟用中的 token 呼叫 toggle 應停用"""
        from .models import RehearsalQRToken
        self.client.force_login(self.officer)
        self.client.post(self.generate_url, {'hours': 4})
        token = RehearsalQRToken.objects.get(rehearsal=self.rehearsal)
        self.assertTrue(token.is_active)
        toggle_url = reverse('events:qr_toggle', args=[self.rehearsal.pk])
        self.client.post(toggle_url)
        token.refresh_from_db()
        self.assertFalse(token.is_active)

    def test_qr_toggle_reenables_inactive_token(self):
        """對已停用的 token 呼叫 toggle 應重新啟用"""
        from .models import RehearsalQRToken
        self.client.force_login(self.officer)
        self.client.post(self.generate_url, {'hours': 4})
        token = RehearsalQRToken.objects.get(rehearsal=self.rehearsal)
        token.is_active = False
        token.save()
        toggle_url = reverse('events:qr_toggle', args=[self.rehearsal.pk])
        self.client.post(toggle_url)
        token.refresh_from_db()
        self.assertTrue(token.is_active)


class SetlistManageTest(TestCase):
    """演出曲目管理"""

    def setUp(self):
        from apps.scores.models import Score
        self.officer = User.objects.create_user(
            username='sl_officer',
            email='sl_officer@test.local',
            password='testpass123',
            name='曲目測試幹部',
            role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='sl_member',
            email='sl_member@test.local',
            password='testpass123',
            name='曲目測試團員',
            role=User.Role.MEMBER,
        )
        self.venue = Venue.objects.create(name='曲目測試場地', type='rehearsal')
        self.event = PerformanceEvent.objects.create(
            name='曲目測試音樂會',
            type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now() + timedelta(days=30),
            performance_venue=self.venue,
        )
        self.full_score = Score.objects.create(
            title='測試總譜', score_type=Score.ScoreType.FULL
        )
        from apps.accounts.models import InstrumentType
        self.instrument = InstrumentType.objects.create(
            name='長笛2', category=InstrumentType.Category.WOODWIND
        )
        self.part_score = Score.objects.create(
            title='測試分譜',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
        )
        self.url = reverse('events:setlist_manage', args=[self.event.pk])

    # ── T01 存取控制 ────────────────────────────────────────

    def test_member_cannot_access(self):
        """一般團員無法進入曲目管理頁"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertRedirects(r, reverse('events:event_detail', args=[self.event.pk]), fetch_redirect_response=False)

    def test_officer_can_access(self):
        """幹部可進入曲目管理頁"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    # ── T02 新增曲目 ─────────────────────────────────────────

    def test_add_full_score_succeeds(self):
        """新增總譜應成功建立 Setlist"""
        from .models import Setlist
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'action': 'add', 'score_id': self.full_score.pk, 'order': 1
        })
        self.assertTrue(Setlist.objects.filter(event=self.event, score=self.full_score).exists())

    def test_add_part_score_blocked(self):
        """嘗試新增分譜應被擋下（404），不建立 Setlist"""
        from .models import Setlist
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {
            'action': 'add', 'score_id': self.part_score.pk, 'order': 1
        })
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Setlist.objects.filter(event=self.event).exists())

    def test_duplicate_order_blocked(self):
        """演出順序重複時應顯示錯誤，不建立第二筆"""
        from .models import Setlist
        self.client.force_login(self.officer)
        self.client.post(self.url, {'action': 'add', 'score_id': self.full_score.pk, 'order': 1})
        from apps.scores.models import Score as ScoreModel
        score2 = ScoreModel.objects.create(title='另一首', score_type=ScoreModel.ScoreType.FULL)
        self.client.post(self.url, {'action': 'add', 'score_id': score2.pk, 'order': 1})
        self.assertEqual(Setlist.objects.filter(event=self.event).count(), 1)

    # ── T03 移除曲目 ─────────────────────────────────────────

    def test_remove_score_deletes_setlist(self):
        """移除曲目應刪除對應 Setlist"""
        from .models import Setlist
        item = Setlist.objects.create(event=self.event, score=self.full_score, order=1)
        self.client.force_login(self.officer)
        self.client.post(self.url, {'action': 'remove', 'item_id': item.pk})
        self.assertFalse(Setlist.objects.filter(pk=item.pk).exists())


class AttendanceReportTest(TestCase):
    """排練出席報表"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='ar_officer', email='ar_officer@test.local',
            password='testpass123', name='出席幹部', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='ar_member', email='ar_member@test.local',
            password='testpass123', name='出席團員', role=User.Role.MEMBER,
        )
        self.venue = Venue.objects.create(name='出席測試場地', type='rehearsal')
        self.event = PerformanceEvent.objects.create(
            name='出席測試音樂會',
            type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now() + timedelta(days=30),
            performance_venue=self.venue,
        )
        self.rehearsal = Rehearsal.objects.create(
            event=self.event, sequence=1,
            date=timezone.now() - timedelta(days=7),
            venue=self.venue,
        )
        self.url = reverse('events:attendance_report', args=[self.event.pk])

    # ── T01 存取控制 ────────────────────────────────────────

    def test_unauthenticated_redirects(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_member_redirects(self):
        """一般團員應被導回活動詳情"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertRedirects(r, reverse('events:event_detail', args=[self.event.pk]),
                             fetch_redirect_response=False)

    def test_officer_can_access(self):
        """幹部可進入出席報表"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_invalid_event_returns_404(self):
        """不存在的活動 pk 應回 404"""
        self.client.force_login(self.officer)
        r = self.client.get(reverse('events:attendance_report', args=[99999]))
        self.assertEqual(r.status_code, 404)

    # ── T02 資料正確性 ──────────────────────────────────────

    def test_shows_rehearsal_in_report(self):
        """報表應顯示排練序號"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '第 1 次')

    def test_shows_member_name(self):
        """報表應顯示團員姓名"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '出席團員')

    def test_present_count_correct(self):
        """出席紀錄存在時統計數字應正確"""
        RehearsalAttendance.objects.create(
            rehearsal=self.rehearsal,
            member=self.member,
            status=RehearsalAttendance.Status.PRESENT,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        rehearsals = r.context['rehearsals']
        self.assertEqual(rehearsals[0].stats['present'], 1)
        self.assertEqual(rehearsals[0].stats['leave'], 0)
        self.assertEqual(rehearsals[0].stats['absent'], 0)

    def test_leave_status_counted_separately(self):
        """請假與缺席各自計入不同欄位"""
        RehearsalAttendance.objects.create(
            rehearsal=self.rehearsal,
            member=self.member,
            status=RehearsalAttendance.Status.LEAVE,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        rehearsals = r.context['rehearsals']
        self.assertEqual(rehearsals[0].stats['leave'], 1)
        self.assertEqual(rehearsals[0].stats['present'], 0)

    def test_no_record_count_includes_members_without_attendance(self):
        """沒有出席紀錄的團員應計入無紀錄欄位"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        rehearsals = r.context['rehearsals']
        # member 沒有任何紀錄 → no_record 至少為 1
        self.assertGreaterEqual(rehearsals[0].stats['no_record'], 1)

    def test_member_row_rate_calculated(self):
        """個人出席率應正確計算"""
        RehearsalAttendance.objects.create(
            rehearsal=self.rehearsal,
            member=self.member,
            status=RehearsalAttendance.Status.PRESENT,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        member_rows = r.context['member_rows']
        member_row = next(row for row in member_rows if row['member'] == self.member)
        self.assertEqual(member_row['present_count'], 1)
        self.assertEqual(member_row['total'], 1)
        self.assertEqual(member_row['rate'], 100)


class LeaveStatsTest(TestCase):
    """請假統計報表"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='ls_officer', email='ls_officer@test.local',
            password='testpass123', name='統計幹部', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='ls_member', email='ls_member@test.local',
            password='testpass123', name='統計團員', role=User.Role.MEMBER,
        )
        self.venue = Venue.objects.create(name='統計測試場地', type='rehearsal')
        self.event = PerformanceEvent.objects.create(
            name='統計測試音樂會',
            type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now() + timedelta(days=30),
            performance_venue=self.venue,
        )
        self.rehearsal = Rehearsal.objects.create(
            event=self.event, sequence=1,
            date=timezone.now() + timedelta(days=7),
            venue=self.venue,
        )
        self.url = reverse('events:leave_stats')

    # ── T01 存取控制 ────────────────────────────────────────

    def test_unauthenticated_redirects(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_member_redirects(self):
        """一般團員應被導回活動列表"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertRedirects(r, reverse('events:event_list'), fetch_redirect_response=False)

    def test_officer_can_access(self):
        """幹部可進入請假統計頁"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    # ── T02 資料正確性 ──────────────────────────────────────

    def test_defaults_to_most_recent_event(self):
        """預設應選取最近一場演出活動"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.context['selected_event'], self.event)

    def test_rehearsal_leave_counts_correct(self):
        """各場排練的核准/待審請假數應正確"""
        LeaveRequest.objects.create(
            member=self.member, rehearsal=self.rehearsal,
            reason='測試請假', status=LeaveRequest.Status.APPROVED,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'event': self.event.pk})
        rehearsal_rows = r.context['rehearsal_rows']
        self.assertEqual(len(rehearsal_rows), 1)
        self.assertEqual(rehearsal_rows[0]['approved'], 1)
        self.assertEqual(rehearsal_rows[0]['pending'], 0)

    def test_member_leave_row_appears(self):
        """有請假紀錄的團員應出現在個人統計區"""
        LeaveRequest.objects.create(
            member=self.member, rehearsal=self.rehearsal,
            reason='測試請假', status=LeaveRequest.Status.PENDING,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'event': self.event.pk})
        member_rows = r.context['member_rows']
        names = [row['member'].name for row in member_rows]
        self.assertIn('統計團員', names)

    def test_member_rows_sorted_by_total_desc(self):
        """個人統計應按請假次數遞減排序"""
        member2 = User.objects.create_user(
            username='ls_member2', email='ls_member2@test.local',
            password='testpass123', name='多假團員', role=User.Role.MEMBER,
        )
        rehearsal2 = Rehearsal.objects.create(
            event=self.event, sequence=2,
            date=timezone.now() + timedelta(days=14),
            venue=self.venue,
        )
        LeaveRequest.objects.create(
            member=self.member, rehearsal=self.rehearsal,
            reason='一次', status=LeaveRequest.Status.PENDING,
        )
        LeaveRequest.objects.create(
            member=member2, rehearsal=self.rehearsal,
            reason='一次', status=LeaveRequest.Status.PENDING,
        )
        LeaveRequest.objects.create(
            member=member2, rehearsal=rehearsal2,
            reason='兩次', status=LeaveRequest.Status.PENDING,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'event': self.event.pk})
        member_rows = r.context['member_rows']
        self.assertEqual(member_rows[0]['member'].name, '多假團員')


class LeaveRequestPastRehearsalTest(TestCase):
    """過期排練的請假申請 server-side 阻擋"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='past_member',
            email='past@test.local',
            password='testpass123',
            name='過期測試員',
            role=User.Role.MEMBER,
        )
        self.venue = Venue.objects.create(name='過期測試場地', type='rehearsal')
        self.event = PerformanceEvent.objects.create(
            name='過期測試音樂會',
            type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now() + timedelta(days=30),
            performance_venue=self.venue,
        )
        self.past_rehearsal = Rehearsal.objects.create(
            event=self.event,
            sequence=1,
            date=timezone.now() - timedelta(days=1),
            venue=self.venue,
        )
        self.leave_url = reverse('events:leave_request_create', args=[self.past_rehearsal.pk])

    def test_post_to_past_rehearsal_is_blocked(self):
        """直接 POST 到已結束排練的請假 URL 應被擋下，不建立資料"""
        self.client.force_login(self.member)
        r = self.client.post(self.leave_url, {'reason': '想繞過前端限制'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(LeaveRequest.objects.count(), 0)
