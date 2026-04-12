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
