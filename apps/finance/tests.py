from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .models import MembershipFee


class MembershipFeeReportTest(TestCase):
    """會費繳納狀況報表"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='fee_officer', email='fee_officer@test.local',
            password='testpass123', name='費用幹部', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='fee_member', email='fee_member@test.local',
            password='testpass123', name='費用團員', role=User.Role.MEMBER,
        )
        self.url = reverse('finance:membership_fee_report')

    # ── T01 存取控制 ────────────────────────────────────────

    def test_unauthenticated_redirects(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_member_redirects(self):
        """一般團員應被導回首頁"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertRedirects(r, '/', fetch_redirect_response=False)

    def test_officer_can_access(self):
        """幹部可進入會費繳納狀況頁"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    # ── T02 空狀態 ──────────────────────────────────────────

    def test_no_periods_shows_hint(self):
        """尚無任何期別時應顯示提示訊息"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, 'Django Admin')

    # ── T03 期別選擇 ─────────────────────────────────────────

    def test_defaults_to_most_recent_period(self):
        """預設應顯示最新期別"""
        MembershipFee.objects.create(
            member=self.member, period='2025 下半年', amount=500,
        )
        MembershipFee.objects.create(
            member=self.member, period='2026 上半年', amount=500,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.context['selected_period'], '2026 上半年')

    def test_period_filter_via_get(self):
        """透過 GET 參數可切換期別"""
        MembershipFee.objects.create(
            member=self.member, period='2025 下半年', amount=500,
        )
        MembershipFee.objects.create(
            member=self.member, period='2026 上半年', amount=500,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'period': '2025 下半年'})
        self.assertEqual(r.context['selected_period'], '2025 下半年')

    # ── T04 繳費狀態分類 ─────────────────────────────────────

    def test_paid_member_counted_correctly(self):
        """已繳費的團員應計入 paid_count"""
        from django.utils import timezone
        MembershipFee.objects.create(
            member=self.member, period='2026 上半年',
            amount=500, paid_at=timezone.localdate(),
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'period': '2026 上半年'})
        self.assertEqual(r.context['paid_count'], 1)
        self.assertEqual(r.context['unpaid_count'], 0)

    def test_unpaid_member_counted_correctly(self):
        """未繳費（paid_at 為空）應計入 unpaid_count"""
        MembershipFee.objects.create(
            member=self.member, period='2026 上半年', amount=500,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'period': '2026 上半年'})
        self.assertEqual(r.context['unpaid_count'], 1)
        self.assertEqual(r.context['paid_count'], 0)

    def test_no_record_member_counted(self):
        """該期別無 MembershipFee 紀錄的團員應計入 no_record_count"""
        # member 沒有 2026 上半年的紀錄
        self.client.force_login(self.officer)
        # 先建立一個期別讓頁面能選
        member2 = User.objects.create_user(
            username='fee_member2', email='fee_member2@test.local',
            password='testpass123', name='另一團員', role=User.Role.MEMBER,
        )
        MembershipFee.objects.create(
            member=member2, period='2026 上半年', amount=500,
        )
        r = self.client.get(self.url, {'period': '2026 上半年'})
        # member 沒紀錄 → no_record_count 至少 1
        self.assertGreaterEqual(r.context['no_record_count'], 1)

    def test_rows_include_all_active_members(self):
        """rows 應包含所有啟用中的非管理員團員"""
        MembershipFee.objects.create(
            member=self.member, period='2026 上半年', amount=500,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'period': '2026 上半年'})
        names = [row['member'].name for row in r.context['rows']]
        self.assertIn('費用團員', names)
        # officer 不是 admin，應也在列表中
        self.assertIn('費用幹部', names)
