from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import User
from apps.public.models import Venue
from .models import LeaveRequest, PerformanceEvent, Rehearsal


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

    # ── T11 已審核區顯示 ─────────────────────────────────────

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
