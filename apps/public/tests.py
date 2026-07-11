from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from .models import CharterContent


class PublicPagesTest(TestCase):
    """公開頁面（未登入可瀏覽）"""

    # ── T01 首頁 ────────────────────────────────────────────

    def test_index_accessible(self):
        """首頁 200"""
        r = self.client.get(reverse('public:index'))
        self.assertEqual(r.status_code, 200)

    def test_index_no_login_required(self):
        """首頁不需登入，不應導向登入頁"""
        r = self.client.get(reverse('public:index'))
        self.assertNotIn('/accounts/login/', r.get('Location', ''))

    # ── T02 關於百韻 ─────────────────────────────────────────

    def test_about_accessible(self):
        """關於頁 200"""
        r = self.client.get(reverse('public:about'))
        self.assertEqual(r.status_code, 200)

    def test_about_no_login_required(self):
        """關於頁不需登入"""
        r = self.client.get(reverse('public:about'))
        self.assertNotIn('/accounts/login/', r.get('Location', ''))

    # ── T03 組織章程 ─────────────────────────────────────────

    def test_rules_accessible(self):
        """章程頁 200"""
        r = self.client.get(reverse('public:rules'))
        self.assertEqual(r.status_code, 200)

    def test_rules_no_login_required(self):
        """章程頁不需登入"""
        r = self.client.get(reverse('public:rules'))
        self.assertNotIn('/accounts/login/', r.get('Location', ''))

    def test_rules_shows_content(self):
        """章程頁顯示 DB 中的章程內容"""
        CharterContent.objects.create(content='第一條　本團名稱為百韻管樂團。')
        r = self.client.get(reverse('public:rules'))
        self.assertContains(r, '第一條')

    def test_rules_empty_when_no_content(self):
        """無章程資料時顯示佔位文字"""
        r = self.client.get(reverse('public:rules'))
        self.assertContains(r, '尚未建立')


class CharterEditTest(TestCase):
    """組織章程編輯（幹部限定）"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='member1', email='member1@test.local', password='pw', role='member')
        self.officer = User.objects.create_user(
            username='officer1', email='officer1@test.local', password='pw', role='officer')

    def test_rules_edit_redirects_anonymous(self):
        """未登入導向登入頁"""
        r = self.client.get(reverse('public:rules_edit'))
        self.assertRedirects(r, f'/accounts/login/?next=/rules/edit/', fetch_redirect_response=False)

    def test_rules_edit_forbidden_for_member(self):
        """一般團員無法進入編輯頁"""
        self.client.login(username='member1', password='pw')
        r = self.client.get(reverse('public:rules_edit'))
        self.assertRedirects(r, reverse('public:rules'), fetch_redirect_response=False)

    def test_rules_edit_accessible_for_officer(self):
        """幹部可進入章程編輯頁"""
        self.client.login(username='officer1', password='pw')
        r = self.client.get(reverse('public:rules_edit'))
        self.assertEqual(r.status_code, 200)

    def test_rules_edit_saves_content(self):
        """POST 正確儲存章程並 redirect 到章程頁"""
        self.client.login(username='officer1', password='pw')
        r = self.client.post(reverse('public:rules_edit'), {'content': '第一條　本團名稱為百韻管樂團。'})
        self.assertRedirects(r, reverse('public:rules'), fetch_redirect_response=False)
        self.assertEqual(CharterContent.objects.first().content, '第一條　本團名稱為百韻管樂團。')

    def test_rules_edit_updates_existing_content(self):
        """二次 POST 更新同一筆資料，不新增"""
        CharterContent.objects.create(pk=1, content='舊版章程')
        self.client.login(username='officer1', password='pw')
        self.client.post(reverse('public:rules_edit'), {'content': '新版章程'})
        self.assertEqual(CharterContent.objects.count(), 1)
        self.assertEqual(CharterContent.objects.first().content, '新版章程')
