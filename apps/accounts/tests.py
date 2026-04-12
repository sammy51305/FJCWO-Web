from django.test import TestCase
from django.urls import reverse

from .models import InstrumentType, User


class LoginLogoutTest(TestCase):
    """登入 / 登出"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.local',
            password='testpass123',
            name='測試團員',
            role=User.Role.MEMBER,
        )
        self.login_url = reverse('accounts:login')
        self.logout_url = reverse('accounts:logout')

    # ── T01 登入頁面 ─────────────────────────────────────────

    def test_login_page_accessible(self):
        """登入頁 200"""
        r = self.client.get(self.login_url)
        self.assertEqual(r.status_code, 200)

    def test_login_page_shows_form(self):
        """登入頁含表單欄位"""
        r = self.client.get(self.login_url)
        self.assertContains(r, 'name="username"')
        self.assertContains(r, 'name="password"')

    def test_already_authenticated_redirects(self):
        """已登入時再訪登入頁應導向首頁"""
        self.client.force_login(self.user)
        r = self.client.get(self.login_url)
        self.assertRedirects(r, '/', fetch_redirect_response=False)

    # ── T02 登入流程 ─────────────────────────────────────────

    def test_valid_login_redirects(self):
        """正確帳密登入後導向首頁"""
        r = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'testpass123',
        })
        self.assertRedirects(r, '/', fetch_redirect_response=False)

    def test_valid_login_with_next(self):
        """登入後導向 next 參數指定頁面"""
        r = self.client.post(
            f'{self.login_url}?next=/events/',
            {'username': 'testuser', 'password': 'testpass123'},
        )
        self.assertRedirects(r, '/events/', fetch_redirect_response=False)

    def test_invalid_login_shows_error(self):
        """錯誤密碼停留在登入頁"""
        r = self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        self.assertEqual(r.status_code, 200)

    def test_invalid_login_no_session(self):
        """錯誤密碼不建立登入 session"""
        self.client.post(self.login_url, {
            'username': 'testuser',
            'password': 'wrongpassword',
        })
        self.assertNotIn('_auth_user_id', self.client.session)

    # ── T03 登出 ─────────────────────────────────────────────

    def test_logout_redirects_to_home(self):
        """登出後導向首頁"""
        self.client.force_login(self.user)
        r = self.client.post(self.logout_url)
        self.assertRedirects(r, '/', fetch_redirect_response=False)

    def test_logout_clears_session(self):
        """登出後 session 清除"""
        self.client.force_login(self.user)
        self.client.post(self.logout_url)
        self.assertNotIn('_auth_user_id', self.client.session)


class ProfileTest(TestCase):
    """個人資料頁面"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='profileuser',
            email='profile@test.local',
            password='testpass123',
            name='資料測試',
            role=User.Role.MEMBER,
        )
        self.url = reverse('accounts:profile')

    # ── T04 個人資料存取控制 ─────────────────────────────────

    def test_unauthenticated_redirects(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_authenticated_can_view(self):
        """登入後可看到個人資料頁"""
        self.client.force_login(self.user)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_profile_shows_current_name(self):
        """頁面顯示現有姓名"""
        self.client.force_login(self.user)
        r = self.client.get(self.url)
        self.assertContains(r, '資料測試')

    # ── T05 個人資料儲存 ─────────────────────────────────────

    def test_valid_profile_update(self):
        """POST 正確資料後儲存並導向個人資料頁"""
        self.client.force_login(self.user)
        r = self.client.post(self.url, {
            'name': '新姓名',
            'email': 'new@test.local',
            'phone': '0912345678',
            'grad_year': 2022,
        })
        self.assertRedirects(r, self.url, fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertEqual(self.user.name, '新姓名')
        self.assertEqual(self.user.phone, '0912345678')


class MemberDirectoryTest(TestCase):
    """會員通訊錄"""

    def setUp(self):
        self.instrument = InstrumentType.objects.create(
            name='長笛', category=InstrumentType.Category.WOODWIND
        )
        self.member = User.objects.create_user(
            username='dir_member',
            email='dirmember@test.local',
            password='testpass123',
            name='通訊錄團員',
            role=User.Role.MEMBER,
            phone='0911111111',
            instrument=self.instrument,
        )
        self.officer = User.objects.create_user(
            username='dir_officer',
            email='dirofficer@test.local',
            password='testpass123',
            name='通訊錄幹部',
            role=User.Role.OFFICER,
        )
        self.url = reverse('accounts:member_directory')

    # ── T06 通訊錄存取控制 ───────────────────────────────────

    def test_unauthenticated_redirects(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_member_can_view_directory(self):
        """一般 member 可進入通訊錄"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    # ── T07 通訊錄資料可見性 ─────────────────────────────────

    def test_member_sees_names(self):
        """所有登入者皆可看到姓名"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '通訊錄團員')

    def test_member_cannot_see_phone(self):
        """一般 member 看不到電話"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertNotContains(r, '0911111111')

    def test_officer_can_see_phone(self):
        """幹部可看到電話"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '0911111111')

    def test_officer_can_see_email(self):
        """幹部可看到 email"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, 'dirmember@test.local')

    def test_admin_excluded_from_directory(self):
        """管理員帳號不出現在通訊錄"""
        admin = User.objects.create_user(
            username='dir_admin',
            email='diradmin@test.local',
            password='testpass123',
            name='管理員本人',
            role=User.Role.ADMIN,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertNotContains(r, '管理員本人')
