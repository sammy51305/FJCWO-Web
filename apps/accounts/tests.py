from django.core import mail
from django.test import TestCase
from django.urls import reverse

from .models import InstrumentFamily, InstrumentType, User


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
        self.family = InstrumentFamily.objects.create(
            name='長笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.instrument = InstrumentType.objects.create(
            name='長笛', family=self.family
        )
        self.member = User.objects.create_user(
            username='dir_member',
            email='dirmember@test.local',
            password='testpass123',
            name='通訊錄團員',
            role=User.Role.MEMBER,
            phone='0911111111',
            instrument=self.family,
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

    def test_admin_role_sets_is_superuser(self):
        """
        admin 角色儲存後 is_superuser 自動為 True。
        is_staff 只讓使用者能登入 Django Admin，但沒有 is_superuser 的話
        不會自動授予任何 model 權限，導致進入後台卻什麼都操作不了（403）。
        設計目標「admin 有完整控制權」需要兩個旗標同時為 True。
        """
        user = User.objects.create_user(
            username='super_admin', password='x', name='', role=User.Role.ADMIN
        )
        self.assertTrue(user.is_superuser)

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
        self.family = InstrumentFamily.objects.create(
            name='小號族', category=InstrumentFamily.Category.BRASS
        )
        self.instrument = InstrumentType.objects.create(
            name='小號', family=self.family
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

    def test_approve_creates_user_account(self):
        """
        核准申請時應真的建立對應的 User 帳號（而不只是改申請狀態），
        姓名/Email/畢業年份/電話需與申請資料一致，樂器對應到族群（InstrumentFamily）。
        """
        from .models import Registration
        reg = Registration.objects.create(
            name='新會員', instrument=self.instrument,
            grad_year=115, email='newuser@test.local', phone='0911222333',
        )
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'reg_id': reg.pk, 'action': 'approve'})

        user = User.objects.get(email='newuser@test.local')
        self.assertEqual(user.name, '新會員')
        self.assertEqual(user.grad_year, 115)
        self.assertEqual(user.phone, '0911222333')
        self.assertEqual(user.instrument, self.family)
        self.assertEqual(user.role, User.Role.MEMBER)
        # 帳號用臨時密碼建立，必須強制對方登入後自行改密碼
        self.assertTrue(user.must_change_password)

    def test_approve_sends_temp_password_email(self):
        """核准申請後應寄送一封含帳號密碼的信到申請者 Email"""
        from .models import Registration
        reg = Registration.objects.create(
            name='收信測試', instrument=self.instrument,
            grad_year=115, email='mail_test@test.local',
        )
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'reg_id': reg.pk, 'action': 'approve'})

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('mail_test@test.local', mail.outbox[0].to)

    def test_approve_with_existing_email_does_not_create_duplicate(self):
        """Email 已被其他帳號使用時，核准應被擋下，不建立重複帳號，申請狀態維持 pending"""
        from .models import Registration
        User.objects.create_user(
            username='existing', password='x', name='已存在的人',
            email='dupemail@test.local', role=User.Role.MEMBER,
        )
        reg = Registration.objects.create(
            name='撞 Email 的人', instrument=self.instrument,
            grad_year=110, email='dupemail@test.local',
        )
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'reg_id': reg.pk, 'action': 'approve'})

        reg.refresh_from_db()
        self.assertEqual(reg.status, Registration.Status.PENDING)
        self.assertEqual(User.objects.filter(email='dupemail@test.local').count(), 1)

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


class MemberCreateTest(TestCase):
    """幹部手動新增團員帳號（不透過校友報到申請）"""

    def setUp(self):
        self.family = InstrumentFamily.objects.create(
            name='豎笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.officer = User.objects.create_user(
            username='mc_officer', password='x', name='新增團員幹部',
            email='mc_officer@test.local', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='mc_member', password='x', name='一般團員',
            email='mc_member@test.local', role=User.Role.MEMBER,
        )
        self.url = reverse('accounts:member_create')

    # ── 存取控制 ────────────────────────────────────────

    def test_unauthenticated_redirects_to_login(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_member_redirects_with_error_message(self):
        """一般團員應被導回通訊錄並顯示權限不足"""
        self.client.force_login(self.member)
        r = self.client.get(self.url, follow=True)
        self.assertRedirects(r, reverse('accounts:member_directory'))
        self.assertContains(r, '權限不足')

    def test_officer_get_returns_200(self):
        """幹部 GET 應正常顯示表單"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    # ── POST 新增團員 ────────────────────────────────────
    # 表單不收帳號/密碼/角色欄位：帳號由 Email 自動產生、密碼是隨機臨時密碼、
    # 角色固定為 MEMBER（幹部不能透過這個表單直接開幹部/管理員帳號）。

    def test_officer_post_creates_member(self):
        """幹部送出有效資料應成功建立帳號（角色固定 member），並導向通訊錄"""
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {
            'name': '手動新增的人',
            'email': 'manual@test.local',
            'instrument': self.family.pk,
        })
        self.assertRedirects(r, reverse('accounts:member_directory'))
        user = User.objects.get(email='manual@test.local')
        self.assertEqual(user.name, '手動新增的人')
        self.assertEqual(user.instrument, self.family)
        self.assertEqual(user.role, User.Role.MEMBER)
        self.assertTrue(user.must_change_password)

    def test_created_username_derived_from_email(self):
        """帳號應依 Email 前綴自動產生，不需要幹部手動輸入"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'name': '帳號產生測試',
            'email': 'autoname@test.local',
        })
        user = User.objects.get(email='autoname@test.local')
        self.assertEqual(user.username, 'autoname')

    def test_duplicate_email_does_not_create_record(self):
        """Email 已被使用時應擋下，不建立記錄"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'name': '重複 Email 測試',
            'email': self.officer.email,  # 與既有幹部帳號的 email 重複
        })
        self.assertEqual(User.objects.filter(email=self.officer.email).count(), 1)

    def test_post_sends_temp_password_email(self):
        """建立帳號後應寄送一封含帳號密碼的信到指定 Email"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'name': '收信測試',
            'email': 'member_mail_test@test.local',
        })
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('member_mail_test@test.local', mail.outbox[0].to)


class ForcePasswordChangeTest(TestCase):
    """强制設定新密碼流程（must_change_password + middleware + change_password view）"""

    def setUp(self):
        self.user = User.objects.create_user(
            username='needs_reset', password='temp12345', name='待改密碼團員',
            email='needs_reset@test.local', role=User.Role.MEMBER,
            must_change_password=True,
        )
        self.normal_user = User.objects.create_user(
            username='normal_user', password='pass12345', name='正常團員',
            email='normal_user@test.local', role=User.Role.MEMBER,
        )
        self.change_url = reverse('accounts:change_password')

    def test_must_change_password_user_redirected_to_change_password(self):
        """must_change_password=True 的使用者訪問任何頁面都會被導向設定密碼頁"""
        self.client.force_login(self.user)
        r = self.client.get(reverse('accounts:member_directory'))
        self.assertRedirects(r, self.change_url, fetch_redirect_response=False)

    def test_normal_user_not_redirected(self):
        """一般使用者（must_change_password=False）不受影響，正常瀏覽"""
        self.client.force_login(self.normal_user)
        r = self.client.get(reverse('accounts:member_directory'))
        self.assertEqual(r.status_code, 200)

    def test_change_password_page_itself_is_exempt(self):
        """避免無限重導向：設定密碼頁本身不會被 middleware 再次攔截"""
        self.client.force_login(self.user)
        r = self.client.get(self.change_url)
        self.assertEqual(r.status_code, 200)

    def test_successful_change_clears_flag_and_updates_password(self):
        """成功設定新密碼後，must_change_password 應變 False，且新密碼可用來登入"""
        self.client.force_login(self.user)
        r = self.client.post(self.change_url, {
            'new_password1': 'brandnewpass456',
            'new_password2': 'brandnewpass456',
        })
        self.assertRedirects(r, '/', fetch_redirect_response=False)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        self.assertTrue(self.user.check_password('brandnewpass456'))

    def test_mismatched_passwords_rejected(self):
        """兩次輸入不一致應被擋下，flag 維持 True"""
        self.client.force_login(self.user)
        self.client.post(self.change_url, {
            'new_password1': 'brandnewpass456',
            'new_password2': 'somethingelse789',
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)

    def test_weak_password_rejected(self):
        """太弱的密碼（Django 內建驗證器擋下）應被拒絕，flag 維持 True"""
        self.client.force_login(self.user)
        self.client.post(self.change_url, {
            'new_password1': '12345678',
            'new_password2': '12345678',
        })
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)

    def test_redirected_user_still_reaches_change_password_after_login(self):
        """
        整合情境：使用臨時密碼登入 → 任何頁面都被導向設定密碼頁 → 完成後恢復正常瀏覽。
        確認「登入需要真正的密碼」這道防線存在——沒帶對密碼一樣登入失敗。
        """
        r = self.client.post(reverse('accounts:login'), {
            'username': 'needs_reset', 'password': 'wrong-password',
        })
        self.assertEqual(r.status_code, 200)  # 沒有導向，代表登入失敗，留在登入頁

        r = self.client.post(reverse('accounts:login'), {
            'username': 'needs_reset', 'password': 'temp12345',
        }, follow=True)
        self.assertRedirects(r, self.change_url)
