from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import InstrumentFamily, InstrumentType, User
from .models import CUSTOM_INSTRUMENT_NAME, Score

DRIVE = 'https://drive.google.com/file/d/abc123/view'


class ScoreModelValidationTest(TestCase):
    """Score.clean() 驗證邏輯"""

    def setUp(self):
        self.family = InstrumentFamily.objects.create(
            name='長笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.instrument = InstrumentType.objects.create(
            name='長笛', family=self.family
        )

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

    def test_full_score_with_custom_instrument_name_raises(self):
        """總譜填了手填樂器名稱應拋出 ValidationError"""
        score = Score(
            title='測試總譜',
            score_type=Score.ScoreType.FULL,
            custom_instrument_name='手搖鈴',
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

    def test_custom_instrument_requires_name(self):
        """樂器選「其他（手填）」卻沒填名稱，應拋出 ValidationError"""
        custom = InstrumentType.objects.create(name=CUSTOM_INSTRUMENT_NAME, family=self.family)
        score = Score(title='星空', score_type=Score.ScoreType.PART, instrument=custom)
        with self.assertRaises(ValidationError):
            score.clean()

    def test_custom_name_only_allowed_for_custom_instrument(self):
        """一般樂器不能手填名稱（避免畫面顯示與樂器主檔不一致）"""
        score = Score(
            title='星空', score_type=Score.ScoreType.PART,
            instrument=self.instrument, custom_instrument_name='手搖鈴',
        )
        with self.assertRaises(ValidationError):
            score.clean()

    def test_str_custom_instrument_uses_typed_name(self):
        """手填樂器的 __str__ 與 instrument_label 顯示手填名稱，不是「其他（手填）」"""
        custom = InstrumentType.objects.create(name=CUSTOM_INSTRUMENT_NAME, family=self.family)
        score = Score(
            title='星空', score_type=Score.ScoreType.PART,
            instrument=custom, custom_instrument_name='手搖鈴',
        )
        score.clean()
        self.assertEqual(str(score), '星空（手搖鈴）')
        self.assertEqual(score.instrument_label, '手搖鈴')

    def test_drive_url_only_accepts_google_https(self):
        """Google Drive 連結只收 https 的 drive.google.com／docs.google.com，其餘（含 http、外站）拒絕"""
        for bad in ('http://drive.google.com/x', 'https://evil.example.com/x', 'https://drive.google.com.evil.com/x'):
            score = Score(title='星空', score_type=Score.ScoreType.FULL, copyright_status='public_domain', drive_url=bad)
            with self.assertRaises(ValidationError, msg=bad):
                score.full_clean()
        for good in (DRIVE, 'https://docs.google.com/document/d/abc/edit', 'https://drive.google.com/drive/folders/xyz'):
            score = Score(title='星空', score_type=Score.ScoreType.FULL, copyright_status='public_domain', drive_url=good)
            score.full_clean()

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

    # ── T02 列表只列總譜（#13-4）─────────────────────────────

    def test_list_shows_full_scores_only(self):
        """#13-4：清單只列總譜，分譜（含已綁定與未綁定）完全不出現"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '天空之城')
        self.assertNotContains(r, '天空之城（單簧管）')
        self.assertNotContains(r, '孤立分譜（單簧管）')

    def test_type_param_no_longer_shows_parts(self):
        """
        #13-4：譜種篩選器已移除。舊網址帶著 ?type=part 進來（書籤、舊連結）
        不應該變成分譜清單——參數被忽略，仍然只列總譜。
        """
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'type': 'part'})
        self.assertContains(r, '天空之城')
        self.assertNotContains(r, '天空之城（單簧管）')

    def test_part_count_column_shows_number_of_parts(self):
        """列表顯示每首總譜底下的分譜份數（天空之城有 1 份）"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '1 份')

    def test_full_score_without_parts_shows_placeholder(self):
        """沒有任何分譜的總譜，分譜欄顯示提示而非 0"""
        Score.objects.create(title='無分譜曲', score_type=Score.ScoreType.FULL)
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '尚未上傳')

    def test_filter_by_instrument_returns_full_scores(self):
        """
        #13-4：樂器篩選語意改為「底下有這個樂器分譜的總譜」。
        總譜本身沒有 instrument 欄位，舊的 filter(instrument_id=...) 會永遠篩不出東西。
        """
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'instrument': self.instrument.pk})
        self.assertContains(r, '天空之城')

    def test_filter_by_instrument_excludes_full_scores_without_that_part(self):
        """沒有該樂器分譜的總譜，不應出現在樂器篩選結果中"""
        Score.objects.create(title='只有總譜的曲子', score_type=Score.ScoreType.FULL)
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'instrument': self.instrument.pk})
        self.assertNotContains(r, '只有總譜的曲子')

    def test_filter_by_instrument_does_not_duplicate_rows(self):
        """
        同一總譜底下同一樂器有多份分譜時（舊資料併聲部後可能殘留），join 會產生重複列，
        view 用 distinct() 去重，總譜只應出現一次。
        """
        Score.objects.create(
            title='天空之城（單簧管二）',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
            full_score=self.full_score,
        )
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'instrument': self.instrument.pk})
        self.assertEqual(len(r.context['scores']), 1)

    def test_part_count_counts_all_parts_under_instrument_filter(self):
        """
        套用樂器篩選時，分譜份數欄仍應是「該總譜的全部分譜數」，
        而不是被篩選條件縮成「符合該樂器的分譜數」——annotate 在 filter 之前，
        Django 會另開一個 join 給 filter 用，兩者不共用（此測試釘住這個行為）。
        """
        flute = InstrumentType.objects.create(name='長笛', family=self.instrument.family)
        Score.objects.create(
            title='天空之城（長笛）',
            score_type=Score.ScoreType.PART,
            instrument=flute,
            full_score=self.full_score,
        )
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'instrument': self.instrument.pk})
        self.assertEqual(r.context['scores'][0].part_count, 2)

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

    # ── T03 未綁定總譜的分譜（#13-4 衍生）───────────────────

    def test_orphan_part_listed_for_officer(self):
        """
        分譜不再列在清單上之後，沒綁總譜的分譜就失去所有入口，
        因此列在幹部限定的警告區塊裡，讓幹部點進去補綁定。
        """
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '未綁定總譜')
        self.assertContains(r, '孤立分譜（單簧管）')

    def test_orphan_part_not_listed_for_member(self):
        """一般團員看不到未綁定分譜的警告區塊（那是幹部要處理的資料錯誤）"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertNotContains(r, '孤立分譜（單簧管）')

    def test_orphan_block_absent_when_all_parts_bound(self):
        """所有分譜都綁好總譜時，不顯示警告區塊"""
        self.unbound_part_score.full_score = self.full_score
        self.unbound_part_score.save()
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertNotContains(r, '份分譜未綁定總譜')

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
        self.officer = User.objects.create_user(
            username='score_detail_officer', password='x', name='詳情幹部',
            email='scoredetail_officer@test.local', role=User.Role.OFFICER,
        )
        self.admin = User.objects.create_user(
            username='score_detail_admin', password='x', name='詳情管理員',
            email='scoredetail_admin@test.local', role=User.Role.ADMIN,
        )
        self.score = Score.objects.create(
            title='卡門組曲',
            score_type=Score.ScoreType.FULL,
            composer='比才',
        )
        # #13-4 之後分譜只能從總譜詳情頁進入，故詳情測試需要一組總譜＋分譜
        family = InstrumentFamily.objects.create(
            name='長笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.instrument = InstrumentType.objects.create(name='長笛', family=family)
        self.full_score = Score.objects.create(
            title='阿爾卑斯交響曲', score_type=Score.ScoreType.FULL
        )
        self.part_score = Score.objects.create(
            title='阿爾卑斯交響曲（長笛）',
            score_type=Score.ScoreType.PART,
            instrument=self.instrument,
            full_score=self.full_score,
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

    # ── 分譜的入口與刪除（#13-4 衍生）─────────────────────

    def test_full_score_detail_links_to_each_part(self):
        """
        #13-4 之後庫存清單不列分譜，總譜詳情頁的分譜清單是進入分譜的**唯一**入口。
        少了這個連結，分譜就編輯不到也刪不掉（此測試釘住那條路）。
        """
        self.client.force_login(self.member)
        r = self.client.get(reverse('scores:score_detail', args=[self.full_score.pk]))
        self.assertContains(r, reverse('scores:score_detail', args=[self.part_score.pk]))

    def test_admin_can_delete_a_part(self):
        """管理員可以刪掉單一分譜，不影響所屬總譜"""
        self.client.force_login(self.admin)
        self.client.post(reverse('scores:score_delete', args=[self.part_score.pk]))
        self.assertFalse(Score.objects.filter(pk=self.part_score.pk).exists())
        self.assertTrue(Score.objects.filter(pk=self.full_score.pk).exists())

    def test_deleting_a_part_redirects_back_to_its_full_score(self):
        """
        刪完分譜要導回所屬總譜，不是導回清單——清單已經不列分譜，
        導回清單等於把人丟在找不到原本那首曲子的地方。
        """
        self.client.force_login(self.admin)
        r = self.client.post(reverse('scores:score_delete', args=[self.part_score.pk]))
        self.assertRedirects(
            r, reverse('scores:score_detail', args=[self.full_score.pk]),
            fetch_redirect_response=False,
        )

    def test_deleting_a_full_score_still_redirects_to_list(self):
        """總譜刪掉後沒有可回去的曲目，維持導回清單"""
        self.client.force_login(self.admin)
        r = self.client.post(reverse('scores:score_delete', args=[self.full_score.pk]))
        self.assertRedirects(r, reverse('scores:score_list'), fetch_redirect_response=False)

    def test_officer_cannot_delete_a_part(self):
        """刪除限管理員，幹部不行（與全站刪除權限一致）"""
        self.client.force_login(self.officer)
        self.client.post(reverse('scores:score_delete', args=[self.part_score.pk]))
        self.assertTrue(Score.objects.filter(pk=self.part_score.pk).exists())

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
        從列表帶著篩選條件（如 ?q=天空）進入詳情頁時，
        麵包屑「樂譜庫存」連結應帶回同樣的篩選條件，而不是導回無篩選的預設列表。
        """
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'q': '天空'})
        self.assertContains(r, f'{reverse("scores:score_list")}?q=')

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


class ScoreEditViewTest(TestCase):
    """編輯樂譜頁面（/scores/<pk>/edit/）"""

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

    def test_post_without_drive_url_keeps_existing_link(self):
        """沒送 drive_url 欄位時，保留原本的連結，不會被清空"""
        self.score.drive_url = DRIVE
        self.score.save()
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'title': '卡門組曲',
            'score_type': Score.ScoreType.FULL,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
        })
        self.score.refresh_from_db()
        self.assertEqual(self.score.drive_url, DRIVE)

    def test_post_with_new_drive_url_replaces_existing(self):
        """送出新連結應取代原本的連結"""
        self.score.drive_url = DRIVE
        self.score.save()
        self.client.force_login(self.officer)
        new_url = 'https://drive.google.com/file/d/new999/view'
        self.client.post(self.url, {
            'title': '卡門組曲',
            'score_type': Score.ScoreType.FULL,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
            'drive_url': new_url,
        })
        self.score.refresh_from_db()
        self.assertEqual(self.score.drive_url, new_url)

    def test_post_with_non_google_url_is_rejected(self):
        """貼非 Google 網域的連結會被擋下，原連結不變"""
        self.score.drive_url = DRIVE
        self.score.save()
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {
            'title': '卡門組曲',
            'score_type': Score.ScoreType.FULL,
            'copyright_status': Score.CopyrightStatus.PUBLIC_DOMAIN,
            'drive_url': 'https://evil.example.com/x.pdf',
        })
        self.assertContains(r, 'Google Drive')
        self.score.refresh_from_db()
        self.assertEqual(self.score.drive_url, DRIVE)

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


class ScoreDriveLinkDisplayTest(TestCase):
    """樂譜詳情頁：有 Google Drive 連結就直接連過去（新分頁、不帶 referrer），沒有就顯示「無數位版本」"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='dl_member', email='dl@test.local', password='testpass123',
            name='下載測試員', role=User.Role.MEMBER,
        )

    def test_detail_links_to_drive(self):
        score = Score.objects.create(title='有連結總譜', score_type=Score.ScoreType.FULL, drive_url=DRIVE)
        self.client.force_login(self.member)
        r = self.client.get(reverse('scores:score_detail', args=[score.pk]))
        self.assertContains(r, f'href="{DRIVE}"')
        self.assertContains(r, 'rel="noopener noreferrer"')

    def test_detail_without_link_shows_no_digital_copy(self):
        score = Score.objects.create(title='無連結總譜', score_type=Score.ScoreType.FULL)
        self.client.force_login(self.member)
        r = self.client.get(reverse('scores:score_detail', args=[score.pk]))
        self.assertContains(r, '無數位版本')

    def test_old_download_route_is_gone(self):
        """舊的 /scores/<pk>/download/ 已移除（檔案不再存在本系統）"""
        score = Score.objects.create(title='舊路徑', score_type=Score.ScoreType.FULL, drive_url=DRIVE)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(f'/scores/{score.pk}/download/').status_code, 404)


class ScorePartsManageTest(TestCase):
    """
    分譜連結管理頁（/scores/<pk>/parts/）

    樂譜檔案放在 Google Drive，幹部在這裡替一首總譜貼各樂器的連結：
    - 每種樂器一格（欄位名 url_<樂器id>），全部選填、至少填一個
    - 「其他（手填）」另列多列（custom_name / custom_url 成對）
    - 以送出內容為準：清空的格子會把原有分譜移除
    """

    def setUp(self):
        self.officer = User.objects.create_user(
            username='parts_officer', email='parts_officer@test.local', password='testpass123',
            name='分譜管理幹部', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='parts_member', email='parts_member@test.local', password='testpass123',
            name='一般團員', role=User.Role.MEMBER,
        )
        self.family = InstrumentFamily.objects.create(
            name='長笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.other_family = InstrumentFamily.objects.create(
            name='其他', category=InstrumentFamily.Category.OTHER
        )
        self.flute = InstrumentType.objects.create(name='長笛', family=self.family)
        self.piccolo = InstrumentType.objects.create(name='短笛', family=self.family)
        self.custom = InstrumentType.objects.create(name=CUSTOM_INSTRUMENT_NAME, family=self.other_family)
        self.full_score = Score.objects.create(
            title='星空', score_type=Score.ScoreType.FULL,
            copyright_status=Score.CopyrightStatus.PUBLIC_DOMAIN,
        )
        self.part_score = Score.objects.create(
            title='星空（長笛）', score_type=Score.ScoreType.PART, instrument=self.flute,
        )
        self.url = reverse('scores:score_parts_manage', args=[self.full_score.pk])

    # ── T01 存取控制 ────────────────────────────────────────

    def test_unauthenticated_get_redirects_to_login(self):
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_member_get_redirects_with_error_message(self):
        """一般團員 GET 導回總譜詳情頁並顯示「權限不足」"""
        self.client.force_login(self.member)
        r = self.client.get(self.url, follow=True)
        self.assertRedirects(r, reverse('scores:score_detail', args=[self.full_score.pk]))
        self.assertContains(r, '權限不足')

    def test_member_cannot_post(self):
        """一般團員 POST 被擋下，資料庫不增加分譜"""
        self.client.force_login(self.member)
        self.client.post(self.url, {f'url_{self.flute.pk}': DRIVE})
        self.assertEqual(Score.objects.filter(full_score=self.full_score).count(), 0)

    def test_officer_get_shows_one_input_per_instrument(self):
        """幹部看到每種樂器一個連結輸入框；「其他（手填）」不在固定清單裡"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, f'name="url_{self.flute.pk}"')
        self.assertContains(r, f'name="url_{self.piccolo.pk}"')
        self.assertNotContains(r, f'name="url_{self.custom.pk}"')
        self.assertContains(r, 'id="batch-text"')

    def test_officer_get_part_score_returns_404(self):
        """分譜的 pk 不能進管理頁（只有總譜可以）"""
        self.client.force_login(self.officer)
        r = self.client.get(reverse('scores:score_parts_manage', args=[self.part_score.pk]))
        self.assertEqual(r.status_code, 404)

    def test_officer_get_invalid_pk_returns_404(self):
        self.client.force_login(self.officer)
        r = self.client.get(reverse('scores:score_parts_manage', args=[99999]))
        self.assertEqual(r.status_code, 404)

    # ── T02 儲存連結 ─────────────────────────────────────────

    def test_post_creates_parts_only_for_filled_instruments(self):
        """只填長笛一格：只建長笛分譜，短笛（空白）不建；分譜繼承總譜的曲名與版權"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {f'url_{self.flute.pk}': DRIVE, f'url_{self.piccolo.pk}': ''})
        parts = Score.objects.filter(full_score=self.full_score)
        self.assertEqual(parts.count(), 1)
        part = parts.get()
        self.assertEqual(part.instrument, self.flute)
        self.assertEqual(part.drive_url, DRIVE)
        self.assertEqual(part.score_type, Score.ScoreType.PART)
        self.assertEqual(part.title, self.full_score.title)
        self.assertEqual(part.copyright_status, self.full_score.copyright_status)

    def test_post_again_updates_instead_of_duplicating(self):
        """同一樂器再送出是更新連結，不是多建一筆"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {f'url_{self.flute.pk}': DRIVE})
        new_url = 'https://drive.google.com/file/d/new/view'
        self.client.post(self.url, {f'url_{self.flute.pk}': new_url})
        part = Score.objects.get(full_score=self.full_score)
        self.assertEqual(part.drive_url, new_url)

    def test_clearing_a_field_removes_that_part(self):
        """以送出內容為準：清空某樂器的格子，原有分譜移除"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {f'url_{self.flute.pk}': DRIVE, f'url_{self.piccolo.pk}': DRIVE})
        self.assertEqual(Score.objects.filter(full_score=self.full_score).count(), 2)
        self.client.post(self.url, {f'url_{self.flute.pk}': DRIVE, f'url_{self.piccolo.pk}': ''})
        self.assertEqual(
            list(Score.objects.filter(full_score=self.full_score).values_list('instrument__name', flat=True)),
            ['長笛'],
        )

    def test_all_blank_is_rejected(self):
        """全部留白不能送出，並提示至少填一個"""
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {f'url_{self.flute.pk}': ''}, follow=True)
        self.assertContains(r, '請至少填一個')
        self.assertEqual(Score.objects.filter(full_score=self.full_score).count(), 0)

    def test_non_google_url_is_rejected_and_nothing_saved(self):
        """任何一格不是 Google 連結：整批不存，並把填的值帶回表單"""
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {
            f'url_{self.flute.pk}': DRIVE,
            f'url_{self.piccolo.pk}': 'https://evil.example.com/x',
        })
        self.assertContains(r, '短笛')
        self.assertContains(r, 'Google Drive')
        self.assertContains(r, f'value="{DRIVE}"')
        self.assertEqual(Score.objects.filter(full_score=self.full_score).count(), 0)

    # ── T03 手填樂器 ─────────────────────────────────────────

    def test_custom_instrument_rows_create_parts_with_typed_names(self):
        """「其他（手填）」可新增多列，各自存成分譜並顯示手填名稱"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'custom_name': ['手搖鈴', '鈴鼓'],
            'custom_url': [DRIVE, 'https://drive.google.com/file/d/b/view'],
        })
        parts = Score.objects.filter(full_score=self.full_score, instrument=self.custom)
        self.assertEqual({p.custom_instrument_name for p in parts}, {'手搖鈴', '鈴鼓'})
        self.assertEqual({p.instrument_label for p in parts}, {'手搖鈴', '鈴鼓'})

    def test_custom_row_needs_both_name_and_url(self):
        """手填列只填名稱或只填連結：不存，並提示"""
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {
            f'url_{self.flute.pk}': DRIVE, 'custom_name': ['手搖鈴'], 'custom_url': [''],
        }, follow=True)
        self.assertContains(r, '名稱與連結都要填')
        self.assertEqual(Score.objects.filter(full_score=self.full_score).count(), 0)

    def test_custom_row_removed_when_not_resubmitted(self):
        """再次送出時沒有帶上的手填列，原有的手填分譜會被移除"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {'custom_name': ['手搖鈴'], 'custom_url': [DRIVE]})
        self.client.post(self.url, {f'url_{self.flute.pk}': DRIVE})
        self.assertFalse(Score.objects.filter(full_score=self.full_score, instrument=self.custom).exists())

    def test_existing_custom_parts_are_listed_on_get(self):
        """GET 時已存在的手填分譜會回填到手填區"""
        Score.objects.create(
            title='星空', score_type=Score.ScoreType.PART, full_score=self.full_score,
            instrument=self.custom, custom_instrument_name='手搖鈴', drive_url=DRIVE,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, 'value="手搖鈴"')


class PerformancePartsViewTest(TestCase):
    """
    演出分譜下載入口（/scores/performance/<pk>/parts/）

    依登入者的「樂器族群」自動篩選出該演出曲目單用得到的分譜。
    關聯路徑：PerformanceEvent → Setlist.score（總譜）→ Score.parts（分譜）；
    篩選用 instrument__family（因 User.instrument 是族群、Score.instrument 是具體樂器，差一層）。
    """

    def setUp(self):
        from apps.events.models import PerformanceEvent, Setlist
        from apps.public.models import Venue

        # 兩個樂器族群：長笛族（登入者所屬）與小號族（別人的）
        self.flute_family = InstrumentFamily.objects.create(
            name='長笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.trumpet_family = InstrumentFamily.objects.create(
            name='小號族', category=InstrumentFamily.Category.BRASS
        )
        self.flute = InstrumentType.objects.create(name='長笛', family=self.flute_family)
        self.trumpet = InstrumentType.objects.create(name='小號', family=self.trumpet_family)

        # 登入者：樂器族群設為長笛族
        self.member = User.objects.create_user(
            username='pp_member', email='pp_member@test.local', password='x',
            name='分譜下載員', role=User.Role.MEMBER, instrument=self.flute_family,
        )

        # 演出 + 曲目單（總譜「星空」）
        venue = Venue.objects.create(name='演出分譜測試場地', type='performance')
        self.event = PerformanceEvent.objects.create(
            name='春季音樂會', type='concert', performance_date=timezone.now(),
            performance_venue=venue,
        )
        self.full_score = Score.objects.create(title='星空', score_type=Score.ScoreType.FULL)
        Setlist.objects.create(event=self.event, score=self.full_score, order=1)

        # 分譜：長笛（有檔案，登入者族群）、小號（別族群，應被濾掉）
        self.flute_part = Score.objects.create(
            title='星空', score_type=Score.ScoreType.PART,
            instrument=self.flute, full_score=self.full_score, drive_url=DRIVE,
        )
        self.trumpet_part = Score.objects.create(
            title='星空', score_type=Score.ScoreType.PART,
            instrument=self.trumpet, full_score=self.full_score,
            drive_url='https://drive.google.com/file/d/trumpet/view',
        )
        self.url = reverse('scores:performance_parts', args=[self.event.pk])

    # ── T01 存取控制 ────────────────────────────────────────

    def test_unauthenticated_redirects(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_authenticated_can_view(self):
        """登入後可開啟頁面"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_invalid_event_pk_returns_404(self):
        """不存在的演出 pk 應回 404"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('scores:performance_parts', args=[99999]))
        self.assertEqual(r.status_code, 404)

    # ── T02 依樂器族群篩選 ───────────────────────────────────

    def test_shows_part_of_own_family(self):
        """列出登入者所屬族群（長笛族）的分譜，並提供下載連結"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '長笛')
        self.assertContains(r, f'href="{DRIVE}"')

    def test_hides_part_of_other_family(self):
        """不列出其他族群（小號族）的分譜"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertNotContains(r, '小號')
        self.assertNotContains(r, 'trumpet/view')

    def test_part_not_in_this_event_excluded(self):
        """分譜的總譜沒被排進這場演出時，不應出現"""
        other_full = Score.objects.create(title='另一首', score_type=Score.ScoreType.FULL)
        Score.objects.create(
            title='另一首', score_type=Score.ScoreType.PART,
            instrument=self.flute, full_score=other_full,
        )
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertNotContains(r, '另一首')

    # ── T03 邊界情況 ─────────────────────────────────────────

    def test_member_without_family_sees_hint(self):
        """未設定樂器族群的團員應看到提示，而非空白頁"""
        self.member.instrument = None
        self.member.save()
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '尚未設定樂器族群')

    def test_no_matching_parts_shows_empty_message(self):
        """有設定族群但這場沒有該族群分譜時，顯示友善訊息"""
        self.flute_part.delete()  # 只剩小號族分譜，登入者是長笛族 → 無結果
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '沒有')
