from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import InstrumentType, SectionType, User
from .models import Score


class ScoreModelValidationTest(TestCase):
    """Score.clean() 驗證邏輯"""

    def setUp(self):
        self.instrument = InstrumentType.objects.create(
            name='長笛', category=InstrumentType.Category.WOODWIND
        )
        self.section = SectionType.objects.create(name='第一聲部')

    # ── T01 總譜驗證 ─────────────────────────────────────────

    def test_full_score_with_instrument_raises(self):
        """總譜指定樂器應拋出 ValidationError"""
        score = Score(
            title='測試總譜',
            score_type=Score.ScoreType.FULL,
            instrument=self.instrument,
        )
        with self.assertRaises(ValidationError):
            score.clean()

    def test_full_score_with_section_raises(self):
        """總譜指定聲部應拋出 ValidationError"""
        score = Score(
            title='測試總譜',
            score_type=Score.ScoreType.FULL,
            section=self.section,
        )
        with self.assertRaises(ValidationError):
            score.clean()

    def test_full_score_without_instrument_passes(self):
        """總譜不指定樂器應通過驗證"""
        score = Score(title='測試總譜', score_type=Score.ScoreType.FULL)
        score.clean()  # 不應拋出例外

    # ── T02 分譜驗證 ─────────────────────────────────────────

    def test_part_score_without_instrument_raises(self):
        """分譜未指定樂器應拋出 ValidationError"""
        score = Score(title='測試分譜', score_type=Score.ScoreType.PART)
        with self.assertRaises(ValidationError):
            score.clean()

    def test_part_score_with_instrument_passes(self):
        """分譜指定樂器應通過驗證"""
        score = Score(
            title='測試分譜',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
        )
        score.clean()  # 不應拋出例外


class ScoreListViewTest(TestCase):
    """樂譜庫存列表頁面"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='score_member',
            email='score@test.local',
            password='testpass123',
            name='樂譜測試員',
            role=User.Role.MEMBER,
        )
        self.instrument = InstrumentType.objects.create(
            name='單簧管', category=InstrumentType.Category.WOODWIND
        )
        self.full_score = Score.objects.create(
            title='天空之城', score_type=Score.ScoreType.FULL
        )
        self.part_score = Score.objects.create(
            title='天空之城（單簧管）',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
        )
        self.url = reverse('scores:score_list')

    # ── T01 存取控制 ────────────────────────────────────────

    def test_unauthenticated_redirects(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_authenticated_can_view(self):
        """登入後可看到樂譜列表"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    # ── T02 列表顯示 ─────────────────────────────────────────

    def test_list_shows_all_scores_by_default(self):
        """預設顯示所有樂譜"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '天空之城')

    def test_filter_by_full_type(self):
        """type=full 只顯示總譜，不顯示分譜"""
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'type': 'full'})
        self.assertContains(r, '天空之城')
        self.assertNotContains(r, '天空之城（單簧管）')

    def test_filter_by_part_type(self):
        """type=part 只顯示分譜"""
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'type': 'part'})
        self.assertContains(r, '天空之城（單簧管）')
        self.assertNotContains(r, self.full_score.title + '</td>')

    def test_filter_by_instrument(self):
        """instrument 篩選只顯示對應樂器的分譜"""
        self.client.force_login(self.member)
        r = self.client.get(self.url, {
            'type': 'part',
            'instrument': self.instrument.pk,
        })
        self.assertContains(r, '天空之城（單簧管）')

    def test_search_by_title(self):
        """q 參數依曲名搜尋"""
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'q': '天空'})
        self.assertContains(r, '天空之城')

    def test_search_no_match_shows_empty(self):
        """搜尋無結果時顯示提示"""
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'q': '完全不存在的曲名xyz'})
        self.assertContains(r, '沒有符合條件的樂譜')


class ScoreDetailViewTest(TestCase):
    """樂譜詳情頁面"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='score_detail_member',
            email='scoredetail@test.local',
            password='testpass123',
            name='詳情測試員',
            role=User.Role.MEMBER,
        )
        self.score = Score.objects.create(
            title='卡門組曲',
            score_type=Score.ScoreType.FULL,
            composer='比才',
        )
        self.url = reverse('scores:score_detail', args=[self.score.pk])

    # ── T03 存取控制 ────────────────────────────────────────

    def test_unauthenticated_redirects(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_authenticated_can_view(self):
        """登入後可看到樂譜詳情"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_detail_shows_title_and_composer(self):
        """詳情頁顯示曲名與作曲家"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '卡門組曲')
        self.assertContains(r, '比才')

    def test_detail_404_on_invalid_pk(self):
        """不存在的樂譜 pk 應回 404"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('scores:score_detail', args=[99999]))
        self.assertEqual(r.status_code, 404)

    def test_no_pdf_shows_placeholder(self):
        """無 PDF 時顯示提示文字"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '無數位版本')


class ScoreDownloadViewTest(TestCase):
    """樂譜 PDF 下載保護"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='dl_member',
            email='dl@test.local',
            password='testpass123',
            name='下載測試員',
            role=User.Role.MEMBER,
        )
        self.score_no_file = Score.objects.create(
            title='無檔案總譜', score_type=Score.ScoreType.FULL
        )
        self.download_url = reverse('scores:score_download', args=[self.score_no_file.pk])

    def test_unauthenticated_redirects(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.download_url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_no_file_returns_404(self):
        """無 PDF 的樂譜應回 404"""
        self.client.force_login(self.member)
        r = self.client.get(self.download_url)
        self.assertEqual(r.status_code, 404)

    def test_invalid_pk_returns_404(self):
        """不存在的樂譜 pk 應回 404"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('scores:score_download', args=[99999]))
        self.assertEqual(r.status_code, 404)
