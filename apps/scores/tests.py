from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import InstrumentFamily, User
from apps.events.models import EventPartFolder, PerformanceEvent, Setlist
from apps.public.models import Venue

from .models import Score, ScoreExchange, ScoreExchangeItem, normalize_drive_url

DRIVE = 'https://drive.google.com/drive/folders/archive'
PARTS = 'https://drive.google.com/drive/folders/archive-parts'


def make_users():
    """建立一般團員／幹部／管理員各一，回傳 (member, officer, admin)。"""
    return tuple(
        User.objects.create_user(
            username=f'sc_{role}', email=f'sc_{role}@test.local', password='x',
            name=f'樂譜{role}', role=role,
        )
        for role in (User.Role.MEMBER, User.Role.OFFICER, User.Role.ADMIN)
    )


def make_event(name='春季音樂會', days=-10, status=PerformanceEvent.Status.CONFIRMED):
    """建立演出活動。days < 0 代表已演出（過去），> 0 代表即將演出。"""
    venue, _ = Venue.objects.get_or_create(name='樂譜測試場地', defaults={'type': 'performance'})
    return PerformanceEvent.objects.create(
        name=name, type='concert', performance_date=timezone.now() + timedelta(days=days),
        performance_venue=venue, status=status,
    )


class ScoreModelTest(TestCase):
    """藏譜 Model：藏譜資料夾必填、分譜資料夾與版權選填、連結限 Google、顯示名稱含版本"""

    def _errors(self, **kw):
        try:
            Score(**kw).full_clean()
            return {}
        except ValidationError as e:
            return e.message_dict

    def test_minimal_valid(self):
        """只要曲名＋藏譜資料夾就合法（版權、分譜資料夾等皆選填）"""
        self.assertEqual(self._errors(title='星空', drive_url=DRIVE), {})

    def test_drive_url_required(self):
        self.assertIn('drive_url', self._errors(title='星空'))

    def test_urls_only_accept_google_https(self):
        for bad in ('http://drive.google.com/x', 'https://example.com/x',
                    'https://drive.google.com.evil.com/x'):
            self.assertIn('drive_url', self._errors(title='星空', drive_url=bad))
            self.assertIn('parts_url', self._errors(title='星空', drive_url=DRIVE, parts_url=bad))

    def test_is_cut_follows_parts_url(self):
        self.assertFalse(Score(title='a', drive_url=DRIVE).is_cut)
        self.assertTrue(Score(title='a', drive_url=DRIVE, parts_url=PARTS).is_cut)

    def test_str_includes_arranger_and_version(self):
        """同曲名不同版本靠編曲者與版本說明區分"""
        self.assertEqual(str(Score(title='天空之城')), '天空之城')
        self.assertEqual(str(Score(title='天空之城', arranger='真島俊夫')), '天空之城（真島俊夫 編）')
        self.assertEqual(str(Score(title='天空之城', arranger='真島俊夫', version_note='縮編版')),
                         '天空之城（真島俊夫 編、縮編版）')
        self.assertEqual(str(Score(title='天空之城', version_note='縮編版')), '天空之城（縮編版）')


class NormalizeDriveUrlTest(TestCase):
    """連結整理：拿掉瀏覽器帳號編號 `/u/數字/`，其餘原樣"""

    FOLDER = 'https://drive.google.com/drive/folders/1NRe9zK0V9qRBe0OODwchLwySF88LX1JS'

    def test_strips_account_index_from_folder_url(self):
        self.assertEqual(
            normalize_drive_url('https://drive.google.com/drive/u/1/folders/1NRe9zK0V9qRBe0OODwchLwySF88LX1JS'),
            self.FOLDER,
        )

    def test_strips_any_account_number_and_other_paths(self):
        self.assertEqual(
            normalize_drive_url('https://docs.google.com/document/u/0/d/abc/edit'),
            'https://docs.google.com/document/d/abc/edit',
        )
        self.assertEqual(
            normalize_drive_url('https://drive.google.com/drive/u/12/folders/xyz'),
            'https://drive.google.com/drive/folders/xyz',
        )

    def test_keeps_query_and_unrelated_u_segments(self):
        """查詢參數保留；`/u/` 後面不是數字的路徑（例如檔案 id 剛好含 u）不誤刪"""
        self.assertEqual(
            normalize_drive_url('https://drive.google.com/drive/u/1/folders/abc?usp=sharing'),
            'https://drive.google.com/drive/folders/abc?usp=sharing',
        )
        self.assertEqual(
            normalize_drive_url('https://drive.google.com/file/d/uuu1/view'),
            'https://drive.google.com/file/d/uuu1/view',
        )

    def test_already_clean_and_whitespace(self):
        self.assertEqual(normalize_drive_url('  ' + self.FOLDER + '  '), self.FOLDER)
        self.assertEqual(normalize_drive_url(self.FOLDER), self.FOLDER)
        self.assertEqual(normalize_drive_url(''), '')

    def test_non_google_url_is_left_alone_for_validator_to_reject(self):
        """外站網址不動（含其中的 /u/1/），交給 validate_drive_url 擋掉"""
        self.assertEqual(normalize_drive_url('https://evil.example.com/u/1/x'), 'https://evil.example.com/u/1/x')

    def test_model_save_normalizes_any_entry_path(self):
        """從 Admin 或程式直接 save 也會整理（安全網）"""
        score = Score.objects.create(
            title='星空',
            drive_url='https://drive.google.com/drive/u/1/folders/abc',
            parts_url='https://drive.google.com/drive/u/2/folders/abc-parts',
        )
        score.refresh_from_db()
        self.assertEqual(score.drive_url, 'https://drive.google.com/drive/folders/abc')
        self.assertEqual(score.parts_url, 'https://drive.google.com/drive/folders/abc-parts')


class ScoreAccessTest(TestCase):
    """樂譜庫存（藏譜）整個限幹部：團員被導回首頁並顯示權限不足，未登入導向登入頁"""

    def setUp(self):
        self.member, self.officer, _ = make_users()
        self.score = Score.objects.create(title='星空', drive_url=DRIVE)
        self.urls = [
            reverse('scores:score_list'),
            reverse('scores:score_create'),
            reverse('scores:score_detail', args=[self.score.pk]),
            reverse('scores:score_edit', args=[self.score.pk]),
        ]

    def test_unauthenticated_redirects_to_login(self):
        for url in self.urls:
            r = self.client.get(url)
            self.assertEqual(r.status_code, 302)
            self.assertIn('/accounts/login/', r['Location'])

    def test_member_denied(self):
        self.client.force_login(self.member)
        for url in self.urls:
            r = self.client.get(url, follow=True)
            self.assertRedirects(r, reverse('public:index'))
            self.assertContains(r, '權限不足')

    def test_member_cannot_create_by_post(self):
        self.client.force_login(self.member)
        self.client.post(reverse('scores:score_create'), {'title': '偷建', 'drive_url': DRIVE})
        self.assertFalse(Score.objects.filter(title='偷建').exists())

    def test_officer_can_view(self):
        self.client.force_login(self.officer)
        for url in self.urls:
            self.assertEqual(self.client.get(url).status_code, 200)

    def test_nav_link_only_for_officer(self):
        """導覽列的「樂譜庫存」只出現在幹部畫面"""
        link = f'href="{reverse("scores:score_list")}"'
        self.client.force_login(self.member)
        self.assertNotContains(self.client.get(reverse('public:index')), link)
        self.client.force_login(self.officer)
        self.assertContains(self.client.get(reverse('public:index')), link)


class ScoreListViewTest(TestCase):
    """藏譜列表：搜尋、篩選（演出／是否切割）、演出標籤與次數、排序、待辦卡片、刪除按鈕"""

    def setUp(self):
        self.member, self.officer, self.admin = make_users()
        self.cut = Score.objects.create(title='天空之城', arranger='真島俊夫', drive_url=DRIVE, parts_url=PARTS)
        self.uncut = Score.objects.create(title='星空', composer='某作曲', drive_url=DRIVE)
        self.past = make_event('輔韻之聲', days=-30)
        self.past2 = make_event('冬季音樂會', days=-5)
        Setlist.objects.create(event=self.past, score=self.uncut, order=1)
        Setlist.objects.create(event=self.past2, score=self.uncut, order=1)
        self.url = reverse('scores:score_list')
        self.client.force_login(self.officer)

    def test_search_by_title_composer_arranger(self):
        self.assertEqual(list(self.client.get(self.url, {'q': '真島'}).context['scores']), [self.cut])
        self.assertEqual(list(self.client.get(self.url, {'q': '某作曲'}).context['scores']), [self.uncut])
        self.assertEqual(list(self.client.get(self.url, {'q': '天空'}).context['scores']), [self.cut])

    def test_filter_cut(self):
        self.assertEqual(list(self.client.get(self.url, {'cut': 'yes'}).context['scores']), [self.cut])
        self.assertEqual(list(self.client.get(self.url, {'cut': 'no'}).context['scores']), [self.uncut])

    def test_filter_by_event(self):
        r = self.client.get(self.url, {'event': self.past.pk})
        self.assertEqual(list(r.context['scores']), [self.uncut])
        # 亂填的參數不應 500，視同不篩
        self.assertEqual(self.client.get(self.url, {'event': 'abc'}).status_code, 200)

    def test_tags_and_count_shown(self):
        """每場演出一個標籤（年月日＋名稱），並顯示演出次數"""
        r = self.client.get(self.url)
        self.assertContains(r, self.past.tag)
        self.assertContains(r, self.past2.tag)
        self.assertContains(r, '演出 2 次')

    def test_count_excludes_cancelled_and_upcoming_and_dedupes(self):
        """次數只算已演出：取消的不算、即將演出的不算、同一場重複列只算一次"""
        Setlist.objects.create(event=self.past, score=self.uncut, order=2)  # 同場重複（安可）
        Setlist.objects.create(event=make_event('取消場', days=-3, status=PerformanceEvent.Status.CANCELLED),
                               score=self.uncut, order=1)
        upcoming = make_event('明年場', days=30)
        Setlist.objects.create(event=upcoming, score=self.uncut, order=1)
        r = self.client.get(self.url)
        row = next(s for s in r.context['scores'] if s.pk == self.uncut.pk)
        self.assertEqual(row.performance_count, 2)
        self.assertNotContains(r, '取消場')
        self.assertContains(r, upcoming.tag)  # 即將演出的仍顯示標籤（空心）

    def test_sort_by_count(self):
        r = self.client.get(self.url, {'sort': 'count'})
        self.assertEqual(list(r.context['scores']), [self.uncut, self.cut])

    def test_uncut_performed_todo_card(self):
        """演過但沒有分譜資料夾的藏譜列在待辦卡片；已切割的不列"""
        r = self.client.get(self.url)
        self.assertContains(r, '已演出但尚未歸檔分譜')
        self.assertEqual(list(r.context['uncut_performed']), [self.uncut])

    def test_upcoming_only_not_in_todo(self):
        """只排進未來演出的藏譜還沒演過，不列入待辦"""
        Setlist.objects.all().delete()
        Setlist.objects.create(event=make_event('明年場', days=30), score=self.uncut, order=1)
        r = self.client.get(self.url)
        self.assertEqual(list(r.context['uncut_performed']), [])

    def test_unarchived_card(self):
        """曲目單裡未入藏的特例曲目列給幹部追蹤"""
        Setlist.objects.create(event=self.past, unarchived_title='借來的曲子',
                               unarchived_reason='向友團借譜', order=9)
        r = self.client.get(self.url)
        self.assertContains(r, '未入藏的演出曲目')
        self.assertContains(r, '借來的曲子')
        self.assertContains(r, '向友團借譜')

    def test_delete_button_admin_only(self):
        delete_url = reverse('scores:score_delete', args=[self.cut.pk])
        self.assertNotContains(self.client.get(self.url), delete_url)
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(self.url), delete_url)


class ScoreDetailViewTest(TestCase):
    """藏譜詳情：資料夾連結（已切割時分譜最顯眼）、基本資料、演出紀錄"""

    def setUp(self):
        _, self.officer, _ = make_users()
        self.client.force_login(self.officer)

    def test_cut_score_shows_parts_and_archive(self):
        score = Score.objects.create(title='天空之城', drive_url=DRIVE, parts_url=PARTS)
        r = self.client.get(reverse('scores:score_detail', args=[score.pk]))
        self.assertContains(r, f'href="{PARTS}"')
        self.assertContains(r, f'href="{DRIVE}"')
        self.assertContains(r, '切割好的分譜')
        self.assertContains(r, 'rel="noopener noreferrer"')

    def test_uncut_score_shows_archive_and_hint(self):
        score = Score.objects.create(title='星空', drive_url=DRIVE)
        r = self.client.get(reverse('scores:score_detail', args=[score.pk]))
        self.assertContains(r, f'href="{DRIVE}"')
        self.assertContains(r, '尚未有切割好的分譜')

    def test_shows_performance_tags(self):
        score = Score.objects.create(title='星空', drive_url=DRIVE)
        event = make_event('輔韻之聲')
        Setlist.objects.create(event=event, score=score, order=1)
        r = self.client.get(reverse('scores:score_detail', args=[score.pk]))
        self.assertContains(r, event.tag)
        self.assertContains(r, '演出 1 次')
        self.assertContains(r, reverse('events:event_detail', args=[event.pk]))

    def test_invalid_pk_404(self):
        self.assertEqual(self.client.get(reverse('scores:score_detail', args=[99999])).status_code, 404)


class ScoreCreateEditViewTest(TestCase):
    """新增／編輯藏譜：必填欄位、連結驗證與整理、重複提醒"""

    def setUp(self):
        _, self.officer, _ = make_users()
        self.client.force_login(self.officer)
        self.create_url = reverse('scores:score_create')

    def test_create_minimal(self):
        """只填曲名與藏譜資料夾即可建立（版權可不選）"""
        r = self.client.post(self.create_url, {'title': '星空', 'drive_url': DRIVE})
        score = Score.objects.get(title='星空')
        self.assertRedirects(r, reverse('scores:score_detail', args=[score.pk]), fetch_redirect_response=False)
        self.assertEqual(score.copyright_status, '')

    def test_create_without_drive_url_rejected(self):
        r = self.client.post(self.create_url, {'title': '星空', 'drive_url': ''})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Score.objects.exists())

    def test_create_with_non_google_url_rejected(self):
        self.client.post(self.create_url, {'title': '星空', 'drive_url': 'https://example.com/x'})
        self.client.post(self.create_url, {'title': '星空', 'drive_url': DRIVE, 'parts_url': 'https://example.com/x'})
        self.assertFalse(Score.objects.exists())

    def test_create_strips_account_index(self):
        self.client.post(self.create_url, {
            'title': '星空', 'drive_url': 'https://drive.google.com/drive/u/1/folders/archive',
        })
        self.assertEqual(Score.objects.get().drive_url, DRIVE)

    def test_form_has_no_removed_fields(self):
        """改版自、實體紙本數量、譜種、樂器、所屬總譜已移除"""
        r = self.client.get(self.create_url)
        for name in ('parent_score', 'physical_quantity', 'score_type', 'instrument', 'full_score'):
            self.assertNotContains(r, f'name="{name}"')

    def test_duplicate_warns_but_saves(self):
        """同曲名＋編曲＋版本說明已存在時提醒，但仍建立"""
        Score.objects.create(title='星空', drive_url=DRIVE)
        r = self.client.post(self.create_url, {'title': '星空', 'drive_url': DRIVE}, follow=True)
        self.assertContains(r, '藏譜裡已經有')
        self.assertEqual(Score.objects.filter(title='星空').count(), 2)

    def test_different_version_no_warning(self):
        Score.objects.create(title='星空', drive_url=DRIVE)
        r = self.client.post(self.create_url, {'title': '星空', 'version_note': '縮編版', 'drive_url': DRIVE}, follow=True)
        self.assertNotContains(r, '藏譜裡已經有')

    def test_edit_prefills_and_updates(self):
        score = Score.objects.create(title='星空', drive_url=DRIVE)
        url = reverse('scores:score_edit', args=[score.pk])
        self.assertContains(self.client.get(url), f'value="{DRIVE}"')
        self.client.post(url, {'title': '星空', 'drive_url': DRIVE, 'parts_url': PARTS, 'version_note': '新版'})
        score.refresh_from_db()
        self.assertEqual((score.parts_url, score.version_note), (PARTS, '新版'))

    def test_edit_invalid_does_not_save(self):
        score = Score.objects.create(title='星空', drive_url=DRIVE)
        self.client.post(reverse('scores:score_edit', args=[score.pk]), {'title': '', 'drive_url': DRIVE})
        score.refresh_from_db()
        self.assertEqual(score.title, '星空')


class ScoreDeleteViewTest(TestCase):
    """刪除藏譜：限管理員；被曲目單或交換紀錄引用時擋下"""

    def setUp(self):
        _, self.officer, self.admin = make_users()
        self.score = Score.objects.create(title='星空', drive_url=DRIVE)
        self.url = reverse('scores:score_delete', args=[self.score.pk])

    def test_officer_cannot_delete(self):
        self.client.force_login(self.officer)
        self.client.post(self.url)
        self.assertTrue(Score.objects.filter(pk=self.score.pk).exists())

    def test_admin_can_delete(self):
        self.client.force_login(self.admin)
        r = self.client.post(self.url)
        self.assertRedirects(r, reverse('scores:score_list'), fetch_redirect_response=False)
        self.assertFalse(Score.objects.filter(pk=self.score.pk).exists())

    def test_blocked_by_setlist(self):
        Setlist.objects.create(event=make_event(), score=self.score, order=1)
        self.client.force_login(self.admin)
        self.client.post(self.url)
        self.assertTrue(Score.objects.filter(pk=self.score.pk).exists())

    def test_blocked_by_exchange(self):
        ex = ScoreExchange.objects.create(other_band='友團', exchange_date=timezone.localdate())
        ScoreExchangeItem.objects.create(exchange=ex, direction='give', score=self.score)
        self.client.force_login(self.admin)
        self.client.post(self.url)
        self.assertTrue(Score.objects.filter(pk=self.score.pk).exists())


class PerformancePartsViewTest(TestCase):
    """
    演出分譜下載（/scores/performance/<pk>/parts/）。
    團員：只看到自己族群的資料夾（C），看不到總譜（A）、典藏與其他族群；
    幹部：總譜、典藏與所有族群。
    """

    CONDUCTOR = 'https://drive.google.com/drive/folders/conductor'
    ARCHIVE = 'https://drive.google.com/drive/folders/concert-archive'
    FLUTE = 'https://drive.google.com/drive/folders/flute'
    BRASS = 'https://drive.google.com/drive/folders/trumpet'

    def setUp(self):
        self.flute = InstrumentFamily.objects.create(name='長笛族', category='woodwind')
        self.trumpet = InstrumentFamily.objects.create(name='小號族', category='brass')
        self.member, self.officer, _ = make_users()
        self.member.instrument = self.flute
        self.member.save()
        self.event = make_event(days=10)
        self.event.conductor_folder_url = self.CONDUCTOR
        self.event.archive_folder_url = self.ARCHIVE
        self.event.save()
        EventPartFolder.objects.create(event=self.event, family=self.flute, drive_url=self.FLUTE)
        EventPartFolder.objects.create(event=self.event, family=self.trumpet, drive_url=self.BRASS)
        self.url = reverse('scores:performance_parts', args=[self.event.pk])

    def test_unauthenticated_redirects(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_invalid_event_404(self):
        self.client.force_login(self.member)
        r = self.client.get(reverse('scores:performance_parts', args=[99999]))
        self.assertEqual(r.status_code, 404)

    def test_member_sees_only_own_family_folder(self):
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, f'href="{self.FLUTE}"')
        for hidden in (self.BRASS, self.CONDUCTOR, self.ARCHIVE):
            self.assertNotContains(r, hidden)

    def test_member_without_family_sees_hint(self):
        self.member.instrument = None
        self.member.save()
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '尚未設定樂器族群')
        self.assertNotContains(r, self.FLUTE)

    def test_member_family_without_folder_sees_message(self):
        EventPartFolder.objects.filter(family=self.flute).delete()
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '還沒準備好')
        self.assertNotContains(r, self.BRASS)

    def test_officer_sees_conductor_archive_and_all_families(self):
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        for link in (self.CONDUCTOR, self.ARCHIVE, self.FLUTE, self.BRASS):
            self.assertContains(r, f'href="{link}"')
        self.assertContains(r, reverse('events:score_folders_manage', args=[self.event.pk]))
