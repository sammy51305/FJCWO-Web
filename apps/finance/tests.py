import tempfile

from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import ProtectedError
from django.test import RequestFactory, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User

from .admin import FinanceCategoryAdmin
from .models import (
    FeePeriod, FinanceCategory, FinanceRecord, MembershipFee, PaymentConfig,
)


class MembershipFeeReportTest(TestCase):
    """團費收繳狀況報表（期別改為 FeePeriod 主檔，附錄五 §9 P1）"""

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

    def _period(self, year=2026, term=FeePeriod.Term.FIRST, amount=500):
        return FeePeriod.objects.create(
            year=year, term=term, amount=amount, created_by=self.officer,
        )

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
        """幹部可進入團費收繳狀況頁"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    # ── T02 空狀態 ──────────────────────────────────────────

    def test_no_periods_shows_hint(self):
        """尚無任何期別時應提示先新增期別"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '新增期別')

    # ── T03 期別選擇 ─────────────────────────────────────────

    def test_defaults_to_most_recent_period(self):
        """預設應顯示最新期別（-year, term）"""
        self._period(2025, FeePeriod.Term.SECOND)
        latest = self._period(2026, FeePeriod.Term.FIRST)
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.context['selected_period'], latest)

    def test_period_filter_via_get(self):
        """透過 GET 參數（期別 pk）可切換期別"""
        older = self._period(2025, FeePeriod.Term.SECOND)
        self._period(2026, FeePeriod.Term.FIRST)
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'period': older.pk})
        self.assertEqual(r.context['selected_period'], older)

    # ── T04 繳費狀態分類 ─────────────────────────────────────

    def test_paid_member_counted_correctly(self):
        """已繳費（status=paid）的團員應計入 paid_count"""
        period = self._period()
        MembershipFee.objects.create(
            member=self.member, period=period, amount=500,
            status=MembershipFee.Status.PAID, paid_at=timezone.localdate(),
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'period': period.pk})
        self.assertEqual(r.context['paid_count'], 1)
        self.assertEqual(r.context['unpaid_count'], 0)

    def test_unpaid_member_counted_correctly(self):
        """未繳費（status=unpaid）應計入 unpaid_count"""
        period = self._period()
        MembershipFee.objects.create(
            member=self.member, period=period, amount=500,
            status=MembershipFee.Status.UNPAID,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'period': period.pk})
        self.assertEqual(r.context['unpaid_count'], 1)
        self.assertEqual(r.context['paid_count'], 0)

    def test_void_counted_as_no_record(self):
        """作廢（status=void）的紀錄應視為無紀錄，不計入已繳/未繳"""
        period = self._period()
        MembershipFee.objects.create(
            member=self.member, period=period, amount=500,
            status=MembershipFee.Status.VOID,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'period': period.pk})
        self.assertEqual(r.context['paid_count'], 0)
        self.assertEqual(r.context['unpaid_count'], 0)
        self.assertGreaterEqual(r.context['no_record_count'], 1)

    def test_no_record_member_counted(self):
        """該期別無紀錄的團員應計入 no_record_count"""
        period = self._period()
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'period': period.pk})
        self.assertGreaterEqual(r.context['no_record_count'], 1)

    def test_rows_include_all_active_members(self):
        """rows 應包含所有啟用中的非管理員/非槍手團員"""
        period = self._period()
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'period': period.pk})
        names = [row['member'].name for row in r.context['rows']]
        self.assertIn('費用團員', names)
        self.assertIn('費用幹部', names)

    def test_guest_excluded_from_rows(self):
        """槍手（role=guest）不列入團費名單"""
        period = self._period()
        guest = User.objects.create_user(
            username='fee_guest', email='fee_guest@test.local',
            password='testpass123', name='客座槍手', role=User.Role.GUEST,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'period': period.pk})
        names = [row['member'].name for row in r.context['rows']]
        self.assertNotIn('客座槍手', names)


class FeePeriodTest(TestCase):
    """團費期別主檔 CRUD（附錄五 §9 P1）"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='fp_officer', email='fp_officer@test.local', password='x',
            name='期別幹部', role=User.Role.OFFICER,
        )
        self.admin = User.objects.create_user(
            username='fp_admin', email='fp_admin@test.local', password='x',
            name='期別管理員', role=User.Role.ADMIN,
        )
        self.member = User.objects.create_user(
            username='fp_member', email='fp_member@test.local', password='x',
            name='期別團員', role=User.Role.MEMBER,
        )
        self.list_url = reverse('finance:fee_period_list')
        self.create_url = reverse('finance:fee_period_create')

    def test_member_forbidden(self):
        self.client.force_login(self.member)
        r = self.client.get(self.list_url, follow=True)
        self.assertContains(r, '權限不足')

    def test_officer_can_view_list(self):
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(self.list_url).status_code, 200)

    def test_create_period(self):
        self.client.force_login(self.officer)
        r = self.client.post(self.create_url, {
            'year': '2026', 'term': 'first', 'amount': '1000',
        })
        self.assertRedirects(r, self.list_url)
        p = FeePeriod.objects.get()
        self.assertEqual(p.year, 2026)
        self.assertEqual(p.term, 'first')
        self.assertEqual(p.amount, 1000)
        self.assertEqual(p.created_by, self.officer)

    def test_create_duplicate_blocked(self):
        """同年份+期別不可重複建立"""
        FeePeriod.objects.create(year=2026, term='first', amount=500, created_by=self.officer)
        self.client.force_login(self.officer)
        self.client.post(self.create_url, {'year': '2026', 'term': 'first', 'amount': '800'})
        self.assertEqual(FeePeriod.objects.filter(year=2026, term='first').count(), 1)

    def test_create_invalid_amount_blocked(self):
        """金額 0 應被擋下"""
        self.client.force_login(self.officer)
        self.client.post(self.create_url, {'year': '2026', 'term': 'first', 'amount': '0'})
        self.assertFalse(FeePeriod.objects.exists())

    def test_edit_period(self):
        p = FeePeriod.objects.create(year=2026, term='first', amount=500, created_by=self.officer)
        self.client.force_login(self.officer)
        self.client.post(reverse('finance:fee_period_edit', args=[p.pk]),
                         {'year': '2026', 'term': 'first', 'amount': '1200'})
        p.refresh_from_db()
        self.assertEqual(p.amount, 1200)

    def test_delete_officer_forbidden(self):
        """一般幹部不可刪除期別"""
        p = FeePeriod.objects.create(year=2026, term='first', amount=500, created_by=self.officer)
        self.client.force_login(self.officer)
        r = self.client.post(reverse('finance:fee_period_delete', args=[p.pk]), follow=True)
        self.assertTrue(FeePeriod.objects.filter(pk=p.pk).exists())
        self.assertContains(r, '僅管理員')

    def test_delete_admin_ok(self):
        """管理員可刪除無繳費紀錄的期別"""
        p = FeePeriod.objects.create(year=2026, term='first', amount=500, created_by=self.officer)
        self.client.force_login(self.admin)
        self.client.post(reverse('finance:fee_period_delete', args=[p.pk]))
        self.assertFalse(FeePeriod.objects.filter(pk=p.pk).exists())

    def test_delete_protected_when_has_fees(self):
        """期別已有繳費紀錄（PROTECT）時，即使管理員也擋下"""
        p = FeePeriod.objects.create(year=2026, term='first', amount=500, created_by=self.officer)
        MembershipFee.objects.create(member=self.member, period=p, amount=500)
        self.client.force_login(self.admin)
        r = self.client.post(reverse('finance:fee_period_delete', args=[p.pk]), follow=True)
        self.assertTrue(FeePeriod.objects.filter(pk=p.pk).exists())
        self.assertContains(r, '無法刪除')


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

    # ── 分類（#13-10 新增保險費；2026-11 起分類改為資料表，見 FinanceCategoryTest）──
    def test_insurance_category_exists(self):
        """#13-10：財務收支要有「保險費」分類（幹部 2026-08-12 回饋）"""
        self.assertEqual(FinanceCategory.objects.get(code='insurance').name, '保險費')

    def test_insurance_appears_in_create_form(self):
        """新增收支的表單要列出保險費選項（選項由 FinanceCategory 資料表帶出）"""
        self.client.force_login(self.officer)
        r = self.client.get(reverse('finance:finance_create'))
        self.assertContains(r, 'insurance')
        self.assertContains(r, '保險費')

    def test_can_create_insurance_expense(self):
        """保險費支出能實際存進資料庫"""
        self.client.force_login(self.officer)
        self.client.post(reverse('finance:finance_create'), self._valid_payload(
            type='expense', category='insurance', description='團員平安保險年費',
        ))
        record = FinanceRecord.objects.get(category='insurance')
        self.assertEqual(record.category.name, '保險費')

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
            type='expense', category_id='venue', amount=500, date='2026-08-01',
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
            type='income', category_id='other', amount=100, date='2026-08-01',
            description='x', created_by=self.officer,
        )
        self.client.force_login(self.officer)
        r = self.client.post(reverse('finance:finance_delete', args=[rec.pk]), follow=True)
        self.assertTrue(FinanceRecord.objects.filter(pk=rec.pk).exists())
        self.assertContains(r, '僅管理員')

    def test_delete_admin_ok(self):
        rec = FinanceRecord.objects.create(
            type='income', category_id='other', amount=100, date='2026-08-01',
            description='x', created_by=self.officer,
        )
        self.client.force_login(self.admin)
        self.client.post(reverse('finance:finance_delete', args=[rec.pk]))
        self.assertFalse(FinanceRecord.objects.filter(pk=rec.pk).exists())

    # ── 摘要 ──
    def test_list_summary(self):
        FinanceRecord.objects.create(type='income', category_id='other', amount=1000,
                                     date='2026-08-01', description='收', created_by=self.officer)
        FinanceRecord.objects.create(type='expense', category_id='venue', amount=300,
                                     date='2026-08-02', description='支', created_by=self.officer)
        self.client.force_login(self.officer)
        r = self.client.get(self.list_url)
        self.assertEqual(r.context['income'], 1000)
        self.assertEqual(r.context['expense'], 300)
        self.assertEqual(r.context['balance'], 700)


class FeeEditTest(TestCase):
    """團費登記／編輯（fee_edit）：權限、建立、已繳/未繳、金額由期別快照、更新不重複"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='feedit_officer', email='feedit_officer@test.local', password='x',
            name='團費幹部', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='feedit_member', email='feedit_member@test.local', password='x',
            name='繳費團員', role=User.Role.MEMBER,
        )
        self.period = FeePeriod.objects.create(
            year=2026, term='first', amount=500, created_by=self.officer,
        )
        self.url = reverse('finance:fee_edit')

    def test_member_forbidden(self):
        self.client.force_login(self.member)
        r = self.client.get(self.url, follow=True)
        self.assertContains(r, '權限不足')

    def test_create_paid_fee(self):
        """登記已繳：status=paid、設 paid_at 與收款幹部、金額自期別快照"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'member': self.member.pk, 'period': self.period.pk,
            'paid': 'on', 'paid_at': '2026-08-01',
        })
        fee = MembershipFee.objects.get(member=self.member, period=self.period)
        self.assertEqual(fee.amount, 500)   # 由期別金額快照，非表單輸入
        self.assertEqual(fee.status, MembershipFee.Status.PAID)
        self.assertTrue(fee.is_paid)
        self.assertEqual(fee.collected_by, self.officer)

    def test_create_unpaid_fee(self):
        """未勾已繳：status=unpaid、paid_at 與收款幹部皆為空"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'member': self.member.pk, 'period': self.period.pk,
        })
        fee = MembershipFee.objects.get(member=self.member, period=self.period)
        self.assertEqual(fee.status, MembershipFee.Status.UNPAID)
        self.assertIsNone(fee.paid_at)
        self.assertIsNone(fee.collected_by)

    def test_amount_snapshot_from_period(self):
        """金額一律取期別的固定金額，不受表單傳入影響"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'member': self.member.pk, 'period': self.period.pk, 'amount': '99999',
        })
        fee = MembershipFee.objects.get(member=self.member, period=self.period)
        self.assertEqual(fee.amount, 500)

    def test_update_does_not_duplicate(self):
        """對同一 member+period 再次登記應更新，不建立第二筆（get_or_create）"""
        MembershipFee.objects.create(member=self.member, period=self.period, amount=500)
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'member': self.member.pk, 'period': self.period.pk, 'paid': 'on',
        })
        fees = MembershipFee.objects.filter(member=self.member, period=self.period)
        self.assertEqual(fees.count(), 1)
        self.assertEqual(fees.first().status, MembershipFee.Status.PAID)

    def test_requires_member_and_period(self):
        """缺團員或期別應被擋下"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {'member': '', 'period': ''})
        self.assertFalse(MembershipFee.objects.exists())


class FeeReportTest(TestCase):
    """團員自助申報繳費（附錄五 §9 P2，現金）"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='rpt_member', email='rpt_member@test.local', password='x',
            name='申報團員', role=User.Role.MEMBER,
        )
        self.other = User.objects.create_user(
            username='rpt_other', email='rpt_other@test.local', password='x',
            name='其他團員', role=User.Role.MEMBER,
        )
        self.officer = User.objects.create_user(
            username='rpt_officer', email='rpt_officer@test.local', password='x',
            name='收款幹部', role=User.Role.OFFICER,
        )
        self.period = FeePeriod.objects.create(
            year=2026, term='first', amount=500, created_by=self.officer,
        )
        self.mine_url = reverse('finance:my_fees')
        self.report_url = reverse('finance:fee_report_create', args=[self.period.pk])

    def test_my_fees_requires_login(self):
        r = self.client.get(self.mine_url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_my_fees_shows_period_and_report_action(self):
        """我的團費列出期別，應繳未繳可申報"""
        self.client.force_login(self.member)
        r = self.client.get(self.mine_url)
        self.assertContains(r, str(self.period))
        self.assertContains(r, '申報繳費')

    def test_member_can_report_cash(self):
        """申報現金：建立 reported 紀錄，記收款幹部、金額自期別快照"""
        self.client.force_login(self.member)
        self.client.post(self.report_url, {'collected_by': self.officer.pk})
        fee = MembershipFee.objects.get(member=self.member, period=self.period)
        self.assertEqual(fee.status, MembershipFee.Status.REPORTED)
        self.assertEqual(fee.payment_method, MembershipFee.PaymentMethod.CASH)
        self.assertEqual(fee.collected_by, self.officer)
        self.assertEqual(fee.amount, 500)
        self.assertIsNone(fee.paid_at)

    def test_report_requires_officer(self):
        """現金：未選收款幹部不建立紀錄"""
        self.client.force_login(self.member)
        self.client.post(self.report_url, {'payment_method': 'cash', 'collected_by': ''})
        self.assertFalse(MembershipFee.objects.exists())

    def test_member_can_report_transfer(self):
        """轉帳申報（P4）：建 reported、記末五碼、payment_method=transfer、無收款幹部"""
        self.client.force_login(self.member)
        self.client.post(self.report_url, {'payment_method': 'transfer', 'account_last5': '12345'})
        fee = MembershipFee.objects.get(member=self.member, period=self.period)
        self.assertEqual(fee.status, MembershipFee.Status.REPORTED)
        self.assertEqual(fee.payment_method, MembershipFee.PaymentMethod.TRANSFER)
        self.assertEqual(fee.account_last5, '12345')
        self.assertIsNone(fee.collected_by)

    def test_transfer_requires_valid_last5(self):
        """轉帳末五碼須為 5 位數字，否則不建立"""
        self.client.force_login(self.member)
        self.client.post(self.report_url, {'payment_method': 'transfer', 'account_last5': '12'})
        self.assertFalse(MembershipFee.objects.exists())
        self.client.post(self.report_url, {'payment_method': 'transfer', 'account_last5': 'abcde'})
        self.assertFalse(MembershipFee.objects.exists())

    def test_cannot_report_when_reported(self):
        """已在待確認狀態不可重複申報"""
        MembershipFee.objects.create(
            member=self.member, period=self.period, amount=500,
            status=MembershipFee.Status.REPORTED, collected_by=self.officer,
        )
        self.client.force_login(self.member)
        self.client.post(self.report_url, {'collected_by': self.officer.pk})
        self.assertEqual(MembershipFee.objects.filter(member=self.member, period=self.period).count(), 1)

    def test_cannot_report_when_paid(self):
        """已繳不可再申報"""
        MembershipFee.objects.create(
            member=self.member, period=self.period, amount=500,
            status=MembershipFee.Status.PAID,
        )
        self.client.force_login(self.member)
        self.client.post(self.report_url, {'collected_by': self.officer.pk})
        fee = MembershipFee.objects.get(member=self.member, period=self.period)
        self.assertEqual(fee.status, MembershipFee.Status.PAID)

    def test_can_rereport_after_void(self):
        """作廢後可重新申報（沿用同一列，不違反 unique）"""
        MembershipFee.objects.create(
            member=self.member, period=self.period, amount=500,
            status=MembershipFee.Status.VOID,
        )
        self.client.force_login(self.member)
        self.client.post(self.report_url, {'collected_by': self.officer.pk})
        fees = MembershipFee.objects.filter(member=self.member, period=self.period)
        self.assertEqual(fees.count(), 1)
        self.assertEqual(fees.first().status, MembershipFee.Status.REPORTED)

    def test_withdraw_own_reported(self):
        """團員可撤回自己的待確認申報"""
        fee = MembershipFee.objects.create(
            member=self.member, period=self.period, amount=500,
            status=MembershipFee.Status.REPORTED, collected_by=self.officer,
        )
        self.client.force_login(self.member)
        self.client.post(reverse('finance:fee_report_withdraw', args=[fee.pk]))
        self.assertFalse(MembershipFee.objects.filter(pk=fee.pk).exists())

    def test_cannot_withdraw_paid(self):
        """已確認繳費不可撤回"""
        fee = MembershipFee.objects.create(
            member=self.member, period=self.period, amount=500,
            status=MembershipFee.Status.PAID,
        )
        self.client.force_login(self.member)
        self.client.post(reverse('finance:fee_report_withdraw', args=[fee.pk]))
        self.assertTrue(MembershipFee.objects.filter(pk=fee.pk).exists())

    def test_cannot_withdraw_others(self):
        """不能撤回他人的申報"""
        fee = MembershipFee.objects.create(
            member=self.other, period=self.period, amount=500,
            status=MembershipFee.Status.REPORTED, collected_by=self.officer,
        )
        self.client.force_login(self.member)
        self.client.post(reverse('finance:fee_report_withdraw', args=[fee.pk]))
        self.assertTrue(MembershipFee.objects.filter(pk=fee.pk).exists())


class FeeReviewTest(TestCase):
    """幹部確認/作廢團費 ＋ 管理員硬刪（附錄五 §9 P2）"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='rv_member', email='rv_member@test.local', password='x',
            name='繳費團員', role=User.Role.MEMBER,
        )
        self.officer = User.objects.create_user(
            username='rv_officer', email='rv_officer@test.local', password='x',
            name='審核幹部', role=User.Role.OFFICER,
        )
        self.admin = User.objects.create_user(
            username='rv_admin', email='rv_admin@test.local', password='x',
            name='審核管理員', role=User.Role.ADMIN,
        )
        self.period = FeePeriod.objects.create(
            year=2026, term='first', amount=500, created_by=self.officer,
        )
        self.url = reverse('finance:fee_review_list')

    def _reported(self):
        return MembershipFee.objects.create(
            member=self.member, period=self.period, amount=500,
            status=MembershipFee.Status.REPORTED, collected_by=self.officer,
        )

    def test_member_cannot_access(self):
        self.client.force_login(self.member)
        r = self.client.get(self.url, follow=True)
        self.assertContains(r, '權限不足')

    def test_officer_can_view(self):
        self._reported()
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '繳費團員')

    def test_confirm_sets_paid(self):
        """確認：status=paid、記 paid_at、result_seen=False、金額再快照"""
        self.period.amount = 800   # 確認時應以期別當下金額為準
        self.period.save()
        fee = self._reported()
        self.client.force_login(self.officer)
        self.client.post(self.url, {'fee_id': fee.pk, 'action': 'confirm'})
        fee.refresh_from_db()
        self.assertEqual(fee.status, MembershipFee.Status.PAID)
        self.assertIsNotNone(fee.paid_at)
        self.assertFalse(fee.result_seen)
        self.assertEqual(fee.amount, 800)

    def test_void_sets_void(self):
        """作廢：status=void、result_seen=False"""
        fee = self._reported()
        self.client.force_login(self.officer)
        self.client.post(self.url, {'fee_id': fee.pk, 'action': 'void'})
        fee.refresh_from_db()
        self.assertEqual(fee.status, MembershipFee.Status.VOID)
        self.assertFalse(fee.result_seen)

    def test_cannot_review_processed(self):
        """已處理的申報不可重複操作"""
        fee = MembershipFee.objects.create(
            member=self.member, period=self.period, amount=500,
            status=MembershipFee.Status.PAID,
        )
        self.client.force_login(self.officer)
        self.client.post(self.url, {'fee_id': fee.pk, 'action': 'void'})
        fee.refresh_from_db()
        self.assertEqual(fee.status, MembershipFee.Status.PAID)

    def test_officer_cannot_delete(self):
        """一般幹部不可硬刪團費紀錄"""
        fee = self._reported()
        self.client.force_login(self.officer)
        r = self.client.post(reverse('finance:fee_delete', args=[fee.pk]), follow=True)
        self.assertTrue(MembershipFee.objects.filter(pk=fee.pk).exists())
        self.assertContains(r, '僅管理員')

    def test_admin_can_delete(self):
        """管理員可硬刪團費紀錄"""
        fee = self._reported()
        self.client.force_login(self.admin)
        self.client.post(reverse('finance:fee_delete', args=[fee.pk]))
        self.assertFalse(MembershipFee.objects.filter(pk=fee.pk).exists())


class FeeIncomeTest(TestCase):
    """確認繳費自動入帳到收支明細（附錄五 §9 P3）"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='fi_member', email='fi_member@test.local', password='x',
            name='入帳團員', role=User.Role.MEMBER,
        )
        self.officer = User.objects.create_user(
            username='fi_officer', email='fi_officer@test.local', password='x',
            name='入帳幹部', role=User.Role.OFFICER,
        )
        self.admin = User.objects.create_user(
            username='fi_admin', email='fi_admin@test.local', password='x',
            name='入帳管理員', role=User.Role.ADMIN,
        )
        self.period = FeePeriod.objects.create(
            year=2026, term='first', amount=500, created_by=self.officer,
        )
        self.review_url = reverse('finance:fee_review_list')
        self.edit_url = reverse('finance:fee_edit')

    def _reported(self):
        return MembershipFee.objects.create(
            member=self.member, period=self.period, amount=500,
            status=MembershipFee.Status.REPORTED, collected_by=self.officer,
        )

    def test_confirm_creates_income(self):
        """確認繳費 → 自動產生一筆團費收入（金額、日期=收款日），並連結 finance_record"""
        fee = self._reported()
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'fee_id': fee.pk, 'action': 'confirm'})
        fee.refresh_from_db()
        self.assertIsNotNone(fee.finance_record)
        rec = fee.finance_record
        self.assertEqual(rec.type, FinanceRecord.Type.INCOME)
        self.assertEqual(rec.category_id, 'membership')
        self.assertEqual(rec.amount, 500)
        self.assertEqual(rec.date, fee.paid_at)
        self.assertEqual(FinanceRecord.objects.count(), 1)

    def test_void_reported_creates_no_income(self):
        """作廢待確認的申報不會產生收入（尚未繳費）"""
        fee = self._reported()
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'fee_id': fee.pk, 'action': 'void'})
        self.assertFalse(FinanceRecord.objects.exists())

    def test_fee_edit_paid_creates_income(self):
        """幹部代登記為已繳也會自動入帳"""
        self.client.force_login(self.officer)
        self.client.post(self.edit_url, {
            'member': self.member.pk, 'period': self.period.pk, 'paid': 'on',
        })
        fee = MembershipFee.objects.get(member=self.member, period=self.period)
        self.assertIsNotNone(fee.finance_record)
        self.assertEqual(FinanceRecord.objects.filter(category='membership').count(), 1)

    def test_fee_edit_unpaid_removes_income(self):
        """已繳改回未繳 → 連動移除先前的收入紀錄"""
        self.client.force_login(self.officer)
        # 先登記已繳（產生收入）
        self.client.post(self.edit_url, {
            'member': self.member.pk, 'period': self.period.pk, 'paid': 'on',
        })
        self.assertEqual(FinanceRecord.objects.count(), 1)
        # 再改回未繳
        self.client.post(self.edit_url, {
            'member': self.member.pk, 'period': self.period.pk,
        })
        fee = MembershipFee.objects.get(member=self.member, period=self.period)
        self.assertIsNone(fee.finance_record)
        self.assertFalse(FinanceRecord.objects.exists())

    def test_admin_delete_removes_linked_income(self):
        """管理員硬刪已繳團費 → 連動刪除那筆收入"""
        fee = self._reported()
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'fee_id': fee.pk, 'action': 'confirm'})
        self.assertEqual(FinanceRecord.objects.count(), 1)
        self.client.force_login(self.admin)
        self.client.post(reverse('finance:fee_delete', args=[fee.pk]))
        self.assertFalse(MembershipFee.objects.filter(pk=fee.pk).exists())
        self.assertFalse(FinanceRecord.objects.exists())


class AnnualReportTest(TestCase):
    """當年度收支報表（附錄五 §9 P3）"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='an_officer', email='an_officer@test.local', password='x',
            name='年度幹部', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='an_member', email='an_member@test.local', password='x',
            name='年度團員', role=User.Role.MEMBER,
        )
        self.url = reverse('finance:annual_report')

    def _rec(self, type_, category, amount, date):
        return FinanceRecord.objects.create(
            type=type_, category_id=category, amount=amount, date=date,
            description='x', created_by=self.officer,
        )

    def test_member_forbidden(self):
        self.client.force_login(self.member)
        r = self.client.get(self.url, follow=True)
        self.assertContains(r, '權限不足')

    def test_officer_can_view(self):
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_defaults_to_recent_year(self):
        self._rec('income', 'other', 100, '2025-06-01')
        self._rec('income', 'other', 100, '2026-06-01')
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.context['selected_year'], 2026)

    def test_year_totals(self):
        self._rec('income', 'membership', 1000, '2026-03-01')
        self._rec('expense', 'venue', 300, '2026-04-01')
        self._rec('income', 'other', 999, '2025-01-01')  # 不同年，不計入
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'year': '2026'})
        self.assertEqual(r.context['income'], 1000)
        self.assertEqual(r.context['expense'], 300)
        self.assertEqual(r.context['balance'], 700)

    def test_confirmed_fee_counts_into_year_income(self):
        """整合：確認繳費產生的團費收入，會出現在當年度收支"""
        from django.utils import timezone as tz
        period = FeePeriod.objects.create(year=2026, term='first', amount=500, created_by=self.officer)
        fee = MembershipFee.objects.create(
            member=self.member, period=period, amount=500,
            status=MembershipFee.Status.REPORTED, collected_by=self.officer,
        )
        self.client.force_login(self.officer)
        self.client.post(reverse('finance:fee_review_list'), {'fee_id': fee.pk, 'action': 'confirm'})
        this_year = tz.localdate().year
        r = self.client.get(self.url, {'year': this_year})
        self.assertEqual(r.context['income'], 500)


class PaymentConfigTest(TestCase):
    """轉帳收款設定（附錄五 §9 P4）"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='pc_officer', email='pc_officer@test.local', password='x',
            name='設定幹部', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='pc_member', email='pc_member@test.local', password='x',
            name='設定團員', role=User.Role.MEMBER,
        )
        self.url = reverse('finance:payment_config_edit')

    def test_member_forbidden(self):
        self.client.force_login(self.member)
        r = self.client.get(self.url, follow=True)
        self.assertContains(r, '權限不足')

    def test_officer_can_view(self):
        self.client.force_login(self.officer)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_save_fields(self):
        """儲存結構化收款欄位（代號/名稱/戶名/帳號）到單例設定"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'bank_code': '004', 'bank_name': '臺灣銀行',
            'account_name': '輔仁百韻管樂團', 'account_number': '123456789012',
        })
        config = PaymentConfig.objects.first()
        self.assertIsNotNone(config)
        self.assertEqual(config.bank_code, '004')
        self.assertEqual(config.bank_name, '臺灣銀行')
        self.assertEqual(config.account_name, '輔仁百韻管樂團')
        self.assertEqual(config.account_number, '123456789012')

    def test_account_number_strips_dash(self):
        """帳號存檔時自動去除 dash 與空白，存成純數字"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'bank_code': '822', 'account_number': '123-456-789 012',
        })
        config = PaymentConfig.objects.first()
        self.assertEqual(config.account_number, '123456789012')

    def test_qrcode_upload(self):
        """上傳收款 QR Code 圖檔並保存（隔離到暫存 MEDIA_ROOT，不污染真實 media）"""
        self.client.force_login(self.officer)
        img = SimpleUploadedFile('qr.png', b'\x89PNG\r\n\x1a\nfake-png', content_type='image/png')
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                self.client.post(self.url, {'bank_code': '004', 'qrcode': img})
                config = PaymentConfig.objects.first()
                self.assertTrue(config.qrcode.name)
                self.assertTrue(config.qrcode.name.startswith('payment/'))

    def test_qrcode_replace_deletes_old_file(self):
        """重新上傳 QR Code 會刪掉舊檔，避免 media/payment/ 堆積孤兒檔"""
        import os
        self.client.force_login(self.officer)
        with tempfile.TemporaryDirectory() as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                self.client.post(self.url, {'qrcode': SimpleUploadedFile('a.png', b'aaa', content_type='image/png')})
                old_path = PaymentConfig.objects.first().qrcode.path
                self.assertTrue(os.path.exists(old_path))
                self.client.post(self.url, {'qrcode': SimpleUploadedFile('b.png', b'bbb', content_type='image/png')})
                self.assertFalse(os.path.exists(old_path))
                self.assertTrue(os.path.exists(PaymentConfig.objects.first().qrcode.path))

    def test_media_requires_login(self):
        """/media/ 在 DEBUG=False 也要能提供檔案（否則 QR Code 破圖），但未登入不可讀"""
        self.client.force_login(self.officer)
        # Windows 下串流回應會握著檔案不放，暫存目錄清理時忽略該錯誤
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            with override_settings(MEDIA_ROOT=tmp):
                self.client.post(self.url, {'qrcode': SimpleUploadedFile('a.png', b'aaa', content_type='image/png')})
                url = PaymentConfig.objects.first().qrcode.url
                self.assertEqual(self.client.get(url).status_code, 200)
                self.client.logout()
                self.assertEqual(self.client.get(url).status_code, 302)


class StudentFeeTest(TestCase):
    """學生團費：期別可另訂學生金額，學生在登記、申報、確認各步驟的金額快照都取學生團費"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='sf_officer', email='sf_officer@test.local', password='x',
            name='學生費幹部', role=User.Role.OFFICER,
        )
        self.student = User.objects.create_user(
            username='sf_student', email='sf_student@test.local', password='x',
            name='學生團員', role=User.Role.MEMBER, is_student=True,
        )
        self.adult = User.objects.create_user(
            username='sf_adult', email='sf_adult@test.local', password='x',
            name='一般團員', role=User.Role.MEMBER,
        )
        self.period = FeePeriod.objects.create(
            year=2026, term='second', amount=4500, student_amount=1000, created_by=self.officer,
        )

    def test_amount_for(self):
        """學生取學生團費、非學生取一般金額；期別沒訂學生團費時學生也繳一般金額"""
        self.assertEqual(self.period.amount_for(self.student), 1000)
        self.assertEqual(self.period.amount_for(self.adult), 4500)
        no_student_price = FeePeriod.objects.create(year=2027, term='first', amount=4500)
        self.assertEqual(no_student_price.amount_for(self.student), 4500)

    def test_period_form_saves_student_amount(self):
        """期別表單：學生團費選填，留空存成 None，填 0 被擋下"""
        self.client.force_login(self.officer)
        url = reverse('finance:fee_period_create')
        self.client.post(url, {'year': '2027', 'term': 'first', 'amount': '4500', 'student_amount': '1000'})
        self.assertEqual(FeePeriod.objects.get(year=2027).student_amount, 1000)
        self.client.post(url, {'year': '2028', 'term': 'first', 'amount': '4500', 'student_amount': ''})
        self.assertIsNone(FeePeriod.objects.get(year=2028).student_amount)
        self.client.post(url, {'year': '2029', 'term': 'first', 'amount': '4500', 'student_amount': '0'})
        self.assertFalse(FeePeriod.objects.filter(year=2029).exists())

    def test_officer_fee_edit_uses_student_amount(self):
        """幹部登記學生已繳：金額與自動產生的收支明細收入都是 1,000，不被期別金額蓋回 4,500"""
        self.client.force_login(self.officer)
        self.client.post(reverse('finance:fee_edit'), {
            'member': self.student.pk, 'period': self.period.pk, 'paid': 'on', 'paid_at': '2026-11-02',
        })
        fee = MembershipFee.objects.get(member=self.student)
        self.assertEqual(fee.amount, 1000)
        self.assertEqual(fee.finance_record.amount, 1000)

    def test_self_report_and_confirm_keep_student_amount(self):
        """學生自行申報 → 金額 1,000；幹部確認時重新快照仍是 1,000"""
        self.client.force_login(self.student)
        self.client.post(reverse('finance:fee_report_create', args=[self.period.pk]), {
            'payment_method': 'transfer', 'account_last5': '01234',
        })
        fee = MembershipFee.objects.get(member=self.student)
        self.assertEqual((fee.status, fee.amount), (MembershipFee.Status.REPORTED, 1000))

        self.client.force_login(self.officer)
        self.client.post(reverse('finance:fee_review_list'), {'fee_id': fee.pk, 'action': 'confirm'})
        fee.refresh_from_db()
        self.assertEqual((fee.status, fee.amount), (MembershipFee.Status.PAID, 1000))

    def test_my_fees_and_report_form_show_student_amount(self):
        """「我的團費」與申報頁顯示學生應繳的 1,000"""
        self.client.force_login(self.student)
        r = self.client.get(reverse('finance:my_fees'))
        self.assertEqual(r.context['rows'][0]['amount_due'], 1000)
        r = self.client.get(reverse('finance:fee_report_create', args=[self.period.pk]))
        self.assertEqual(r.context['amount_due'], 1000)
        self.assertContains(r, '學生團費')

    def test_report_marks_students(self):
        """團費收繳狀況：表頭列出學生團費、學生名字旁標「學生」"""
        self.client.force_login(self.officer)
        r = self.client.get(reverse('finance:membership_fee_report'), {'period': self.period.pk})
        self.assertContains(r, '學生 1000 元')
        self.assertContains(r, 'badge bg-info text-dark">學生</span>')


class FinanceCategoryTest(TestCase):
    """收支分類改為資料表（2026-11）：預設分類、自訂分類、適用範圍、停用、系統分類保護。"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='cat_officer', email='cat_officer@test.local', password='x',
            name='分類幹部', role=User.Role.OFFICER,
        )
        self.create_url = reverse('finance:finance_create')

    def _payload(self, **over):
        data = {'type': 'income', 'category': 'sponsorship', 'amount': '5000',
                'date': '2026-11-08', 'description': '校友贊助'}
        data.update(over)
        return data

    def _record(self, code='sponsorship', type_='income', description='x'):
        return FinanceRecord.objects.create(
            type=type_, category_id=code, amount=100, date='2026-08-01',
            description=description, created_by=self.officer,
        )

    def test_default_categories_seeded_by_migration(self):
        """資料遷移要建好原本 8 個分類，加上新增的「贊助／捐款」「幹部代墊」；不含售票收入"""
        codes = set(FinanceCategory.objects.values_list('code', flat=True))
        self.assertEqual(codes, {
            'venue', 'instructor', 'instrument_purchase', 'instrument_maintenance',
            'score', 'insurance', 'membership', 'sponsorship', 'officer_advance', 'other',
        })
        self.assertFalse(FinanceCategory.objects.filter(name__contains='售票').exists())

    def test_kinds_of_new_categories(self):
        """贊助／捐款只能是收入；幹部代墊收入（墊進來）與支出（歸還）都要能記"""
        self.assertEqual(FinanceCategory.objects.get(code='sponsorship').kind, 'income')
        self.assertEqual(FinanceCategory.objects.get(code='officer_advance').kind, 'both')

    def test_custom_category_gets_code_and_can_be_used(self):
        """幹部自己加的分類：自動配代碼，馬上能在新增收支的表單選到並存檔"""
        cat = FinanceCategory.objects.create(name='義演收入', kind='income')
        self.assertTrue(cat.code)
        self.client.force_login(self.officer)
        self.assertContains(self.client.get(self.create_url), '義演收入')
        self.client.post(self.create_url, self._payload(category=cat.code, description='義演'))
        self.assertEqual(FinanceRecord.objects.get(description='義演').category, cat)

    def test_income_only_category_rejected_for_expense(self):
        """「贊助／捐款」是收入專用，選成支出要被擋"""
        self.client.force_login(self.officer)
        self.client.post(self.create_url, self._payload(type='expense'))
        self.assertFalse(FinanceRecord.objects.exists())

    def test_both_category_works_for_income_and_expense(self):
        """幹部代墊：墊進來是收入、歸還是支出"""
        self.client.force_login(self.officer)
        self.client.post(self.create_url,
                         self._payload(category='officer_advance', description='代墊'))
        self.client.post(self.create_url,
                         self._payload(category='officer_advance', type='expense',
                                       description='歸還'))
        self.assertEqual(FinanceRecord.objects.filter(category_id='officer_advance').count(), 2)

    def test_unknown_category_rejected(self):
        self.client.force_login(self.officer)
        self.client.post(self.create_url, self._payload(category='nope'))
        self.assertFalse(FinanceRecord.objects.exists())

    def test_inactive_category_hidden_and_rejected_for_new(self):
        """停用的分類：新增表單不再列出、直接送出也會被擋"""
        FinanceCategory.objects.filter(code='sponsorship').update(is_active=False)
        self.client.force_login(self.officer)
        self.assertNotContains(self.client.get(self.create_url), 'sponsorship')
        self.client.post(self.create_url, self._payload())
        self.assertFalse(FinanceRecord.objects.exists())

    def test_inactive_category_kept_when_editing_old_record(self):
        """分類後來被停用，舊紀錄仍能正常編輯、分類不會被改掉"""
        rec = self._record(description='舊贊助')
        FinanceCategory.objects.filter(code='sponsorship').update(is_active=False)
        self.client.force_login(self.officer)
        edit_url = reverse('finance:finance_edit', args=[rec.pk])
        self.assertContains(self.client.get(edit_url), '已停用')
        self.client.post(edit_url, self._payload(amount='200', description='舊贊助（改）'))
        rec.refresh_from_db()
        self.assertEqual((rec.amount, rec.category_id), (200, 'sponsorship'))

    def test_category_in_use_cannot_be_deleted(self):
        """已有紀錄用的分類刪不掉（PROTECT），只能停用"""
        self._record()
        with self.assertRaises(ProtectedError):
            FinanceCategory.objects.get(code='sponsorship').delete()

    def test_rename_does_not_touch_records(self):
        """改名後舊紀錄跟著顯示新名稱（紀錄是以代碼指向分類）"""
        rec = self._record()
        FinanceCategory.objects.filter(code='sponsorship').update(name='贊助')
        rec.refresh_from_db()
        self.assertEqual(rec.category.name, '贊助')

    def test_membership_is_system_category(self):
        """團費是系統分類：後台不能刪、改名／停用欄位唯讀"""
        cat = FinanceCategory.membership()
        self.assertTrue(cat.is_system)
        model_admin = FinanceCategoryAdmin(FinanceCategory, AdminSite())
        request = RequestFactory().get('/')
        request.user = User.objects.create_superuser(
            username='cat_root', email='cat_root@test.local', password='x')
        self.assertFalse(model_admin.has_delete_permission(request, cat))
        self.assertTrue(model_admin.has_delete_permission(
            request, FinanceCategory.objects.get(code='sponsorship')))
        self.assertIn('is_active', model_admin.get_readonly_fields(request, cat))

    def test_membership_recreated_if_missing(self):
        """團費分類被清掉時，FinanceCategory.membership() 會補建，確認繳費不會因此壞掉"""
        FinanceCategory.objects.filter(code='membership').delete()
        self.assertEqual(FinanceCategory.membership().code, 'membership')

    def test_annual_report_groups_by_category_name(self):
        """年度報表依分類名稱彙總，贊助不再混進「其他」"""
        for code, amt in [('sponsorship', 3000), ('other', 500)]:
            FinanceRecord.objects.create(
                type='income', category_id=code, amount=amt, date='2026-06-01',
                description='x', created_by=self.officer)
        self.client.force_login(self.officer)
        r = self.client.get(reverse('finance:annual_report'), {'year': 2026})
        names = {row['category']: row['income'] for row in r.context['rows']}
        self.assertEqual(names, {'贊助／捐款': 3000, '其他': 500})
