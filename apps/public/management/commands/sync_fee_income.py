"""
manage.py sync_fee_income
=========================
補登「團費已繳、收支明細卻沒有這筆收入」的漏網之魚（2026-11-20 回饋）。

正常操作（幹部登記已繳、確認團員申報、試算表匯入）都會自動產生收入；
漏掉的通常是在 Django Admin 直接把團費改成已繳（2026-11-20 起後台也會同步，但之前改的不會）。

只處理「狀態為已繳」的團費：
- 沒有對應收入 → 補一筆（金額＝團費金額、日期＝繳費日，與網站操作同一套邏輯）
- 有對應收入但金額不一致 → 改成團費金額

使用方式：
    python manage.py sync_fee_income                                # 只列出會補哪些，不動資料庫（預設）
    python manage.py sync_fee_income --apply --operator <幹部帳號>  # 實際寫入
補登的收入「建立者」記為該筆的收款幹部；沒有收款幹部（例如轉帳）時記為 --operator。
可重複執行：已補過的不會再補第二筆。
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.finance.models import MembershipFee
from apps.finance.views import _sync_fee_income


class Command(BaseCommand):
    help = '補登已繳團費缺少的收支明細收入（預設只列出，加 --apply 才寫入）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='實際寫入資料庫')
        parser.add_argument('--operator', help='幹部帳號（--apply 時必填），記為沒有收款幹部那幾筆收入的建立者')

    def handle(self, *args, apply=False, operator=None, **options):
        operator_user = None
        if apply:
            if not operator:
                raise CommandError('加 --apply 時請一併給 --operator <幹部帳號>。')
            operator_user = User.objects.filter(username=operator).first()
            if operator_user is None:
                raise CommandError(f'找不到帳號「{operator}」。')
            if not operator_user.is_officer:
                raise CommandError(f'「{operator}」不是幹部，不能執行補登。')

        fees = (
            MembershipFee.objects.filter(status=MembershipFee.Status.PAID)
            .select_related('member', 'period', 'finance_record', 'collected_by')
            .order_by('period__year', 'period__term', 'member__name')
        )
        todo = []
        for fee in fees:
            rec = fee.finance_record
            if rec is None:
                todo.append((fee, '缺收入'))
            elif rec.amount != fee.amount:
                todo.append((fee, f'收入金額 {rec.amount:.0f} ≠ 團費 {fee.amount:.0f}'))

        if not todo:
            self.stdout.write(self.style.SUCCESS('所有已繳團費都有對應的收支明細收入，不需要補登。'))
            return

        for fee, reason in todo:
            self.stdout.write(
                f'  {fee.period}  {fee.member.name}  {fee.amount:.0f} 元'
                f'  繳費日 {fee.paid_at or "（未填，以今天入帳）"}  → {reason}'
            )

        if not apply:
            self.stdout.write(self.style.WARNING(
                f'共 {len(todo)} 筆需要補登。這次只是列出，沒有寫入；'
                f'確認無誤後加上 --apply --operator <幹部帳號> 再跑一次。'
            ))
            return

        with transaction.atomic():
            for fee, _ in todo:
                _sync_fee_income(fee, fee.collected_by or operator_user)
        self.stdout.write(self.style.SUCCESS(f'已補登 {len(todo)} 筆團費收入。'))
