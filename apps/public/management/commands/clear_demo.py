"""
manage.py clear_demo
====================
清除 `manage.py seed_demo` 建立的 demo 資料。

**只刪 seed_demo 建立的東西**——依帳號前綴（demo_）與各類資料的固定名稱比對，
不會碰到主檔（樂器/聲部/場地）、既有帳號，或幹部自己新增的資料。

使用方式：
    python manage.py clear_demo --dry-run   # 只列出會刪什麼，不動資料庫
    python manage.py clear_demo             # 實際刪除（會再問一次）
    python manage.py clear_demo --noinput   # 不詢問直接刪

刪除順序依 FK 的 PROTECT 限制排定（例如 Announcement.created_by、
MembershipFee.period、Setlist.score 都是 PROTECT，必須先刪引用方）。

轉帳收款設定（PaymentConfig）為單例設定、不刪除，僅在結尾提醒自行更新。
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import Registration, User
from apps.announcements.models import Announcement
from apps.assets.models import AssetBorrow, BandProperty
from apps.events.models import (
    LeaveRequest, PerformanceAttendance, PerformanceEvent, PerformanceLeaveRequest,
    Rehearsal, RehearsalAttendance, RehearsalQRToken, Setlist,
)
from apps.finance.models import FeePeriod, FinanceRecord, MembershipFee, PaymentConfig
from apps.scores.models import Score

from .seed_demo import (
    DEMO_ANNOUNCEMENT_TITLES, DEMO_ASSET_NAMES, DEMO_EVENT_NAME,
    DEMO_FEE_PERIOD, DEMO_FINANCE_DESCRIPTIONS, DEMO_REGISTRATION_EMAILS,
    DEMO_SCORE_TITLES, DEMO_USERNAME_PREFIX,
)


class Command(BaseCommand):
    help = '清除 seed_demo 建立的 demo 資料'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='只列出會刪除什麼，不實際刪除')
        parser.add_argument('--noinput', action='store_true',
                            help='不詢問確認直接刪除')

    def _say(self, msg, style=None):
        """verbosity=0 時完全靜音（測試呼叫時不要污染測試輸出）。"""
        if self.verbosity:
            self.stdout.write(style(msg) if style else msg)

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        dry = options['dry_run']

        def freeze(model, qs):
            """
            把 queryset 固化成一組 pk。刪除是分批進行的，若沿用 lazy queryset，
            後面的查詢會因為前面已刪掉關聯而查不到東西（例如會費入帳的收入是靠
            MembershipFee 反查的，會費一刪就找不到那些收入，導致漏刪後續 PROTECT 爆掉）。
            """
            return model.objects.filter(pk__in=list(qs.values_list('pk', flat=True)))

        users = freeze(User, User.objects.filter(
            username__startswith=DEMO_USERNAME_PREFIX))
        events = freeze(PerformanceEvent,
                        PerformanceEvent.objects.filter(name=DEMO_EVENT_NAME))
        rehearsals = freeze(Rehearsal, Rehearsal.objects.filter(event__in=events))
        full_scores = freeze(Score, Score.objects.filter(
            title__in=DEMO_SCORE_TITLES, score_type=Score.ScoreType.FULL))
        part_scores = freeze(Score, Score.objects.filter(full_score__in=full_scores))
        assets = freeze(BandProperty,
                        BandProperty.objects.filter(name__in=DEMO_ASSET_NAMES))
        fee_periods = freeze(FeePeriod, FeePeriod.objects.filter(
            year=DEMO_FEE_PERIOD[0], term=DEMO_FEE_PERIOD[1]))
        member_fees = freeze(MembershipFee,
                             MembershipFee.objects.filter(member__in=users))
        registrations = freeze(Registration, Registration.objects.filter(
            email__in=DEMO_REGISTRATION_EMAILS))

        # FinanceRecord.created_by 與 Announcement.created_by 都是 PROTECT User，
        # 除了 seed 建立的那幾筆，還要涵蓋 demo 期間用 demo 帳號新增的資料，
        # 否則最後刪帳號時會被 PROTECT 擋下。
        finance = freeze(FinanceRecord, FinanceRecord.objects.filter(
            Q(description__in=DEMO_FINANCE_DESCRIPTIONS) | Q(created_by__in=users)))
        announcements = freeze(Announcement, Announcement.objects.filter(
            Q(title__in=DEMO_ANNOUNCEMENT_TITLES) | Q(created_by__in=users)))

        plan = [
            ('演出曲目 Setlist', Setlist.objects.filter(event__in=events)),
            ('排練出席紀錄', RehearsalAttendance.objects.filter(rehearsal__in=rehearsals)),
            ('排練 QR Token', RehearsalQRToken.objects.filter(rehearsal__in=rehearsals)),
            ('排練請假', LeaveRequest.objects.filter(rehearsal__in=rehearsals)),
            ('演出請假', PerformanceLeaveRequest.objects.filter(event__in=events)),
            ('演出出席確認', PerformanceAttendance.objects.filter(event__in=events)),
            ('會費繳納紀錄', member_fees),
            ('財務收支（含會費自動入帳）', finance),
            ('公告', announcements),
            ('財產借用紀錄', AssetBorrow.objects.filter(asset__in=assets)),
            ('公用財產', assets),
            ('樂譜（分譜）', part_scores),
            ('樂譜（總譜）', full_scores),
            ('排練', rehearsals),
            ('演出活動', events),
            ('校友報到申請', registrations),
            ('會費期別 2026 下期', fee_periods),
            ('demo 帳號', users),
        ]

        counts = [(label, qs.count()) for label, qs in plan]
        total = sum(n for _, n in counts)

        self._say('')
        self._say('=' * 52)
        self._say('將清除的 demo 資料' + ('（--dry-run，不會實際刪除）' if dry else ''))
        self._say('=' * 52)
        for label, n in counts:
            mark = '  ' if n else '- '
            self._say(f'{mark}{label}：{n} 筆')
        self._say('=' * 52)
        self._say(f'  合計 {total} 筆')

        if total == 0:
            self._say('沒有找到 demo 資料，不需清除。', self.style.WARNING)
            return
        if dry:
            self._say('--dry-run：未刪除任何資料。', self.style.WARNING)
            return

        if not options['noinput']:
            answer = input('\n確定刪除以上資料？輸入 yes 繼續：')
            if answer.strip().lower() != 'yes':
                self._say('已取消，未刪除任何資料。', self.style.WARNING)
                return

        # 先收集要一併刪掉的實體檔案（FileField 刪 model 不會刪檔案）
        files = [s.file for s in Score.objects.filter(
            pk__in=list(part_scores.values_list('pk', flat=True))
                   + list(full_scores.values_list('pk', flat=True))) if s.file]

        with transaction.atomic():
            for label, qs in plan:
                n, _ = qs.delete()
                if n:
                    self._say(f'  已刪除 {label}')

        removed = 0
        for f in files:
            try:
                f.delete(save=False)
                removed += 1
            except Exception as e:  # 檔案不存在或被佔用，不影響資料庫已完成的刪除
                self.stderr.write(self.style.WARNING(f'  樂譜檔案刪除失敗（{f.name}）：{e}'))

        self._say('')
        self._say(f'demo 資料已清除，另刪除 {removed} 個樂譜檔案。', self.style.SUCCESS)

        pc = PaymentConfig.objects.filter(pk=1).first()
        if pc and pc.bank_code == '822' and pc.account_number == '1234567890123':
            self._say(
                '注意：轉帳收款設定仍是 demo 假帳號（822 / 1234567890123），'
                '屬單例設定未自動清除，請自行更新為正確帳戶或清空。', self.style.WARNING)
