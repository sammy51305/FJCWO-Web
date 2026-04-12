from django.test import TestCase
from django.urls import reverse


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
