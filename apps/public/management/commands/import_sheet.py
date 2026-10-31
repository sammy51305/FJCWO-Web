"""
manage.py import_sheet
======================
把「團練紀錄」Google 試算表（系統上線前的暫用紀錄）匯入系統。

試算表 → 檔案 → 下載 → Microsoft Excel (.xlsx)，再執行：

    python manage.py import_sheet 團練紀錄.xlsx --operator <幹部帳號>            # 試跑，不寫入
    python manage.py import_sheet 團練紀錄.xlsx --operator <幹部帳號> --commit   # 確認無誤後真的寫入

各分頁的對應（欄位定義見試算表的「說明」分頁，設計見 DESIGN.md §4.23）：

| 分頁 | 寫入 | 對照依據 |
|------|------|---------|
| 團員名冊 | 沒有帳號的人 → `Registration`（待審核） | Email，其次姓名 |
| 排練日程 | `Rehearsal` | 排練日期（一天一場） |
| 出席紀錄 | `RehearsalAttendance` | 團員 × 排練日期 |
| 請假紀錄 | `LeaveRequest`（核准者同步出席為請假） | 團員 × 排練日期 |
| 團費期別 | `FeePeriod` | 年份 × 期 |
| 團費收繳 | `MembershipFee`（已繳者同步收支明細收入） | 團員 × 期別 |
| 支出紀錄 | `FinanceRecord`（支出） | 日期 × 金額 × 說明 |

**不直接建帳號**：DESIGN §4.2 訂了「Registration 是帳號怎麼來的唯一紀錄」，所以名冊裡
沒有帳號的人只會變成待審核的入團申請，由幹部在「入團申請審核」頁批次核准（會寄臨時密碼信）。
那些人在其他分頁的資料這次會被略過並列在報告裡——**核准後再跑一次本指令即可補進來**。

**可重複執行**：每筆都以對照依據 get_or_create，已存在的紀錄一律不覆蓋
（上線後以系統為準，試算表不應回頭蓋掉系統裡的修改）。

**預設試跑**：沒加 `--commit` 時整批在 transaction 裡做完再 rollback，
報告內容與真的匯入完全相同，可以放心先看結果。
"""

import datetime as dt
import re
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.views import _import_registration_rows
from apps.events.models import (
    LeaveRequest, PerformanceEvent, Rehearsal, RehearsalAttendance,
)
from apps.finance.models import FeePeriod, FinanceRecord, MembershipFee
from apps.finance.views import _sync_fee_income
from apps.public.models import Venue

SHEET_ROSTER = '團員名冊'
SHEET_REHEARSALS = '排練日程'
SHEET_ATTENDANCE = '出席紀錄'
SHEET_LEAVES = '請假紀錄'
SHEET_PERIODS = '團費期別'
SHEET_FEES = '團費收繳'
SHEET_EXPENSES = '支出紀錄'

# 各分頁必須有的標題。試算表範本改了欄位名稱就整份拒絕，不要猜著對位
_REQUIRED_HEADERS = {
    SHEET_ROSTER: ('姓名', 'Email'),
    SHEET_REHEARSALS: ('排練日期', '開始時間', '場地', '所屬演出', '第幾次排練'),
    SHEET_LEAVES: ('申請時間', '姓名', '排練日期', '請假原因', '審核狀態', '審核幹部', '審核時間'),
    SHEET_PERIODS: ('年份', '期', '團費金額', '繳費開始日', '繳費截止日'),
    SHEET_FEES: ('姓名', '期別', '實收金額', '繳費方式', '帳號末五碼', '繳費日期', '收款幹部', '狀態'),
    SHEET_EXPENSES: ('日期', '項目', '金額', '說明', '經手人'),
}

# 試算表「收支」分頁的預算項目 → 系統收支明細的分類。系統分類比較粗（團練室與場地費同屬
# 場地費），所以描述一律寫成「項目：說明」，原本的預算項目不會因此消失。
# 對不上的項目歸「其他」並列入報告，不擋匯入——錢確實花了，帳不能漏。
_EXPENSE_CATEGORY = {
    '場地費': FinanceRecord.Category.VENUE,
    '團練室': FinanceRecord.Category.VENUE,
    '指揮費用': FinanceRecord.Category.INSTRUCTOR,
    '樂譜': FinanceRecord.Category.SCORE,
    '架站與伺服器費': FinanceRecord.Category.OTHER,
    '開發網站': FinanceRecord.Category.OTHER,      # 舊名，改名前填的支出紀錄仍認得
    '宣傳': FinanceRecord.Category.OTHER,
    '音樂會錄音錄影': FinanceRecord.Category.OTHER,
    '工作人員': FinanceRecord.Category.OTHER,
    '大型樂器': FinanceRecord.Category.OTHER,
}

# 出席紀錄是矩陣：第 1 列從 G 欄起是排練日期，第 5 列起每列一位團員（A 欄姓名）
_ATTENDANCE_FIRST_DATE_COL = 7
_ATTENDANCE_FIRST_MEMBER_ROW = 5

_ATTENDANCE_STATUS = {
    '出席': RehearsalAttendance.Status.PRESENT,
    '請假': RehearsalAttendance.Status.LEAVE,
    '缺席': RehearsalAttendance.Status.ABSENT,
}
_LEAVE_STATUS = {
    '待審核': LeaveRequest.Status.PENDING,
    '核准': LeaveRequest.Status.APPROVED,
    '拒絕': LeaveRequest.Status.REJECTED,
}
_FEE_STATUS = {
    '待確認': MembershipFee.Status.REPORTED,
    '已繳': MembershipFee.Status.PAID,
    '作廢': MembershipFee.Status.VOID,
}
_PAYMENT_METHOD = {
    '現金': MembershipFee.PaymentMethod.CASH,
    '轉帳': MembershipFee.PaymentMethod.TRANSFER,
}
_TERM = {'上期': FeePeriod.Term.FIRST, '下期': FeePeriod.Term.SECOND}
_PERIOD_LABEL_RE = re.compile(r'^\s*(\d{4})\s*(上期|下期)\s*$')

_DATE_FORMATS = ('%Y/%m/%d', '%Y-%m-%d', '%Y.%m.%d')
_DATETIME_FORMATS = ('%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M', '%Y/%m/%d %H:%M:%S', '%Y-%m-%d %H:%M:%S')
# Excel／Sheets 的日期序號起點（序號 1 = 1899/12/31，沿用 Lotus 1-2-3 的閏年錯誤所以是 12/30）
_SERIAL_EPOCH = dt.datetime(1899, 12, 30)


class _Rollback(Exception):
    """試跑模式用來丟棄整個 transaction。"""


# ── 儲存格值轉換 ────────────────────────────────────────────────


def _text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def _to_datetime(value):
    """儲存格值 → naive datetime；認不得回傳 None。

    openpyxl 對有日期格式的格子會直接給 datetime，但格式被改掉的格子會變成序號或字串，三種都要收。
    """
    if value is None or value == '':
        return None
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time())
    if isinstance(value, (int, float)):
        return _SERIAL_EPOCH + dt.timedelta(days=float(value))
    text = str(value).strip()
    for fmt in _DATETIME_FORMATS + _DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _to_date(value):
    moment = _to_datetime(value)
    return moment.date() if moment else None


def _to_time(value):
    if value is None or value == '':
        return None
    if isinstance(value, dt.time):
        return value
    if isinstance(value, dt.datetime):
        return value.time()
    if isinstance(value, (int, float)):      # 時間序號是一天的比例
        return (_SERIAL_EPOCH + dt.timedelta(days=float(value) % 1)).time()
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return dt.datetime.strptime(str(value).strip(), fmt).time()
        except ValueError:
            continue
    return None


def _aware(moment):
    return timezone.make_aware(moment, timezone.get_current_timezone())


def _to_amount(value):
    if value is None or value == '':
        return None
    try:
        amount = int(float(str(value).replace(',', '')))
    except ValueError:
        return None
    return amount if amount > 0 else None


def _read_table(ws):
    """一般分頁：第 1 列是標題，回傳 [(列號, {標題: 值})]，跳過整列空白。"""
    rows = ws.iter_rows(values_only=True)
    try:
        header = [_text(h) for h in next(rows)]
    except StopIteration:
        return [], []
    table = []
    for row_no, values in enumerate(rows, start=2):
        # 勾選框欄位（如支出紀錄的「收據」）沒勾也有值 FALSE，整片空白列都會帶著它，
        # 所以 False 視同空白，否則每一列空白都會被當成資料、報一堆「日期無法辨識」
        if not any(v is not False and _text(v) for v in values):
            continue
        table.append((row_no, {h: values[i] if i < len(values) else None
                               for i, h in enumerate(header) if h}))
    return header, table


class Command(BaseCommand):
    help = '把「團練紀錄」試算表（下載成 .xlsx）匯入系統。預設試跑，加 --commit 才寫入。'

    def add_arguments(self, parser):
        parser.add_argument('xlsx', help='從 Google 試算表下載的 .xlsx 檔')
        parser.add_argument('--operator', required=True,
                            help='執行匯入的幹部帳號（username），記為收支紀錄的登記者等')
        parser.add_argument('--commit', action='store_true', help='真的寫入（沒加就是試跑）')
        parser.add_argument('--default-time', default='19:00',
                            help='排練日程沒填開始時間時用的時間（預設 19:00）')

    # ── 進入點 ─────────────────────────────────────────────────

    def handle(self, *args, **opts):
        try:
            import openpyxl
        except ImportError:
            raise CommandError('缺少 openpyxl，請先執行 pip install -r requirements.txt')

        self.operator = User.objects.filter(username=opts['operator']).first()
        if self.operator is None:
            raise CommandError(f'找不到帳號「{opts["operator"]}」。')
        if not self.operator.is_officer:
            raise CommandError(f'「{opts["operator"]}」不是幹部，不能執行匯入。')
        self.default_time = _to_time(opts['default_time'])
        if self.default_time is None:
            raise CommandError('--default-time 格式要像 19:00。')

        try:
            wb = openpyxl.load_workbook(opts['xlsx'], data_only=True, read_only=True)
        except FileNotFoundError:
            raise CommandError(f'找不到檔案：{opts["xlsx"]}')
        except Exception as exc:     # 檔案壞掉或不是 xlsx，openpyxl 丟的例外種類很多
            raise CommandError(f'無法讀取 {opts["xlsx"]}：{exc}')

        self.sheets = {}
        for name in (SHEET_ROSTER, SHEET_REHEARSALS, SHEET_ATTENDANCE,
                     SHEET_LEAVES, SHEET_PERIODS, SHEET_FEES, SHEET_EXPENSES):
            if name in wb.sheetnames:
                self.sheets[name] = wb[name]
            else:
                self.stdout.write(self.style.WARNING(f'找不到「{name}」分頁，略過。'))
        for name, required in _REQUIRED_HEADERS.items():
            if name not in self.sheets:
                continue
            header, _ = _read_table(self.sheets[name])
            missing = [h for h in required if h not in header]
            if missing:
                raise CommandError(
                    f'「{name}」分頁缺少欄位：{"、".join(missing)}。請確認用的是原本的試算表範本、沒有改過欄位名稱。'
                )

        self.report = []         # [(分頁, 新增數, 已存在數, [問題…])]
        try:
            with transaction.atomic():
                self._run()
                if not opts['commit']:
                    raise _Rollback
        except _Rollback:
            pass
        self._print_report(committed=opts['commit'])

    def _run(self):
        self.members = self._import_roster()
        self.rehearsals = self._import_rehearsals()
        # 出席先於請假：核准的請假要同步出席狀態（比照系統審核頁的行為）
        self._import_attendance()
        self._import_leaves()
        self.periods = self._import_periods()
        self._import_fees()
        self._import_expenses()

    # ── 共用查詢 ───────────────────────────────────────────────

    def _member(self, name):
        """姓名 → (User 或 None, 找不到的原因)。名冊比對過的結果優先，其次直接查系統。"""
        name = _text(name)
        if not name:
            return None, '缺姓名'
        if name in self.members:
            user = self.members[name]
            return (user, '') if user else (None, f'{name} 尚無系統帳號（入團申請核准後再匯入一次）')
        found = list(User.objects.filter(name=name)[:2])
        if len(found) == 1:
            return found[0], ''
        if found:
            return None, f'系統裡有不只一位「{name}」，無法判斷是誰'
        return None, f'系統與名冊都沒有「{name}」'

    def _rehearsal(self, day):
        """日期 → (Rehearsal 或 None, 原因)。一天一場是試算表的規則，同一天兩場就無法對照。"""
        if day in self.rehearsals:
            return self.rehearsals[day], ''
        found = list(Rehearsal.objects.filter(date__date=day)[:2])
        if len(found) == 1:
            self.rehearsals[day] = found[0]
            return found[0], ''
        if found:
            return None, f'系統裡 {day:%Y/%m/%d} 有不只一場排練，無法判斷是哪一場'
        return None, f'系統沒有 {day:%Y/%m/%d} 的排練（請先在排練日程填這一天）'

    # ── 各分頁 ─────────────────────────────────────────────────

    def _import_roster(self):
        """回傳 {姓名: User 或 None}，供其他分頁對照。沒有帳號、有 Email 的人建成入團申請。"""
        members = {}
        if SHEET_ROSTER not in self.sheets:
            return members
        _, table = _read_table(self.sheets[SHEET_ROSTER])
        problems, matched, to_register = [], 0, []
        by_email = {
            u.email.lower(): u for u in User.objects.exclude(email=None).exclude(email='')
        }
        for row_no, row in table:
            name = _text(row.get('姓名'))
            email = _text(row.get('Email')).lower()
            if not name:
                problems.append(f'第 {row_no} 列：缺姓名')
                continue
            if name in members:
                problems.append(f'第 {row_no} 列：姓名「{name}」重複，其他分頁無法分辨是誰（同名請加註）')
                continue
            user = by_email.get(email) if email else None
            if user is None:
                found = list(User.objects.filter(name=name)[:2])
                user = found[0] if len(found) == 1 else None
            members[name] = user
            if user:
                matched += 1
            elif email:
                to_register.append({
                    'name': name, 'email': email,
                    'phone': _text(row.get('手機')), 'line_id': _text(row.get('LINE ID')),
                    'instrument': _text(row.get('樂器')),
                })
            else:
                problems.append(f'第 {row_no} 列：{name} 沒有帳號也沒有 Email，無法建立入團申請')

        result = _import_registration_rows(to_register)
        for label, note in result['created']:
            if note:
                problems.append(f'{label}：已建入團申請，但{note}')
        for label, reason in result['skipped']:
            problems.append(f'{label}：未建入團申請（{reason}）')
        self.report.append((
            f'{SHEET_ROSTER}（新增＝新建的入團申請，請到「入團申請審核」核准；已存在＝已有帳號）',
            len(result['created']), matched, problems,
        ))
        return members

    def _import_rehearsals(self):
        rehearsals = {}
        if SHEET_REHEARSALS not in self.sheets:
            return rehearsals
        _, table = _read_table(self.sheets[SHEET_REHEARSALS])
        problems, created, existing = [], 0, 0
        for row_no, row in table:
            day = _to_date(row.get('排練日期'))
            if day is None:
                problems.append(f'第 {row_no} 列：排練日期無法辨識')
                continue
            if day in rehearsals:
                problems.append(f'第 {row_no} 列：{day:%Y/%m/%d} 重複（一天只能一場）')
                continue
            found = list(Rehearsal.objects.filter(date__date=day)[:2])
            if found:
                if len(found) == 1:
                    rehearsals[day] = found[0]
                existing += 1
                continue

            event_name = _text(row.get('所屬演出'))
            event = PerformanceEvent.objects.filter(name=event_name).first() if event_name else None
            if event is None:
                problems.append(
                    f'第 {row_no} 列：所屬演出「{event_name or "（空白）"}」在系統找不到，請先在系統建立演出活動'
                )
                continue
            venue_name = _text(row.get('場地'))
            venue = Venue.objects.filter(name=venue_name).first() if venue_name else None
            if venue is None:
                problems.append(
                    f'第 {row_no} 列：場地「{venue_name or "（空白）"}」在系統找不到，請先在系統建立場地'
                )
                continue

            start = _to_time(row.get('開始時間')) or self.default_time
            sequence_raw = _text(row.get('第幾次排練'))
            if sequence_raw:
                if not sequence_raw.isdigit():
                    problems.append(f'第 {row_no} 列：第幾次排練「{sequence_raw}」不是數字')
                    continue
                sequence = int(sequence_raw)
                if event.rehearsals.filter(sequence=sequence).exists():
                    problems.append(f'第 {row_no} 列：「{event}」已經有第 {sequence} 次排練')
                    continue
            else:
                sequence = (event.rehearsals.aggregate(m=Max('sequence'))['m'] or 0) + 1

            rehearsals[day] = Rehearsal.objects.create(
                event=event, venue=venue, sequence=sequence,
                date=_aware(dt.datetime.combine(day, start)),
                summary_progress=_text(row.get('今日進度')),
                summary_notes=_text(row.get('備註')),
            )
            created += 1
        self.report.append((SHEET_REHEARSALS, created, existing, problems))
        return rehearsals

    def _import_attendance(self):
        if SHEET_ATTENDANCE not in self.sheets:
            return
        grid = list(self.sheets[SHEET_ATTENDANCE].iter_rows(values_only=True))
        if not grid:
            return
        problems, created, existing = [], 0, 0

        member_rows = grid[_ATTENDANCE_FIRST_MEMBER_ROW - 1:]
        columns = []        # [(欄索引, Rehearsal)]
        for col in range(_ATTENDANCE_FIRST_DATE_COL - 1, len(grid[0])):
            cell = grid[0][col]
            if cell in (None, ''):
                continue
            # 日期欄通常整季先排好、還沒點名；沒有任何點名的欄位不必對照，也不該報錯
            if not any(col < len(v) and _text(v[col]) for v in member_rows):
                continue
            day = _to_date(cell)
            if day is None:
                problems.append(f'第 1 列第 {col + 1} 欄：排練日期「{_text(cell)}」無法辨識')
                continue
            rehearsal, reason = self._rehearsal(day)
            if rehearsal is None:
                problems.append(f'{day:%m/%d} 這一欄整欄略過：{reason}')
                continue
            columns.append((col, rehearsal))

        for row_no, values in enumerate(member_rows,
                                        start=_ATTENDANCE_FIRST_MEMBER_ROW):
            name = _text(values[0]) if values else ''
            marks = [(r, _text(values[c])) for c, r in columns if c < len(values) and _text(values[c])]
            if not name or not marks:
                continue
            member, reason = self._member(name)
            if member is None:
                problems.append(f'第 {row_no} 列：{reason}')
                continue
            for rehearsal, mark in marks:
                status = _ATTENDANCE_STATUS.get(mark)
                if status is None:
                    problems.append(f'第 {row_no} 列 {name}：狀態「{mark}」不是出席／請假／缺席')
                    continue
                att, was_created = RehearsalAttendance.objects.get_or_create(
                    rehearsal=rehearsal, member=member, defaults={'status': status},
                )
                if was_created:
                    created += 1
                else:
                    existing += 1
                    if att.status != status:
                        problems.append(
                            f'{name} {timezone.localtime(rehearsal.date):%m/%d}：系統已是「{att.get_status_display()}」，'
                            f'試算表是「{mark}」，未覆蓋'
                        )
        self.report.append((SHEET_ATTENDANCE, created, existing, problems))

    def _import_leaves(self):
        if SHEET_LEAVES not in self.sheets:
            return
        _, table = _read_table(self.sheets[SHEET_LEAVES])
        problems, created, existing = [], 0, 0
        for row_no, row in table:
            member, reason = self._member(row.get('姓名'))
            if member is None:
                problems.append(f'第 {row_no} 列：{reason}')
                continue
            day = _to_date(row.get('排練日期'))
            if day is None:
                problems.append(f'第 {row_no} 列：排練日期無法辨識')
                continue
            rehearsal, reason = self._rehearsal(day)
            if rehearsal is None:
                problems.append(f'第 {row_no} 列：{reason}')
                continue
            status_text = _text(row.get('審核狀態')) or '待審核'
            status = _LEAVE_STATUS.get(status_text)
            if status is None:
                problems.append(f'第 {row_no} 列：審核狀態「{status_text}」不是待審核／核准／拒絕')
                continue
            reason_text = _text(row.get('請假原因'))
            if not reason_text:
                problems.append(f'第 {row_no} 列：缺請假原因')
                continue

            reviewer, reviewed_at = None, None
            if status != LeaveRequest.Status.PENDING:
                reviewer_name = _text(row.get('審核幹部'))
                reviewer = self._member(reviewer_name)[0] if reviewer_name else None
                reviewer = reviewer or self.operator
                moment = _to_datetime(row.get('審核時間'))
                reviewed_at = _aware(moment) if moment else timezone.now()

            leave, was_created = LeaveRequest.objects.get_or_create(
                member=member, rehearsal=rehearsal,
                defaults={'reason': reason_text, 'status': status,
                          'reviewed_by': reviewer, 'reviewed_at': reviewed_at},
            )
            if not was_created:
                existing += 1
                continue
            created += 1
            applied = _to_datetime(row.get('申請時間'))
            if applied:   # created_at 是 auto_now_add，只能建立後再補
                LeaveRequest.objects.filter(pk=leave.pk).update(created_at=_aware(applied))
            if status == LeaveRequest.Status.APPROVED:
                # 比照系統審核頁：核准 → 出席標為請假，但已簽到（出席）的不覆寫
                att, _ = RehearsalAttendance.objects.get_or_create(
                    rehearsal=rehearsal, member=member,
                    defaults={'status': RehearsalAttendance.Status.LEAVE},
                )
                if att.status == RehearsalAttendance.Status.ABSENT:
                    att.status = RehearsalAttendance.Status.LEAVE
                    att.save(update_fields=['status'])
        self.report.append((SHEET_LEAVES, created, existing, problems))

    def _import_periods(self):
        periods = {}
        if SHEET_PERIODS not in self.sheets:
            return periods
        _, table = _read_table(self.sheets[SHEET_PERIODS])
        problems, created, existing = [], 0, 0
        for row_no, row in table:
            year_text = _text(row.get('年份'))
            term = _TERM.get(_text(row.get('期')))
            amount = _to_amount(row.get('團費金額'))
            if not year_text.isdigit() or term is None:
                problems.append(f'第 {row_no} 列：年份或期無法辨識')
                continue
            if amount is None:
                problems.append(f'第 {row_no} 列：團費金額要是正整數')
                continue
            period, was_created = FeePeriod.objects.get_or_create(
                year=int(year_text), term=term,
                defaults={'amount': amount,
                          'start_date': _to_date(row.get('繳費開始日')),
                          'end_date': _to_date(row.get('繳費截止日')),
                          'created_by': self.operator},
            )
            periods[(period.year, period.term)] = period
            if was_created:
                created += 1
            else:
                existing += 1
                if period.amount != amount:
                    problems.append(
                        f'第 {row_no} 列：系統的「{period}」金額是 {period.amount:,}，試算表是 {amount:,}，未覆蓋'
                    )
        self.report.append((SHEET_PERIODS, created, existing, problems))
        return periods

    def _period(self, label):
        match = _PERIOD_LABEL_RE.match(_text(label))
        if not match:
            return None
        key = (int(match[1]), _TERM[match[2]])
        if key not in self.periods:
            self.periods[key] = FeePeriod.objects.filter(year=key[0], term=key[1]).first()
        return self.periods[key]

    def _import_fees(self):
        if SHEET_FEES not in self.sheets:
            return
        _, table = _read_table(self.sheets[SHEET_FEES])
        problems, created, existing = [], 0, 0
        # 同一人同一期可能有一筆作廢、一筆有效（記錯重記）。系統一人一期只有一筆，
        # 所以先處理有效的那筆，作廢的排最後、遇到已存在就自然略過。
        table.sort(key=lambda item: _text(item[1].get('狀態')) == '作廢')
        unpaid = 0
        for row_no, row in table:
            # 試算表的做法是收到錢才記一列，但幹部可能先填了姓名、期別還沒收錢——狀態空白＝還沒繳。
            # 系統的「應繳未繳」是由團員 × 期別導出、不建紀錄（FeePeriod docstring），所以這種列不匯入
            if not _text(row.get('狀態')):
                unpaid += 1
                continue
            member, reason = self._member(row.get('姓名'))
            if member is None:
                problems.append(f'第 {row_no} 列：{reason}')
                continue
            period = self._period(row.get('期別'))
            if period is None:
                problems.append(f'第 {row_no} 列：期別「{_text(row.get("期別"))}」在團費期別與系統都找不到')
                continue
            status_text = _text(row.get('狀態'))
            status = _FEE_STATUS.get(status_text)
            if status is None:
                problems.append(f'第 {row_no} 列：狀態「{status_text}」不是待確認／已繳／作廢')
                continue
            method_text = _text(row.get('繳費方式')) or '現金'
            method = _PAYMENT_METHOD.get(method_text)
            if method is None:
                problems.append(f'第 {row_no} 列：繳費方式「{method_text}」不是現金／轉帳')
                continue
            last5 = _text(row.get('帳號末五碼'))
            if last5.isdigit() and len(last5) < 5:
                last5 = last5.zfill(5)      # 格式跑掉時開頭的 0 會被吃掉
            if last5 and not (last5.isdigit() and len(last5) == 5):
                problems.append(f'第 {row_no} 列：帳號末五碼「{last5}」不是 5 位數字，已留空')
                last5 = ''
            collector_name = _text(row.get('收款幹部'))
            collector = self._member(collector_name)[0] if collector_name else None
            paid_at = _to_date(row.get('繳費日期'))
            if status == MembershipFee.Status.PAID and paid_at is None:
                problems.append(f'第 {row_no} 列：已繳但沒有繳費日期，收入認列日改用今天')

            fee, was_created = MembershipFee.objects.get_or_create(
                member=member, period=period,
                defaults={'amount': _to_amount(row.get('實收金額')) or period.amount,
                          'status': status, 'payment_method': method,
                          'account_last5': last5, 'paid_at': paid_at,
                          'collected_by': collector},
            )
            if not was_created:
                existing += 1
                continue
            created += 1
            _sync_fee_income(fee, self.operator)   # 已繳 → 產生收支明細收入，與系統操作一致
        label = f'{SHEET_FEES}（狀態空白＝尚未繳費 {unpaid} 列，不匯入）' if unpaid else SHEET_FEES
        self.report.append((label, created, existing, problems))

    def _import_expenses(self):
        """支出紀錄 → FinanceRecord（支出）。

        支出沒有天然的唯一鍵，以「日期 × 金額 × 描述」對照。試算表裡可能真的有兩筆一模一樣的支出
        （同一天付兩次同樣的場地費），所以不是「有就略過」，而是**數量對齊**：
        試算表有 N 筆、系統已有 M 筆，就補建 N−M 筆。重跑時 M 追上 N，自然不再新增。
        """
        if SHEET_EXPENSES not in self.sheets:
            return
        _, table = _read_table(self.sheets[SHEET_EXPENSES])
        problems = []
        wanted = Counter()        # (日期, 金額, 描述) → 試算表裡的筆數
        categories = {}
        for row_no, row in table:
            day = _to_date(row.get('日期'))
            if day is None:
                problems.append(f'第 {row_no} 列：日期無法辨識')
                continue
            amount = _to_amount(row.get('金額'))
            if amount is None:
                problems.append(f'第 {row_no} 列：金額要是正整數')
                continue
            item = _text(row.get('項目'))
            if not item:
                problems.append(f'第 {row_no} 列：缺項目')
                continue
            category = _EXPENSE_CATEGORY.get(item)
            if category is None:
                problems.append(f'第 {row_no} 列：項目「{item}」不在預算項目裡，歸為「其他」')
                category = FinanceRecord.Category.OTHER
            note = _text(row.get('說明'))
            handler = _text(row.get('經手人'))
            description = f'{item}：{note}' if note else item
            if handler:
                description += f'（經手人：{handler}）'
            key = (day, amount, description)
            wanted[key] += 1
            categories[key] = category

        created = existing = 0
        for (day, amount, description), count in wanted.items():
            have = FinanceRecord.objects.filter(
                type=FinanceRecord.Type.EXPENSE, date=day, amount=amount, description=description,
            ).count()
            existing += min(have, count)
            for _ in range(count - have):
                FinanceRecord.objects.create(
                    type=FinanceRecord.Type.EXPENSE, category=categories[(day, amount, description)],
                    amount=amount, date=day, description=description, created_by=self.operator,
                )
                created += 1
        self.report.append((SHEET_EXPENSES, created, existing, problems))

    # ── 報告 ───────────────────────────────────────────────────

    def _print_report(self, committed):
        out = self.stdout
        out.write('')
        for sheet, created, existing, problems in self.report:
            out.write(self.style.MIGRATE_HEADING(f'■ {sheet}'))
            out.write(f'  新增 {created} 筆、已存在略過 {existing} 筆')
            for line in problems:
                out.write(self.style.WARNING(f'  ! {line}'))
        out.write('')
        if committed:
            out.write(self.style.SUCCESS('已寫入資料庫。'))
        else:
            out.write(self.style.NOTICE('這是試跑，什麼都沒寫入。確認上面的結果沒問題後，加上 --commit 再執行一次。'))
