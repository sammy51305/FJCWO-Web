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


class UserRoleTest(TestCase):
    """User 角色與權限屬性"""

    # ── T08 is_officer ───────────────────────────────────────

    def test_member_is_not_officer(self):
        """member 角色 is_officer 為 False"""
        user = User.objects.create_user(
            username='role_member', password='x', name='', role=User.Role.MEMBER
        )
        self.assertFalse(user.is_officer)

    def test_officer_is_officer(self):
        """officer 角色 is_officer 為 True"""
        user = User.objects.create_user(
            username='role_officer', password='x', name='', role=User.Role.OFFICER
        )
        self.assertTrue(user.is_officer)

    def test_admin_is_officer(self):
        """admin 角色 is_officer 為 True"""
        user = User.objects.create_user(
            username='role_admin', password='x', name='', role=User.Role.ADMIN
        )
        self.assertTrue(user.is_officer)

    def test_superuser_is_officer(self):
        """superuser 帳號 is_officer 為 True（不論 role）"""
        user = User.objects.create_user(
            username='role_super', password='x', name='',
            role=User.Role.MEMBER, is_superuser=True,
        )
        self.assertTrue(user.is_officer)

    # ── T09 is_staff 自動設定 ────────────────────────────────

    def test_admin_role_sets_is_staff(self):
        """admin 角色儲存後 is_staff 自動為 True"""
        user = User.objects.create_user(
            username='staff_admin', password='x', name='', role=User.Role.ADMIN
        )
        self.assertTrue(user.is_staff)

    def test_superuser_sets_is_staff(self):
        """superuser 儲存後 is_staff 自動為 True"""
        user = User.objects.create_superuser(
            username='staff_super', password='x', name=''
        )
        self.assertTrue(user.is_staff)

    def test_member_does_not_set_is_staff(self):
        """member 角色 is_staff 不自動設為 True"""
        user = User.objects.create_user(
            username='staff_member', password='x', name='', role=User.Role.MEMBER
        )
        self.assertFalse(user.is_staff)


class RegistrationTest(TestCase):
    """校友報到申請系統"""

    def setUp(self):
        self.instrument = InstrumentType.objects.create(
            name='小號', category=InstrumentType.Category.BRASS
        )
        self.officer = User.objects.create_user(
            username='reg_officer',
            email='reg_officer@test.local',
            password='testpass123',
            name='審核幹部',
            role=User.Role.OFFICER,
        )
        self.apply_url = reverse('accounts:registration_apply')
        self.status_url = reverse('accounts:registration_status')
        self.review_url = reverse('accounts:registration_review')

    # ── T10 申請表單（公開）──────────────────────────────────

    def test_apply_page_accessible_without_login(self):
        """申請頁面不需登入"""
        r = self.client.get(self.apply_url)
        self.assertEqual(r.status_code, 200)

    def test_valid_apply_creates_registration(self):
        """正確送出申請應建立 Registration 記錄"""
        from .models import Registration
        r = self.client.post(self.apply_url, {
            'name': '測試申請人',
            'instrument': self.instrument.pk,
            'grad_year': 110,
            'email': 'apply@test.local',
            'phone': '0912345678',
        })
        self.assertRedirects(r, self.status_url, fetch_redirect_response=False)
        self.assertEqual(Registration.objects.count(), 1)
        reg = Registration.objects.get()
        self.assertEqual(reg.status, Registration.Status.PENDING)

    def test_duplicate_pending_apply_blocked(self):
        """同一 Email 已有待審核申請時，再次送出應被擋下"""
        from .models import Registration
        Registration.objects.create(
            name='第一次', instrument=self.instrument,
            grad_year=110, email='dup@test.local',
        )
        self.client.post(self.apply_url, {
            'name': '第二次', 'instrument': self.instrument.pk,
            'grad_year': 110, 'email': 'dup@test.local',
        })
        self.assertEqual(Registration.objects.count(), 1)

    # ── T11 狀態查詢（公開）──────────────────────────────────

    def test_status_page_accessible_without_login(self):
        """狀態查詢頁不需登入"""
        r = self.client.get(self.status_url)
        self.assertEqual(r.status_code, 200)

    def test_status_query_shows_own_records(self):
        """以 Email 查詢可看到對應申請紀錄"""
        from .models import Registration
        Registration.objects.create(
            name='查詢測試', instrument=self.instrument,
            grad_year=110, email='status@test.local',
        )
        r = self.client.post(self.status_url, {'email': 'status@test.local'})
        self.assertContains(r, '查詢測試')

    # ── T12 幹部審核 ─────────────────────────────────────────

    def test_member_cannot_access_review(self):
        """一般團員無法進入審核頁"""
        member = User.objects.create_user(
            username='reg_member', password='x', name='', role=User.Role.MEMBER
        )
        self.client.force_login(member)
        r = self.client.get(self.review_url)
        self.assertRedirects(r, reverse('accounts:member_directory'), fetch_redirect_response=False)

    def test_officer_can_access_review(self):
        """幹部可進入審核頁"""
        self.client.force_login(self.officer)
        r = self.client.get(self.review_url)
        self.assertEqual(r.status_code, 200)

    def test_officer_can_approve_registration(self):
        """幹部核准後狀態變 approved"""
        from .models import Registration
        reg = Registration.objects.create(
            name='待核准', instrument=self.instrument,
            grad_year=110, email='approve@test.local',
        )
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'reg_id': reg.pk, 'action': 'approve'})
        reg.refresh_from_db()
        self.assertEqual(reg.status, Registration.Status.APPROVED)
        self.assertEqual(reg.reviewed_by, self.officer)

    def test_officer_can_reject_registration(self):
        """幹部拒絕後狀態變 rejected"""
        from .models import Registration
        reg = Registration.objects.create(
            name='待拒絕', instrument=self.instrument,
            grad_year=110, email='reject@test.local',
        )
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'reg_id': reg.pk, 'action': 'reject'})
        reg.refresh_from_db()
        self.assertEqual(reg.status, Registration.Status.REJECTED)
