from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User

from .models import AssetBorrow, BandProperty


class BorrowStatusReportTest(TestCase):
    """公用財產借用現況報表"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='asset_officer', email='asset_officer@test.local',
            password='testpass123', name='財產幹部', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='asset_member', email='asset_member@test.local',
            password='testpass123', name='財產團員', role=User.Role.MEMBER,
        )
        self.asset = BandProperty.objects.create(
            name='測試長笛', category=BandProperty.Category.INSTRUMENT,
        )
        self.url = reverse('assets:borrow_status_report')

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
        """幹部可進入財產借用現況頁"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    # ── T02 空狀態 ──────────────────────────────────────────

    def test_no_active_borrows_shows_empty(self):
        """沒有借出中財產時應顯示空訊息"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '目前沒有借出中的財產')

    # ── T03 資料顯示 ─────────────────────────────────────────

    def test_active_borrow_appears_in_report(self):
        """借出中財產應出現在報表"""
        AssetBorrow.objects.create(
            asset=self.asset, borrower=self.member,
            borrowed_at=timezone.localdate(),
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '測試長笛')
        self.assertContains(r, '財產團員')

    def test_returned_borrow_not_in_report(self):
        """已歸還的財產不應出現在報表"""
        today = timezone.localdate()
        AssetBorrow.objects.create(
            asset=self.asset, borrower=self.member,
            borrowed_at=today - timedelta(days=5),
            returned_at=today,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        rows = r.context['rows']
        self.assertEqual(len(rows), 0)

    def test_overdue_borrow_is_flagged(self):
        """逾期未還的財產應被標記為逾期"""
        today = timezone.localdate()
        AssetBorrow.objects.create(
            asset=self.asset, borrower=self.member,
            borrowed_at=today - timedelta(days=10),
            due_date=today - timedelta(days=3),
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        rows = r.context['rows']
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]['overdue'])

    def test_not_yet_due_borrow_is_not_overdue(self):
        """尚未到期的借用不應標記為逾期"""
        today = timezone.localdate()
        AssetBorrow.objects.create(
            asset=self.asset, borrower=self.member,
            borrowed_at=today,
            due_date=today + timedelta(days=7),
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        rows = r.context['rows']
        self.assertFalse(rows[0]['overdue'])

    def test_overdue_count_in_context(self):
        """overdue_count 應正確反映逾期數量"""
        today = timezone.localdate()
        AssetBorrow.objects.create(
            asset=self.asset, borrower=self.member,
            borrowed_at=today - timedelta(days=10),
            due_date=today - timedelta(days=2),
        )
        asset2 = BandProperty.objects.create(
            name='測試譜架', category=BandProperty.Category.STAND,
        )
        AssetBorrow.objects.create(
            asset=asset2, borrower=self.member,
            borrowed_at=today,
            due_date=today + timedelta(days=7),
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.context['overdue_count'], 1)
