from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User

from .models import FeePeriod, FinanceRecord, MembershipFee


class MembershipFeeReportTest(TestCase):
    """會費繳納狀況報表（期別改為 FeePeriod 主檔，附錄五 §9 P1）"""

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
        """幹部可進入會費繳納狀況頁"""
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
        """槍手（role=guest）不列入會費名單"""
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
    """會費期別主檔 CRUD（附錄五 §9 P1）"""

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
    """會費登記／編輯（fee_edit）：權限、建立、已繳/未繳、金額由期別快照、更新不重複"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='feedit_officer', email='feedit_officer@test.local', password='x',
            name='會費幹部', role=User.Role.OFFICER,
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
        """我的會費列出期別，應繳未繳可申報"""
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
        """未選收款幹部不建立紀錄"""
        self.client.force_login(self.member)
        self.client.post(self.report_url, {'collected_by': ''})
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
    """幹部確認/作廢會費 ＋ 管理員硬刪（附錄五 §9 P2）"""

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
        """一般幹部不可硬刪會費紀錄"""
        fee = self._reported()
        self.client.force_login(self.officer)
        r = self.client.post(reverse('finance:fee_delete', args=[fee.pk]), follow=True)
        self.assertTrue(MembershipFee.objects.filter(pk=fee.pk).exists())
        self.assertContains(r, '僅管理員')

    def test_admin_can_delete(self):
        """管理員可硬刪會費紀錄"""
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
        """確認繳費 → 自動產生一筆會費收入（金額、日期=收款日），並連結 finance_record"""
        fee = self._reported()
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'fee_id': fee.pk, 'action': 'confirm'})
        fee.refresh_from_db()
        self.assertIsNotNone(fee.finance_record)
        rec = fee.finance_record
        self.assertEqual(rec.type, FinanceRecord.Type.INCOME)
        self.assertEqual(rec.category, FinanceRecord.Category.MEMBERSHIP)
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
        """管理員硬刪已繳會費 → 連動刪除那筆收入"""
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
            type=type_, category=category, amount=amount, date=date,
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
        """整合：確認繳費產生的會費收入，會出現在當年度收支"""
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
