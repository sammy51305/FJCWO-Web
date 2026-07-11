import shutil
import tempfile

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.models import InstrumentFamily, InstrumentType, SectionType, User
from .models import Score

# 測試中上傳的 PDF 存到這個暫存目錄，結束後整個目錄刪除，不會污染正式 MEDIA_ROOT
_TEMP_MEDIA = tempfile.mkdtemp()


class ScoreModelValidationTest(TestCase):
    """Score.clean() 驗證邏輯"""

    def setUp(self):
        self.family = InstrumentFamily.objects.create(
            name='長笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.instrument = InstrumentType.objects.create(
            name='長笛', family=self.family
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

    # ── T03 full_score FK 驗證 ──────────────────────────────
    # full_score 是今天新增的欄位，用於把分譜連結到它所屬的總譜。
    # clean() 對這個欄位有三條規則：
    #   1. 總譜本身不能設 full_score（總譜不可能是某個總譜的分譜）
    #   2. 分譜的 full_score 不能指向另一個分譜（只有總譜才能當父級）
    #   3. 分譜的 full_score 指向總譜是合法的

    def test_full_score_cannot_have_full_score_field_set(self):
        """
        總譜（score_type=full）若設定了 full_score FK，應拋出 ValidationError。
        情境：上傳時誤把「所屬總譜」填進一份總譜，必須擋下來。
        """
        parent = Score.objects.create(
            title='父總譜', score_type=Score.ScoreType.FULL
        )
        score = Score(
            title='子總譜',
            score_type=Score.ScoreType.FULL,
            full_score=parent,  # 總譜不應有 full_score
        )
        with self.assertRaises(ValidationError):
            score.clean()

    def test_part_full_score_pointing_to_another_part_raises(self):
        """
        分譜的 full_score 若指向另一份分譜（而非總譜），應拋出 ValidationError。
        情境：A 分譜的「所屬總譜」欄誤填成 B 分譜，必須擋下來。
        """
        another_part = Score.objects.create(
            title='其他分譜',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
        )
        score = Score(
            title='測試分譜',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
            full_score=another_part,  # full_score 應指向總譜，這裡誤指分譜
        )
        with self.assertRaises(ValidationError):
            score.clean()

    def test_part_full_score_pointing_to_full_score_passes(self):
        """
        分譜的 full_score 正確指向一份總譜時，應通過驗證（不拋出例外）。
        這是最常見的正常用法：上傳長笛分譜並掛在「星空」總譜底下。
        """
        full = Score.objects.create(
            title='星空', score_type=Score.ScoreType.FULL
        )
        score = Score(
            title='星空',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
            full_score=full,  # 正確地指向總譜
        )
        score.clean()  # 不應拋出例外

    # ── T04 __str__ 格式 ─────────────────────────────────────
    # Score.__str__ 今天調整成：分譜且有聲部時，格式為「曲名（樂器名 聲部名）」

    def test_str_part_with_instrument_only(self):
        """
        分譜只有樂器、沒有聲部時，__str__ 格式為「曲名（樂器名）」。
        例：「星空（長笛）」
        """
        score = Score(
            title='星空',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
        )
        self.assertEqual(str(score), '星空（長笛）')

    def test_str_part_with_instrument_and_section(self):
        """
        分譜同時有樂器與聲部時，__str__ 格式為「曲名（樂器名 聲部名）」。
        例：「星空（長笛 第一聲部）」
        聲部名之間用空格分隔，方便在列表和下拉選單中一眼辨識。
        """
        score = Score(
            title='星空',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
            section=self.section,
        )
        self.assertEqual(str(score), '星空（長笛 第一聲部）')

    def test_str_full_score(self):
        """
        總譜的 __str__ 只顯示曲名，不附加任何括號資訊。
        例：「星空」
        """
        score = Score(title='星空', score_type=Score.ScoreType.FULL)
        self.assertEqual(str(score), '星空')


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
        self.officer = User.objects.create_user(
            username='score_list_officer', password='x', name='列表幹部',
            email='score_list_officer@test.local', role=User.Role.OFFICER,
        )
        self.admin = User.objects.create_user(
            username='score_list_admin', password='x', name='列表管理員',
            email='score_list_admin@test.local', role=User.Role.ADMIN,
        )
        family = InstrumentFamily.objects.create(
            name='豎笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.instrument = InstrumentType.objects.create(
            name='單簧管', family=family
        )
        self.full_score = Score.objects.create(
            title='天空之城', score_type=Score.ScoreType.FULL
        )
        self.part_score = Score.objects.create(
            title='天空之城（單簧管）',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
            full_score=self.full_score,
        )
        self.unbound_part_score = Score.objects.create(
            title='孤立分譜（單簧管）',
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

    # ── T03 分譜顯示所屬總譜 ─────────────────────────────────

    def test_part_score_shows_bound_full_score(self):
        """已綁定 full_score 的分譜，列表應顯示所屬總譜名稱"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '屬於')
        self.assertContains(r, self.full_score.title)

    def test_unbound_part_score_shows_hint(self):
        """未綁定 full_score 的分譜，列表應顯示未綁定提示"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '未綁定總譜')

    # ── T04 刪除按鈕：限管理員 ───────────────────────────────

    def test_delete_form_appears_for_admin(self):
        """管理員在列表頁應看到指向 score_delete 的刪除表單"""
        self.client.force_login(self.admin)
        r = self.client.get(self.url)
        self.assertContains(r, reverse('scores:score_delete', args=[self.full_score.pk]))

    def test_delete_form_not_appears_for_officer(self):
        """一般幹部在列表頁不應看到刪除表單"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertNotContains(r, reverse('scores:score_delete', args=[self.full_score.pk]))

    def test_delete_form_not_appears_for_member(self):
        """一般團員在列表頁不應看到刪除表單"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertNotContains(r, reverse('scores:score_delete', args=[self.full_score.pk]))


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

    def test_breadcrumb_preserves_list_query_params(self):
        """
        從列表帶著篩選條件（如 ?type=full）進入詳情頁時，
        麵包屑「樂譜庫存」連結應帶回同樣的篩選條件，而不是導回無篩選的預設列表。
        """
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'type': 'full'})
        self.assertContains(r, f'{reverse("scores:score_list")}?type=full')

    def test_breadcrumb_without_query_params_links_to_plain_list(self):
        """直接進入詳情頁（沒有帶篩選條件）時，麵包屑應連回不帶查詢字串的列表頁"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, f'href="{reverse("scores:score_list")}"')


class ScoreCreateViewTest(TestCase):
    """新增樂譜頁面（/scores/create/）"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='create_member',
            email='create_member@test.local',
            password='testpass123',
            name='一般團員',
            role=User.Role.MEMBER,
        )
        self.officer = User.objects.create_user(
            username='create_officer',
            email='create_officer@test.local',
            password='testpass123',
            name='新增樂譜幹部',
            role=User.Role.OFFICER,
        )
        family = InstrumentFamily.objects.create(
            name='豎笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.instrument = InstrumentType.objects.create(name='單簧管', family=family)
        self.url = reverse('scores:score_create')

    # ── 存取控制 ────────────────────────────────────────

    def test_unauthenticated_redirects_to_login(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_member_redirects_with_error_message(self):
        """一般團員應被導回列表頁並顯示權限不足"""
        self.client.force_login(self.member)
        r = self.client.get(self.url, follow=True)
        self.assertRedirects(r, reverse('scores:score_list'))
        self.assertContains(r, '權限不足')

    def test_officer_get_returns_200(self):
        """幹部 GET 應正常顯示表單"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    # ── POST 新增總譜 ────────────────────────────────────

    def test_officer_post_creates_full_score(self):
        """幹部送出總譜資料應成功建立，並導向該樂譜詳情頁"""
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {
            'title': '天空之城',
            'score_type': Score.ScoreType.FULL,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
            'physical_quantity': '2',
        })
        score = Score.objects.get(title='天空之城')
        self.assertRedirects(r, reverse('scores:score_detail', args=[score.pk]))
        self.assertEqual(score.score_type, Score.ScoreType.FULL)
        self.assertIsNone(score.instrument)

    def test_officer_post_creates_part_score_with_instrument(self):
        """幹部送出分譜資料且有指定樂器時應成功建立"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'title': '天空之城',
            'score_type': Score.ScoreType.PART,
            'instrument': self.instrument.pk,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
        })
        score = Score.objects.get(title='天空之城', score_type=Score.ScoreType.PART)
        self.assertEqual(score.instrument, self.instrument)

    def test_empty_title_does_not_create_record(self):
        """曲名空白時 full_clean() 應擋下，不建立任何記錄"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'title': '',
            'score_type': Score.ScoreType.FULL,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
        })
        self.assertFalse(Score.objects.exists())

    def test_part_score_without_instrument_does_not_create_record(self):
        """分譜未指定樂器時 clean() 驗證應擋下，不建立任何記錄"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'title': '天空之城',
            'score_type': Score.ScoreType.PART,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
        })
        self.assertFalse(Score.objects.exists())

    # ── full_score 綁定 ──────────────────────────────────
    # 新增分譜時可直接指定所屬總譜，不再只能透過 score_parts_manage 綁定

    def test_officer_post_creates_part_score_bound_to_full_score(self):
        """新增分譜時指定 full_score，應正確綁定到該總譜"""
        full_score = Score.objects.create(title='天空之城', score_type=Score.ScoreType.FULL)
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'title': '天空之城（單簧管）',
            'score_type': Score.ScoreType.PART,
            'instrument': self.instrument.pk,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
            'full_score': full_score.pk,
        })
        part = Score.objects.get(title='天空之城（單簧管）')
        self.assertEqual(part.full_score, full_score)
        self.assertIn(part, full_score.parts.all())

    def test_full_score_ignores_full_score_field(self):
        """建立總譜時即使 POST 帶了 full_score，也應被忽略（總譜不該有所屬總譜）"""
        other_full = Score.objects.create(title='卡門', score_type=Score.ScoreType.FULL)
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'title': '天空之城',
            'score_type': Score.ScoreType.FULL,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
            'full_score': other_full.pk,
        })
        score = Score.objects.get(title='天空之城')
        self.assertIsNone(score.full_score)


@override_settings(MEDIA_ROOT=_TEMP_MEDIA)
class ScoreEditViewTest(TestCase):
    """編輯樂譜頁面（/scores/<pk>/edit/）"""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(_TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.member = User.objects.create_user(
            username='edit_member',
            email='edit_member@test.local',
            password='testpass123',
            name='一般團員',
            role=User.Role.MEMBER,
        )
        self.officer = User.objects.create_user(
            username='edit_officer',
            email='edit_officer@test.local',
            password='testpass123',
            name='編輯樂譜幹部',
            role=User.Role.OFFICER,
        )
        family = InstrumentFamily.objects.create(
            name='豎笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.instrument = InstrumentType.objects.create(name='單簧管', family=family)
        self.score = Score.objects.create(
            title='卡門組曲',
            composer='比才',
            score_type=Score.ScoreType.FULL,
            copyright_status=Score.CopyrightStatus.PUBLIC_DOMAIN,
        )
        self.url = reverse('scores:score_edit', args=[self.score.pk])

    # ── 存取控制 ────────────────────────────────────────

    def test_unauthenticated_redirects_to_login(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_member_redirects_with_error_message(self):
        """一般團員應被導回該樂譜詳情頁並顯示權限不足（不像 Admin 那樣直接被擋在登入頁外）"""
        self.client.force_login(self.member)
        r = self.client.get(self.url, follow=True)
        self.assertRedirects(r, reverse('scores:score_detail', args=[self.score.pk]))
        self.assertContains(r, '權限不足')

    def test_officer_get_returns_200_with_prefilled_data(self):
        """幹部 GET 應正常顯示表單，且既有資料已預先帶入欄位"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'value="卡門組曲"')
        self.assertContains(r, 'value="比才"')

    def test_invalid_pk_returns_404(self):
        """不存在的樂譜 pk 應回 404"""
        self.client.force_login(self.officer)
        r = self.client.get(reverse('scores:score_edit', args=[99999]))
        self.assertEqual(r.status_code, 404)

    # ── POST 更新 ────────────────────────────────────────

    def test_officer_post_updates_score(self):
        """幹部送出修改後的資料應成功更新，並導向詳情頁"""
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {
            'title': '卡門組曲（修訂版）',
            'composer': '比才',
            'score_type': Score.ScoreType.FULL,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
            'physical_quantity': '3',
        })
        self.assertRedirects(r, reverse('scores:score_detail', args=[self.score.pk]))
        self.score.refresh_from_db()
        self.assertEqual(self.score.title, '卡門組曲（修訂版）')
        self.assertEqual(self.score.physical_quantity, 3)

    def test_empty_title_does_not_update_record(self):
        """曲名清空時 full_clean() 應擋下，原始資料不變"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'title': '',
            'score_type': Score.ScoreType.FULL,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
        })
        self.score.refresh_from_db()
        self.assertEqual(self.score.title, '卡門組曲')

    def test_post_without_file_keeps_existing_file(self):
        """編輯時沒有重新上傳檔案，應保留原本的 PDF，不會被清空"""
        self.score.file = SimpleUploadedFile('original.pdf', b'%PDF-1.4 original', content_type='application/pdf')
        self.score.save()

        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'title': '卡門組曲',
            'score_type': Score.ScoreType.FULL,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
        })
        self.score.refresh_from_db()
        self.assertTrue(self.score.file)

    def test_post_with_new_file_replaces_existing(self):
        """上傳新檔案應取代原本的 PDF"""
        self.score.file = SimpleUploadedFile('original.pdf', b'%PDF-1.4 original', content_type='application/pdf')
        self.score.save()
        old_name = self.score.file.name

        self.client.force_login(self.officer)
        new_pdf = SimpleUploadedFile('replacement.pdf', b'%PDF-1.4 replacement', content_type='application/pdf')
        self.client.post(self.url, {
            'title': '卡門組曲',
            'score_type': Score.ScoreType.FULL,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
            'file': new_pdf,
        })
        self.score.refresh_from_db()
        self.assertNotEqual(self.score.file.name, old_name)

    def test_edit_part_score_binds_to_full_score(self):
        """編輯既有分譜時指定 full_score，應正確更新綁定關係"""
        part = Score.objects.create(
            title='卡門組曲（長笛）', score_type=Score.ScoreType.PART, instrument=self.instrument,
        )
        edit_url = reverse('scores:score_edit', args=[part.pk])
        self.client.force_login(self.officer)
        self.client.post(edit_url, {
            'title': '卡門組曲（長笛）',
            'score_type': Score.ScoreType.PART,
            'instrument': self.instrument.pk,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
            'full_score': self.score.pk,
        })
        part.refresh_from_db()
        self.assertEqual(part.full_score, self.score)


class ScoreDeleteViewTest(TestCase):
    """刪除樂譜（限管理員，跟演出活動／場地／團員通訊錄的刪除權限一致）"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='sdel_officer', password='x', name='刪除樂譜幹部',
            email='sdel_officer@test.local', role=User.Role.OFFICER,
        )
        self.admin = User.objects.create_user(
            username='sdel_admin', password='x', name='刪除樂譜管理員',
            email='sdel_admin@test.local', role=User.Role.ADMIN,
        )
        family = InstrumentFamily.objects.create(
            name='豎笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.instrument = InstrumentType.objects.create(name='單簧管', family=family)
        self.score = Score.objects.create(
            title='要刪除的樂譜', score_type=Score.ScoreType.FULL,
        )
        self.url = reverse('scores:score_delete', args=[self.score.pk])

    def test_officer_cannot_delete(self):
        """一般幹部無法刪除樂譜"""
        self.client.force_login(self.officer)
        r = self.client.post(self.url, follow=True)
        self.assertTrue(Score.objects.filter(pk=self.score.pk).exists())
        self.assertContains(r, '權限不足')

    def test_admin_can_delete_score(self):
        """管理員可刪除樂譜，並導向列表頁"""
        self.client.force_login(self.admin)
        r = self.client.post(self.url)
        self.assertFalse(Score.objects.filter(pk=self.score.pk).exists())
        self.assertRedirects(r, reverse('scores:score_list'))

    def test_deleting_full_score_cascades_parts(self):
        """刪除總譜應一併刪除底下所有分譜（既有 CASCADE 設計）"""
        part = Score.objects.create(
            title='要刪除的樂譜（單簧管）', score_type=Score.ScoreType.PART,
            instrument=self.instrument, full_score=self.score,
        )
        self.client.force_login(self.admin)
        self.client.post(self.url)
        self.assertFalse(Score.objects.filter(pk=part.pk).exists())

    def test_admin_cannot_delete_score_referenced_by_setlist(self):
        """
        樂譜被排入演出曲目單（Setlist，PROTECT）時，即使是管理員也無法刪除，
        應顯示友善錯誤訊息並保留資料，而不是讓伺服器噴 500。
        """
        from django.utils import timezone
        from apps.events.models import PerformanceEvent, Setlist
        from apps.public.models import Venue

        venue = Venue.objects.create(name='刪除樂譜測試場地', type='performance')
        event = PerformanceEvent.objects.create(
            name='刪除樂譜測試演出', type='concert', performance_date=timezone.now(),
            performance_venue=venue,
        )
        Setlist.objects.create(event=event, score=self.score, order=1)

        self.client.force_login(self.admin)
        r = self.client.post(self.url, follow=True)
        self.assertTrue(Score.objects.filter(pk=self.score.pk).exists())
        self.assertContains(r, '已被演出曲目單或對外交換紀錄引用')

    def test_admin_cannot_delete_score_referenced_by_exchange(self):
        """樂譜被對外交換紀錄（ScoreExchangeItem，PROTECT）引用時，管理員也無法刪除"""
        from .models import ScoreExchange, ScoreExchangeItem

        exchange = ScoreExchange.objects.create(other_band='測試樂團', exchange_date='2026-01-01')
        ScoreExchangeItem.objects.create(
            exchange=exchange, direction=ScoreExchangeItem.Direction.GIVE, score=self.score,
        )

        self.client.force_login(self.admin)
        r = self.client.post(self.url, follow=True)
        self.assertTrue(Score.objects.filter(pk=self.score.pk).exists())
        self.assertContains(r, '已被演出曲目單或對外交換紀錄引用')


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


@override_settings(MEDIA_ROOT=_TEMP_MEDIA)
class ScorePartsManageTest(TestCase):
    """
    分譜管理頁面（/scores/<pk>/parts/）

    這個視圖讓幹部為一份總譜批次上傳各樂器的分譜 PDF。
    - GET：顯示所有樂器族群 → 樂器 → 聲部的 checkbox 清單，已上傳的顯示下載連結
    - POST：依勾選的 checkbox 儲存對應 PDF，用 get_or_create 避免重複建立記錄

    @override_settings(MEDIA_ROOT=_TEMP_MEDIA) 讓測試時上傳的檔案存到暫存目錄，
    測試完由 tearDownClass 統一清除，不影響正式環境的 MEDIA_ROOT。
    """

    @classmethod
    def tearDownClass(cls):
        # 清除測試過程中上傳到暫存目錄的所有檔案
        shutil.rmtree(_TEMP_MEDIA, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        # 幹部帳號（role=OFFICER → is_officer 屬性為 True，有權限進入此頁）
        self.officer = User.objects.create_user(
            username='parts_officer',
            email='parts_officer@test.local',
            password='testpass123',
            name='分譜管理幹部',
            role=User.Role.OFFICER,
        )
        # 一般團員帳號（role=MEMBER → is_officer 為 False，無權限）
        self.member = User.objects.create_user(
            username='parts_member',
            email='parts_member@test.local',
            password='testpass123',
            name='一般團員',
            role=User.Role.MEMBER,
        )
        # 樂器階層：木管（category） → 長笛族（family） → 長笛（instrument）
        self.family = InstrumentFamily.objects.create(
            name='長笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.instrument = InstrumentType.objects.create(
            name='長笛', family=self.family
        )
        # 聲部（用於區分「第一部長笛」和「第二部長笛」等）
        self.section = SectionType.objects.create(name='第一部')
        # 總譜：管理分譜的入口，score_type=FULL
        self.full_score = Score.objects.create(
            title='星空', score_type=Score.ScoreType.FULL
        )
        # 分譜：用來驗證「分譜的 pk」不能進入管理頁（只有總譜才能管理分譜）
        self.part_score = Score.objects.create(
            title='星空（長笛）',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
        )
        self.url = reverse('scores:score_parts_manage', args=[self.full_score.pk])

    # ── T01 存取控制 ────────────────────────────────────────
    # 這個頁面涉及檔案上傳，必須嚴格限制只有登入的幹部才能使用。

    def test_unauthenticated_get_redirects_to_login(self):
        """
        未登入的訪客 GET 此頁應被導向登入頁（302）。
        @login_required decorator 負責處理，這裡確認它有正確套用。
        """
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_member_get_redirects_with_error_message(self):
        """
        已登入但角色是一般團員時，GET 應被重新導向到該總譜的詳情頁，
        並顯示「權限不足」的錯誤訊息。
        （幹部才能管理分譜，一般團員只能下載）
        """
        self.client.force_login(self.member)
        r = self.client.get(self.url, follow=True)
        # 應被導向該總譜的詳情頁
        self.assertRedirects(r, reverse('scores:score_detail', args=[self.full_score.pk]))
        # 頁面上應出現錯誤提示
        self.assertContains(r, '權限不足')

    def test_officer_get_full_score_returns_200_with_categories_data(self):
        """
        幹部 GET 總譜的管理頁，應正常顯示（200），
        且 context 中包含 categories_data（用於渲染 木管/銅管/打擊/其他 → 族群 → 樂器 → 聲部的四層清單）。
        """
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertIn('categories_data', r.context)
        # categories_data 至少要有一個分類（setUp 中建立了木管的長笛族）
        self.assertGreaterEqual(len(r.context['categories_data']), 1)

    def test_officer_get_part_score_returns_404(self):
        """
        幹部試圖對「分譜」的 pk 開啟管理頁，應回 404。
        視圖用 get_object_or_404(Score, pk=pk, score_type=FULL) 限制只能操作總譜。
        這條測試確保分譜不會意外進入管理流程。
        """
        self.client.force_login(self.officer)
        url = reverse('scores:score_parts_manage', args=[self.part_score.pk])
        r = self.client.get(url)
        self.assertEqual(r.status_code, 404)

    def test_officer_get_invalid_pk_returns_404(self):
        """
        不存在的 pk → 404，和其他視圖行為一致。
        """
        self.client.force_login(self.officer)
        r = self.client.get(reverse('scores:score_parts_manage', args=[99999]))
        self.assertEqual(r.status_code, 404)

    # ── T02 POST 上傳 ─────────────────────────────────────────
    # 上傳欄位名稱格式為 file_{instrument_id}_{section_id}，
    # 視圖解析這個名稱來決定要建立哪個樂器 × 聲部的分譜記錄。

    def test_post_upload_creates_part_record(self):
        """
        幹部 POST 一個有效的 PDF 檔案後，應在資料庫中建立對應的分譜記錄，
        且記錄的 full_score、instrument、section、score_type 都要正確。

        欄位名稱 file_{instrument_pk}_{section_pk} 是視圖與 template 約定的格式：
        視圖用 split('_', 2) 分解出樂器 id 和聲部 id。
        """
        self.client.force_login(self.officer)
        fake_pdf = SimpleUploadedFile(
            'flute_p1.pdf', b'%PDF-1.4 fake', content_type='application/pdf'
        )
        field_name = f'file_{self.instrument.pk}_{self.section.pk}'
        self.client.post(self.url, {field_name: fake_pdf})

        # 資料庫中應出現 1 筆分譜，掛在 full_score 底下
        self.assertEqual(Score.objects.filter(full_score=self.full_score).count(), 1)
        part = Score.objects.get(full_score=self.full_score)
        self.assertEqual(part.score_type, Score.ScoreType.PART)
        self.assertEqual(part.instrument, self.instrument)
        self.assertEqual(part.section, self.section)
        # 分譜的曲名繼承自總譜
        self.assertEqual(part.title, self.full_score.title)

    def test_post_upload_does_not_duplicate_existing_part(self):
        """
        同一組（total_score × instrument × section）已有分譜記錄時，
        再次 POST 上傳應更新檔案，而不是建立第二筆記錄。

        視圖使用 get_or_create 達成此目的：如果記錄已存在就取出後更新 file 欄位，
        所以不管上傳幾次，資料庫中都只會有 1 筆。
        """
        self.client.force_login(self.officer)
        # 先建立一筆現有的分譜記錄（模擬之前已上傳過）
        Score.objects.create(
            title=self.full_score.title,
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
            section=self.section,
            full_score=self.full_score,
        )
        self.assertEqual(Score.objects.filter(full_score=self.full_score).count(), 1)

        # 再次 POST 上傳同一個樂器 × 聲部
        fake_pdf = SimpleUploadedFile(
            'flute_p1_v2.pdf', b'%PDF-1.4 updated', content_type='application/pdf'
        )
        field_name = f'file_{self.instrument.pk}_{self.section.pk}'
        self.client.post(self.url, {field_name: fake_pdf})

        # 記錄數量仍應只有 1 筆（get_or_create 沒有多建）
        self.assertEqual(Score.objects.filter(full_score=self.full_score).count(), 1)

    def test_post_with_no_files_shows_warning_message(self):
        """
        POST 表單但沒有附上任何檔案時，應顯示「未偵測到上傳檔案」的警告訊息，
        並留在同一頁（重新導向回管理頁）。

        這對應到視圖中 `uploaded == 0` 的分支：
        使用者可能只勾了 checkbox 但忘記選擇 PDF 檔案。
        """
        self.client.force_login(self.officer)
        r = self.client.post(self.url, follow=True)
        self.assertContains(r, '未偵測到上傳檔案')
