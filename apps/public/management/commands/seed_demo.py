"""
manage.py seed_demo
===================
建立展示用的 demo 資料（團員、演出與排練、樂譜、財產、財務會費、待審項目）。

全部使用 get_or_create，可重複執行不會產生重複資料。
只新增、不刪除、不修改既有資料。清除請用 `manage.py clear_demo`。

使用方式：
    python manage.py seed_demo
    python manage.py seed_demo --no-files   # 不產生 QR 圖檔與樂譜 PDF

資料內容與 demo 動線見 _notes/DEMO.md。
"""

import datetime as dt
import io
from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import (
    InstrumentFamily, InstrumentType, Registration, SectionType, User,
)
from apps.announcements.models import Announcement
from apps.assets.models import AssetBorrow, BandProperty
from apps.events.models import (
    LeaveRequest, PerformanceEvent, PerformanceLeaveRequest, Rehearsal,
    RehearsalAttendance, Setlist,
)
from apps.finance.models import FeePeriod, FinanceRecord, MembershipFee, PaymentConfig
from apps.public.models import Venue
from apps.scores.models import Score

# ── demo 資料的識別依據（clear_demo 依這些常數反向清除，兩者務必同步）──────

DEMO_USERNAME_PREFIX = 'demo_'
DEMO_PASSWORD = 'demo1234'
DEMO_EVENT_NAME = '2026 秋季公演「聲之所向」'
DEMO_FEE_PERIOD = (2026, 'second')

DEMO_OFFICER = ('demo_officer', '陳品妤', '小號', '第一部', 2018, '0912-345-678')

DEMO_MEMBERS = [
    ('demo_flute1', '林宜蓁', '長笛', '第一部', 2022, '0911-111-001'),
    ('demo_flute2', '黃郁婷', '長笛', '第二部', 2023, '0911-111-002'),
    ('demo_oboe', '張家豪', '雙簧管', '第一部', 2021, '0911-111-003'),
    ('demo_clar1', '李承恩', '豎笛', '第一部', 2020, '0911-111-004'),
    ('demo_clar2', '吳孟儒', '豎笛', '第二部', 2022, '0911-111-005'),
    ('demo_clar3', '蔡佩君', '豎笛', '第三部', 2024, '0911-111-006'),
    ('demo_sax', '鄭羽軒', '薩克斯風', '第一部', 2019, '0911-111-007'),
    ('demo_bsn', '許雅涵', '低音管', '第一部', 2023, '0911-111-008'),
    ('demo_tpt', '謝宗翰', '小號', '第二部', 2021, '0911-111-009'),
    ('demo_horn', '劉思妤', '法國號', '第一部', 2020, '0911-111-010'),
    ('demo_tbn', '王柏勳', '長號', '第一部', 2024, '0911-111-011'),
    ('demo_perc', '洪詩涵', '打擊樂', 'Solo', 2025, '0911-111-012'),
]

DEMO_SCORE_TITLES = [
    'Festive Overture', 'First Suite in E-flat', 'Danzón No. 2',
    '宝島', '台灣民謠組曲', 'Blue Shades',
]

DEMO_ASSET_NAMES = [
    'YAMAHA YBB-201 低音號', 'YAMAHA YEP-201 上低音號', '定音鼓四顆一組',
    'Bb 豎笛（備用）', '打擊小物收納箱', '鋁製譜架 ×30', '主動式喇叭一對',
    '無線麥克風組', '團員制服（男 20／女 20）', '指揮台',
]

DEMO_FINANCE_DESCRIPTIONS = [
    '校友會年度贊助', '春季音樂會售票收入', '7/15 排練場地費', '7/22 排練場地費',
    '7/29 排練場地費', '7 月指揮鐘點費', '購入 Danzón No. 2 全套譜',
    '定音鼓鼓皮更換', '備用 Bb 豎笛一支', '演出海報印刷',
]

DEMO_ANNOUNCEMENT_TITLES = [
    '秋季公演售票開始', '8/12 排練改至大排練室', '團服尺寸調查',
    '幹部會議紀錄（8月）', '【草稿】年度團員大會通知',
]

DEMO_REGISTRATION_EMAILS = [
    'chou.tzuhan@example.com', 'lai.weiting@example.com',
    'chien.liwen@example.com', 'tseng.chienlin@example.com',
]

_PART_INSTRUMENTS = ['長笛', '雙簧管', 'Bb 豎笛', '中音薩克斯風',
                     '小號', '法國號', '長號', '打擊樂']


def _minimal_pdf(title, subtitle):
    """不依賴 reportlab，手工組一個單頁合法 PDF 當示意樂譜。"""
    def esc(s):
        return s.replace('\\', r'\\').replace('(', r'\(').replace(')', r'\)')

    content = (
        f"BT /F1 24 Tf 60 700 Td ({esc(title)}) Tj ET\n"
        f"BT /F1 13 Tf 60 670 Td ({esc(subtitle)}) Tj ET\n"
        f"BT /F1 10 Tf 60 640 Td (FJCWO demo file - not a real score) Tj ET\n"
    )
    for i in range(10):
        y = 600 - i * 12
        content += f"1 w 60 {y} m 540 {y} l S\n"

    objs = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(content)} >>\nstream\n{content}endstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = "%PDF-1.4\n"
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{body}\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n"
    out += (f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_at}\n%%EOF\n")
    return out.encode('latin-1', errors='replace')


class Command(BaseCommand):
    help = '建立展示用的 demo 資料（可重複執行）'

    def add_arguments(self, parser):
        parser.add_argument('--no-files', action='store_true',
                            help='不產生轉帳 QR 圖檔與樂譜 PDF')

    def _say(self, msg, style=None):
        """verbosity=0 時完全靜音（測試呼叫時不要污染測試輸出）。"""
        if self.verbosity:
            self.stdout.write(style(msg) if style else msg)

    def handle(self, *args, **options):
        self.verbosity = options.get('verbosity', 1)
        self.fam = {f.name: f for f in InstrumentFamily.objects.all()}
        self.sec = {s.name: s for s in SectionType.objects.all()}
        self.itype = {i.name: i for i in InstrumentType.objects.all()}

        if not self.fam or not self.sec:
            self.stderr.write(self.style.ERROR(
                '找不到樂器族群或聲部主檔，請先依 SETUP.md 步驟六載入 fixtures。'))
            return

        rehearsal_venue = Venue.objects.filter(type=Venue.Type.REHEARSAL).first()
        concert_venue = Venue.objects.filter(type=Venue.Type.PERFORMANCE).first()
        if not rehearsal_venue or not concert_venue:
            self.stderr.write(self.style.ERROR(
                '找不到場地主檔，請先載入 venues fixture。'))
            return

        self.log = []
        officer = self._seed_accounts()
        members = self._seed_members()
        event, rehearsals = self._seed_event(officer, rehearsal_venue, concert_venue)
        self._seed_attendance(members, rehearsals)
        self._seed_leaves(officer, event, rehearsals)
        self._seed_registrations()
        full_scores = self._seed_scores()
        self._seed_setlist(event, full_scores)
        assets = self._seed_assets(officer)
        self._seed_borrows(assets)
        self._seed_finance(officer, event)
        self._seed_fees(officer, members)
        self._seed_announcements(officer)
        if not options['no_files']:
            self._seed_files()

        self._say('')
        self._say('=' * 58, self.style.SUCCESS)
        self._say('DEMO 資料建立完成', self.style.SUCCESS)
        self._say('=' * 58, self.style.SUCCESS)
        for line in self.log:
            self._say(f'  - {line}')
        self._say('=' * 58, self.style.SUCCESS)
        self._say(f'  幹部帳號：{DEMO_OFFICER[0]}／團員 {len(members)} 位（demo_*）')
        self._say(f'  密碼統一：{DEMO_PASSWORD}')
        self._say('  demo 動線與注意事項見 _notes/DEMO.md')
        self._say('=' * 58, self.style.SUCCESS)

    # ── 各區塊 ───────────────────────────────────────────────

    def _make_user(self, uname, name, inst, section, grad, phone, role):
        u, created = User.objects.get_or_create(
            username=uname,
            defaults=dict(name=name, email=f'{uname}@fjcwo.test', role=role,
                          instrument=self.fam[inst], section=self.sec[section],
                          grad_year=grad, phone=phone),
        )
        if created:
            u.set_password(DEMO_PASSWORD)
            u.save()
        return u, created

    def _seed_accounts(self):
        officer, created = self._make_user(*DEMO_OFFICER, role=User.Role.OFFICER)
        self.log.append(f'幹部帳號 {DEMO_OFFICER[0]} {"建立" if created else "已存在"}')
        return officer

    def _seed_members(self):
        members, new = [], 0
        for row in DEMO_MEMBERS:
            u, created = self._make_user(*row, role=User.Role.MEMBER)
            members.append(u)
            new += created
        self.log.append(f'團員 {len(members)} 位（新建 {new}）')
        return members

    def _seed_event(self, officer, rehearsal_venue, concert_venue):
        def aware(y, m, d, hh, mm=0):
            return timezone.make_aware(dt.datetime(y, m, d, hh, mm))

        event, created = PerformanceEvent.objects.get_or_create(
            name=DEMO_EVENT_NAME,
            defaults=dict(type=PerformanceEvent.Type.CONCERT,
                          performance_date=aware(2026, 10, 18, 19, 30),
                          performance_venue=concert_venue,
                          status=PerformanceEvent.Status.CONFIRMED),
        )
        self.log.append(f'演出活動「{DEMO_EVENT_NAME}」{"建立" if created else "已存在"}')

        spec = [
            (1, aware(2026, 7, 15, 19, 0), '總奏第一次視譜，全曲跑過一輪',
             '銅管音量壓過木管，附點節奏不齊', '第 2、4 首分部練習'),
            (2, aware(2026, 7, 22, 19, 0), '分部練習：木管 A 段、銅管 C 段',
             '豎笛群音準偏高', '合奏前先對音'),
            (3, aware(2026, 7, 29, 19, 0), '第 1、3 首合奏，打擊加入',
             '定音鼓進場點不明確', '加強第 3 首尾段'),
            (4, aware(2026, 8, 5, 19, 0), '全曲連奏，指揮加入表情處理',
             '曲間銜接太趕', '練習曲間換譜與站位'),
            (5, aware(2026, 8, 12, 19, 0), '', '', ''),
            (6, aware(2026, 8, 19, 19, 0), '', '', ''),
            (7, aware(2026, 8, 26, 19, 0), '', '', ''),
        ]
        rehearsals = {}
        for seq, when, prog, improve, nxt in spec:
            r, _ = Rehearsal.objects.get_or_create(
                event=event, sequence=seq,
                defaults=dict(date=when, venue=rehearsal_venue,
                              summary_progress=prog, summary_improve=improve,
                              summary_next=nxt, summary_by=officer if prog else None),
            )
            rehearsals[seq] = r
        self.log.append(f'排練 {len(rehearsals)} 場（第 5 次留給 QR 簽到 demo）')
        return event, rehearsals

    def _seed_attendance(self, members, rehearsals):
        pattern = {
            1: {'demo_clar3': 'absent', 'demo_tbn': 'leave'},
            2: {'demo_flute2': 'leave', 'demo_perc': 'absent'},
            3: {'demo_oboe': 'leave'},
            4: {'demo_clar2': 'absent', 'demo_sax': 'leave', 'demo_horn': 'leave'},
        }
        n = 0
        for seq in (1, 2, 3, 4):
            r = rehearsals[seq]
            for u in members:
                st = pattern[seq].get(u.username, 'present')
                _, created = RehearsalAttendance.objects.get_or_create(
                    rehearsal=r, member=u,
                    defaults=dict(status=st,
                                  checked_in_at=r.date if st == 'present' else None),
                )
                n += created
        self.log.append(f'出席紀錄新建 {n} 筆（第 1–4 次排練）')

    def _seed_leaves(self, officer, event, rehearsals):
        spec = [
            ('demo_clar1', 6, '當天有研究所面試，需南下一天，無法出席。', 'pending'),
            ('demo_tpt', 6, '公司臨時排班，晚上七點才下班趕不及。', 'pending'),
            ('demo_perc', 7, '家中長輩住院需要陪同就醫。', 'pending'),
            ('demo_tbn', 1, '感冒發燒，避免傳染給大家。', 'approved'),
            ('demo_sax', 4, '學校期末專題發表彩排。', 'approved'),
        ]
        n = 0
        for uname, seq, reason, status in spec:
            u = User.objects.filter(username=uname).first()
            if not u:
                continue
            _, created = LeaveRequest.objects.get_or_create(
                member=u, rehearsal=rehearsals[seq],
                defaults=dict(reason=reason, status=status,
                              reviewed_by=officer if status != 'pending' else None,
                              reviewed_at=timezone.now() if status != 'pending' else None,
                              result_seen=True),
            )
            n += created
        self.log.append(f'排練請假新建 {n} 筆（3 筆待審）')

        u = User.objects.filter(username='demo_flute2').first()
        if u:
            _, created = PerformanceLeaveRequest.objects.get_or_create(
                member=u, event=event,
                defaults=dict(reason='演出當天為家人婚禮，無法出席整場演出。',
                              status='pending'),
            )
            self.log.append(f'演出請假待審 {"新建 1 筆" if created else "已存在"}'
                            f'（註：附錄五 #13-6 已決議廢除此功能）')

    def _seed_registrations(self):
        spec = [
            ('周子涵', '長笛', 2019, '0922-333-101', DEMO_REGISTRATION_EMAILS[0]),
            ('賴威廷', '小號', 2017, '0922-333-102', DEMO_REGISTRATION_EMAILS[1]),
            ('簡俐雯', 'Bb 豎笛', 2021, '0922-333-103', DEMO_REGISTRATION_EMAILS[2]),
            ('曾建霖', '打擊樂', 2016, '0922-333-104', DEMO_REGISTRATION_EMAILS[3]),
        ]
        n = 0
        for name, inst, grad, phone, email in spec:
            _, created = Registration.objects.get_or_create(
                email=email,
                defaults=dict(name=name, instrument=self.itype[inst], grad_year=grad,
                              phone=phone, status=Registration.Status.PENDING),
            )
            n += created
        self.log.append(f'校友報到待審新建 {n} 筆')

    def _seed_scores(self):
        meta = {
            'Festive Overture': ('D. Shostakovich', 'D. Hunsberger', 'copyrighted', 'advanced'),
            'First Suite in E-flat': ('G. Holst', '', 'public_domain', 'intermediate'),
            'Danzón No. 2': ('A. Márquez', 'O. Nickel', 'copyrighted', 'advanced'),
            '宝島': ('和泉宏隆', '真島俊夫', 'licensed', 'intermediate'),
            '台灣民謠組曲': ('傳統民謠', '李哲藝', 'licensed', 'beginner'),
            'Blue Shades': ('F. Ticheli', '', 'copyrighted', 'advanced'),
        }
        full_scores, n = [], 0
        for title in DEMO_SCORE_TITLES:
            comp, arr, cr, diff = meta[title]
            s, created = Score.objects.get_or_create(
                title=title, score_type=Score.ScoreType.FULL,
                defaults=dict(composer=comp, arranger=arr, copyright_status=cr,
                              difficulty=diff, physical_quantity=1,
                              source=Score.Source.PURCHASED,
                              publisher='Hal Leonard' if cr == 'copyrighted' else ''),
            )
            full_scores.append(s)
            n += created
            for iname in _PART_INSTRUMENTS:
                _, pc = Score.objects.get_or_create(
                    title=f'{title} — {iname}分譜', score_type=Score.ScoreType.PART,
                    defaults=dict(composer=comp, arranger=arr, copyright_status=cr,
                                  instrument=self.itype[iname], full_score=s,
                                  physical_quantity=4),
                )
                n += pc
        self.log.append(f'樂譜新建 {n} 筆（{len(DEMO_SCORE_TITLES)} 首總譜 × '
                        f'{len(_PART_INSTRUMENTS)} 種分譜）')
        return full_scores

    def _seed_setlist(self, event, full_scores):
        n = 0
        for i, s in enumerate(full_scores[:5], start=1):
            _, created = Setlist.objects.get_or_create(
                event=event, score=s, defaults=dict(order=i))
            n += created
        self.log.append(f'演出曲目新建 {n} 首')

    def _seed_assets(self, officer):
        spec = [
            ('YAMAHA YBB-201 低音號', 'instrument', dt.date(2019, 3, 12), 185000, 'good', '團庫 A 櫃'),
            ('YAMAHA YEP-201 上低音號', 'instrument', dt.date(2019, 3, 12), 96000, 'good', '團庫 A 櫃'),
            ('定音鼓四顆一組', 'instrument', dt.date(2017, 9, 1), 320000, 'needs_maintenance', '排練室'),
            ('Bb 豎笛（備用）', 'instrument', dt.date(2021, 6, 20), 28000, 'in_repair', '送修中'),
            ('打擊小物收納箱', 'instrument', dt.date(2020, 1, 15), 15000, 'good', '團庫 B 櫃'),
            ('鋁製譜架 ×30', 'stand', dt.date(2018, 8, 5), 24000, 'good', '排練室角落'),
            ('主動式喇叭一對', 'audio', dt.date(2022, 4, 18), 42000, 'good', '團庫 C 櫃'),
            ('無線麥克風組', 'audio', dt.date(2022, 4, 18), 18000, 'good', '團庫 C 櫃'),
            ('團員制服（男 20／女 20）', 'uniform', dt.date(2023, 9, 10), 120000, 'good', '團庫衣櫃'),
            ('指揮台', 'other', dt.date(2018, 8, 5), 8000, 'good', '排練室'),
        ]
        assets, n = {}, 0
        for name, cat, pdate, cost, cond, loc in spec:
            a, created = BandProperty.objects.get_or_create(
                name=name,
                defaults=dict(category=cat, purchase_date=pdate,
                              purchase_cost=Decimal(cost), condition=cond,
                              storage_location=loc, contact_person=officer),
            )
            assets[name] = a
            n += created
        self.log.append(f'公用財產新建 {n} 樣')
        return assets

    def _seed_borrows(self, assets):
        spec = [
            ('YAMAHA YEP-201 上低音號', 'demo_tbn', dt.date(2026, 7, 20), dt.date(2026, 8, 3), None),
            ('Bb 豎笛（備用）', 'demo_clar3', dt.date(2026, 8, 8), dt.date(2026, 8, 22), None),
            ('無線麥克風組', 'demo_perc', dt.date(2026, 8, 10), dt.date(2026, 8, 20), None),
            ('鋁製譜架 ×30', 'demo_horn', dt.date(2026, 6, 1), dt.date(2026, 6, 15), dt.date(2026, 6, 14)),
        ]
        n = 0
        for aname, uname, bdate, due, returned in spec:
            u = User.objects.filter(username=uname).first()
            if not u:
                continue
            _, created = AssetBorrow.objects.get_or_create(
                asset=assets[aname], borrower=u, borrowed_at=bdate,
                defaults=dict(due_date=due, returned_at=returned),
            )
            n += created
        self.log.append(f'借用紀錄新建 {n} 筆（含 1 筆逾期）')

    def _seed_finance(self, officer, event):
        spec = [
            ('income', 'other', 30000, dt.date(2026, 3, 5), DEMO_FINANCE_DESCRIPTIONS[0]),
            ('income', 'other', 12000, dt.date(2026, 5, 20), DEMO_FINANCE_DESCRIPTIONS[1]),
            ('expense', 'venue', 8000, dt.date(2026, 7, 15), DEMO_FINANCE_DESCRIPTIONS[2]),
            ('expense', 'venue', 8000, dt.date(2026, 7, 22), DEMO_FINANCE_DESCRIPTIONS[3]),
            ('expense', 'venue', 8000, dt.date(2026, 7, 29), DEMO_FINANCE_DESCRIPTIONS[4]),
            ('expense', 'instructor', 15000, dt.date(2026, 7, 31), DEMO_FINANCE_DESCRIPTIONS[5]),
            ('expense', 'score', 6800, dt.date(2026, 6, 10), DEMO_FINANCE_DESCRIPTIONS[6]),
            ('expense', 'instrument_maintenance', 4500, dt.date(2026, 8, 1), DEMO_FINANCE_DESCRIPTIONS[7]),
            ('expense', 'instrument_purchase', 28000, dt.date(2026, 6, 20), DEMO_FINANCE_DESCRIPTIONS[8]),
            ('expense', 'other', 3200, dt.date(2026, 8, 6), DEMO_FINANCE_DESCRIPTIONS[9]),
        ]
        n = 0
        for t, cat, amt, d, desc in spec:
            _, created = FinanceRecord.objects.get_or_create(
                description=desc,
                defaults=dict(type=t, category=cat, amount=Decimal(amt), date=d,
                              created_by=officer,
                              related_event=event if '排練場地費' in desc else None),
            )
            n += created
        self.log.append(f'財務收支新建 {n} 筆')

    def _seed_fees(self, officer, members):
        p1 = FeePeriod.objects.filter(year=2026, term='first').first()
        p2, created = FeePeriod.objects.get_or_create(
            year=DEMO_FEE_PERIOD[0], term=DEMO_FEE_PERIOD[1],
            defaults=dict(amount=Decimal(1200), start_date=dt.date(2026, 8, 1),
                          end_date=dt.date(2026, 9, 30), created_by=officer),
        )
        self.log.append(f'會費期別 2026 下期 {"建立" if created else "已存在"}')

        n = 0
        if p1:
            for u in members[:8]:
                mf, c = MembershipFee.objects.get_or_create(
                    member=u, period=p1,
                    defaults=dict(amount=p1.amount, status=MembershipFee.Status.PAID,
                                  payment_method=MembershipFee.PaymentMethod.CASH,
                                  paid_at=dt.date(2026, 3, 15), collected_by=officer),
                )
                if c:
                    mf.finance_record = FinanceRecord.objects.create(
                        type='income', category='membership', amount=p1.amount,
                        date=mf.paid_at, description=f'{u.name} 2026 上期會費',
                        created_by=officer)
                    mf.save()
                    n += 1

        for u, method, last5 in [
            (members[0], 'cash', ''), (members[1], 'cash', ''),
            (members[2], 'transfer', '48213'), (members[3], 'transfer', '90627'),
        ]:
            _, c = MembershipFee.objects.get_or_create(
                member=u, period=p2,
                defaults=dict(amount=p2.amount, status=MembershipFee.Status.REPORTED,
                              payment_method=method, account_last5=last5,
                              collected_by=officer if method == 'cash' else None),
            )
            n += c
        for u in members[4:7]:
            mf, c = MembershipFee.objects.get_or_create(
                member=u, period=p2,
                defaults=dict(amount=p2.amount, status=MembershipFee.Status.PAID,
                              payment_method='cash', paid_at=dt.date(2026, 8, 5),
                              collected_by=officer),
            )
            if c:
                mf.finance_record = FinanceRecord.objects.create(
                    type='income', category='membership', amount=p2.amount,
                    date=mf.paid_at, description=f'{u.name} 2026 下期會費',
                    created_by=officer)
                mf.save()
                n += 1
        self.log.append(f'會費紀錄新建 {n} 筆（4 筆待確認：2 現金 + 2 轉帳）')

        pc, _ = PaymentConfig.objects.get_or_create(pk=1)
        if not pc.bank_code:
            pc.bank_code = '822'
            pc.bank_name = '中國信託商業銀行'
            pc.account_name = '輔仁大學百韻管樂團'
            pc.account_number = '1234567890123'
            pc.save()
            self.log.append('轉帳收款設定已填入 demo 假帳號')

    def _seed_announcements(self, officer):
        spec = [
            (DEMO_ANNOUNCEMENT_TITLES[0],
             '2026 秋季公演「聲之所向」10/18 於新莊文化藝術中心演出，即日起開放索票。',
             'public', dt.date(2026, 10, 18), True),
            (DEMO_ANNOUNCEMENT_TITLES[1],
             '因小排練室冷氣維修，今晚排練改至一樓大排練室，請團員直接前往。',
             'member_only', dt.date(2026, 8, 12), True),
            (DEMO_ANNOUNCEMENT_TITLES[2],
             '請尚未回報團服尺寸的團員於 8/20 前私訊總務，逾期以預設尺寸製作。',
             'member_only', dt.date(2026, 8, 20), True),
            (DEMO_ANNOUNCEMENT_TITLES[3],
             '討論事項：秋季公演分工、會費催繳、樂譜採購預算。',
             'officer_only', dt.date(2026, 8, 9), True),
            (DEMO_ANNOUNCEMENT_TITLES[4],
             '時間地點確認中，尚未發布。', 'member_only', None, False),
        ]
        n = 0
        for title, content, vis, edate, published in spec:
            _, created = Announcement.objects.get_or_create(
                title=title,
                defaults=dict(content=content, visibility=vis, event_date=edate,
                              created_by=officer,
                              published_at=timezone.now() if published else None),
            )
            n += created
        self.log.append(f'公告新建 {n} 則（含 1 則草稿、1 則幹部限定）')

    def _seed_files(self):
        import qrcode

        pc = PaymentConfig.objects.filter(pk=1).first()
        if pc and not pc.qrcode and pc.bank_code:
            payload = (f'BANK:{pc.bank_code} {pc.bank_name}\n'
                       f'ACCOUNT:{pc.account_number}\nNAME:{pc.account_name}')
            buf = io.BytesIO()
            qrcode.make(payload).save(buf, format='PNG')
            pc.qrcode.save('fjcwo_payment_qr.png', ContentFile(buf.getvalue()), save=True)
            self.log.append('轉帳收款 QR 圖檔已產生')

        n = 0
        for s in Score.objects.filter(score_type=Score.ScoreType.FULL, file=''):
            s.file.save(f'demo_full_{s.pk}.pdf',
                        ContentFile(_minimal_pdf(s.title, f'Full Score / {s.composer}')),
                        save=True)
            n += 1
        for s in Score.objects.filter(score_type=Score.ScoreType.PART, file='').select_related('instrument'):
            inst = s.instrument.name if s.instrument else 'Part'
            s.file.save(f'demo_part_{s.pk}.pdf',
                        ContentFile(_minimal_pdf(s.title.split(' — ')[0], f'Part: {inst}')),
                        save=True)
            n += 1
        if n:
            self.log.append(f'樂譜示意 PDF 產生 {n} 份')
