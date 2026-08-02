from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User

from .models import FinanceRecord, MembershipFee


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
        """尚無任何期別時應顯示提示訊息（引導使用「登記繳費」）"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '登記繳費')

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


class FinanceRecordCRUDTest(TestCase):
    """收支明細（FinanceRecord）前端 CRUD：權限、amount 驗證、摘要、刪除限管理員"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='fin_officer', email='fin_officer@test.local', password='x',
            name='財務幹部', role=User.Role.OFFICER,
        )
        self.admin = User.objects.create_user(
            username='fin_admin', email='fin_admin@test.local', password='x',
            name='財務管理員', role=User.Role.ADMIN,
        )
        self.member = User.objects.create_user(
            username='fin_member', email='fin_member@test.local', password='x',
            name='一般團員', role=User.Role.MEMBER,
        )
        self.list_url = reverse('finance:finance_list')

    def _valid_payload(self, **over):
        data = {
            'type': 'income', 'category': 'membership', 'amount': '1000',
            'date': '2026-08-03', 'description': '測試收入',
        }
        data.update(over)
        return data

    # ── 存取控制 ──
    def test_list_unauthenticated_redirects(self):
        r = self.client.get(self.list_url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_list_member_forbidden(self):
        self.client.force_login(self.member)
        r = self.client.get(self.list_url, follow=True)
        self.assertContains(r, '權限不足')

    def test_officer_can_view_list(self):
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(self.list_url).status_code, 200)

    # ── 新增 ──
    def test_create_record(self):
        self.client.force_login(self.officer)
        r = self.client.post(reverse('finance:finance_create'), self._valid_payload())
        self.assertRedirects(r, self.list_url)
        rec = FinanceRecord.objects.get(description='測試收入')
        self.assertEqual(rec.amount, 1000)
        self.assertEqual(rec.type, 'income')
        self.assertEqual(rec.created_by, self.officer)  # 登記者自動帶入

    def test_create_rejects_zero_amount(self):
        """金額 0 應被擋下（amount 必須 > 0）"""
        self.client.force_login(self.officer)
        self.client.post(reverse('finance:finance_create'), self._valid_payload(amount='0'))
        self.assertFalse(FinanceRecord.objects.exists())

    def test_create_rejects_negative_amount(self):
        self.client.force_login(self.officer)
        self.client.post(reverse('finance:finance_create'), self._valid_payload(amount='-50'))
        self.assertFalse(FinanceRecord.objects.exists())

    def test_create_requires_description(self):
        self.client.force_login(self.officer)
        self.client.post(reverse('finance:finance_create'), self._valid_payload(description=''))
        self.assertFalse(FinanceRecord.objects.exists())

    # ── 編輯 ──
    def test_edit_record(self):
        rec = FinanceRecord.objects.create(
            type='expense', category='venue', amount=500, date='2026-08-01',
            description='場地費', created_by=self.officer,
        )
        self.client.force_login(self.officer)
        self.client.post(reverse('finance:finance_edit', args=[rec.pk]),
                         self._valid_payload(type='expense', category='venue',
                                             amount='800', description='場地費（調整）'))
        rec.refresh_from_db()
        self.assertEqual(rec.amount, 800)
        self.assertEqual(rec.description, '場地費（調整）')

    # ── 刪除限管理員 ──
    def test_delete_officer_forbidden(self):
        rec = FinanceRecord.objects.create(
            type='income', category='other', amount=100, date='2026-08-01',
            description='x', created_by=self.officer,
        )
        self.client.force_login(self.officer)
        r = self.client.post(reverse('finance:finance_delete', args=[rec.pk]), follow=True)
        self.assertTrue(FinanceRecord.objects.filter(pk=rec.pk).exists())
        self.assertContains(r, '僅管理員')

    def test_delete_admin_ok(self):
        rec = FinanceRecord.objects.create(
            type='income', category='other', amount=100, date='2026-08-01',
            description='x', created_by=self.officer,
        )
        self.client.force_login(self.admin)
        self.client.post(reverse('finance:finance_delete', args=[rec.pk]))
        self.assertFalse(FinanceRecord.objects.filter(pk=rec.pk).exists())

    # ── 摘要 ──
    def test_list_summary(self):
        FinanceRecord.objects.create(type='income', category='other', amount=1000,
                                     date='2026-08-01', description='收', created_by=self.officer)
        FinanceRecord.objects.create(type='expense', category='venue', amount=300,
                                     date='2026-08-02', description='支', created_by=self.officer)
        self.client.force_login(self.officer)
        r = self.client.get(self.list_url)
        self.assertEqual(r.context['income'], 1000)
        self.assertEqual(r.context['expense'], 300)
        self.assertEqual(r.context['balance'], 700)


class FeeEditTest(TestCase):
    """會費登記／編輯（fee_edit）：權限、建立、已繳/未繳、更新不重複、amount 驗證"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='feedit_officer', email='feedit_officer@test.local', password='x',
            name='會費幹部', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='feedit_member', email='feedit_member@test.local', password='x',
            name='繳費團員', role=User.Role.MEMBER,
        )
        self.url = reverse('finance:fee_edit')

    def test_member_forbidden(self):
        self.client.force_login(self.member)
        r = self.client.get(self.url, follow=True)
        self.assertContains(r, '權限不足')

    def test_create_paid_fee(self):
        """登記已繳：建立 MembershipFee，設 paid_at 與收款幹部"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'member': self.member.pk, 'period': '2026 上半年',
            'amount': '500', 'paid': 'on', 'paid_at': '2026-08-01',
        })
        fee = MembershipFee.objects.get(member=self.member, period='2026 上半年')
        self.assertEqual(fee.amount, 500)
        self.assertTrue(fee.is_paid)
        self.assertEqual(fee.collected_by, self.officer)

    def test_create_unpaid_fee(self):
        """未勾已繳：paid_at 與收款幹部皆為空"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'member': self.member.pk, 'period': '2026 上半年', 'amount': '500',
        })
        fee = MembershipFee.objects.get(member=self.member, period='2026 上半年')
        self.assertIsNone(fee.paid_at)
        self.assertIsNone(fee.collected_by)

    def test_update_does_not_duplicate(self):
        """對同一 member+period 再次登記應更新，不建立第二筆（get_or_create）"""
        MembershipFee.objects.create(member=self.member, period='2026 上半年', amount=500)
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'member': self.member.pk, 'period': '2026 上半年', 'amount': '800',
        })
        fees = MembershipFee.objects.filter(member=self.member, period='2026 上半年')
        self.assertEqual(fees.count(), 1)
        self.assertEqual(fees.first().amount, 800)

    def test_amount_must_be_positive(self):
        """金額 0 應被擋下，不建立紀錄"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'member': self.member.pk, 'period': '2026 上半年', 'amount': '0',
        })
        self.assertFalse(MembershipFee.objects.exists())

    def test_requires_member_and_period(self):
        """缺團員或期別應被擋下"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {'member': '', 'period': '', 'amount': '500'})
        self.assertFalse(MembershipFee.objects.exists())
