from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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
    """團員通訊錄"""

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
            name='負責審核的幹部',
            role=User.Role.OFFICER,
        )
        # 搜尋「應被排除」的斷言不能用登入者（self.officer）自己的名字，
        # 因為導覽列一定會顯示登入者本人姓名（見 base.html），跟篩選結果無關，另建一個第三方團員來驗證
        self.unrelated_member = User.objects.create_user(
            username='dir_unrelated',
            email='dir_unrelated@test.local',
            password='testpass123',
            name='不相關的團員',
            role=User.Role.MEMBER,
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

    # ── 搜尋／篩選 ──────────────────────────────────────

    def test_search_by_name(self):
        """依姓名搜尋"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'q': '通訊錄團員'})
        self.assertContains(r, '通訊錄團員')
        self.assertNotContains(r, '不相關的團員')

    def test_default_hides_inactive_members(self):
        """預設（無篩選）只顯示在團團員，不顯示已退團的人"""
        inactive = User.objects.create_user(
            username='dir_inactive', email='dir_inactive@test.local',
            password='x', name='已退團的人', role=User.Role.MEMBER, is_active=False,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertNotContains(r, '已退團的人')

    def test_status_inactive_filter_shows_only_retired(self):
        """status=inactive 只顯示已退團的人"""
        User.objects.create_user(
            username='dir_inactive2', email='dir_inactive2@test.local',
            password='x', name='已退團的人2', role=User.Role.MEMBER, is_active=False,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.url, {'status': 'inactive'})
        self.assertContains(r, '已退團的人2')
        self.assertNotContains(r, '通訊錄團員')

    def test_member_cannot_use_status_filter(self):
        """一般團員無法用 status 參數看到已退團的人（權限只給幹部）"""
        User.objects.create_user(
            username='dir_inactive3', email='dir_inactive3@test.local',
            password='x', name='已退團的人3', role=User.Role.MEMBER, is_active=False,
        )
        self.client.force_login(self.member)
        r = self.client.get(self.url, {'status': 'inactive'})
        self.assertNotContains(r, '已退團的人3')


class MemberEditTest(TestCase):
    """幹部編輯團員資料"""

    def setUp(self):
        self.family = InstrumentFamily.objects.create(
            name='豎笛族', category=InstrumentFamily.Category.WOODWIND
        )
        self.other_family = InstrumentFamily.objects.create(
            name='薩克斯風族', category=InstrumentFamily.Category.WOODWIND
        )
        self.officer = User.objects.create_user(
            username='edit_m_officer', password='x', name='編輯幹部',
            email='edit_m_officer@test.local', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='edit_m_member', password='x', name='被編輯的人',
            email='edit_m_member@test.local', role=User.Role.MEMBER, instrument=self.family,
        )
        self.other_member = User.objects.create_user(
            username='edit_m_other', password='x', name='一般團員',
            email='edit_m_other@test.local', role=User.Role.MEMBER,
        )
        self.superuser = User.objects.create_superuser(
            username='edit_m_super', password='x', name='超級管理員', email='edit_m_super@test.local',
        )
        self.url = reverse('accounts:member_edit', args=[self.member.pk])

    def test_unauthenticated_redirects_to_login(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_member_redirects_with_error_message(self):
        """一般團員無法編輯他人資料"""
        self.client.force_login(self.other_member)
        r = self.client.get(self.url, follow=True)
        self.assertRedirects(r, reverse('accounts:member_directory'))
        self.assertContains(r, '權限不足')

    def test_officer_get_returns_200_with_prefilled_data(self):
        """幹部 GET 應正常顯示表單，且既有資料已預先帶入"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'value="被編輯的人"')

    def test_officer_post_updates_member(self):
        """幹部送出修改後的資料應成功更新"""
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {
            'name': '改名後的人',
            'email': self.member.email,
            'role': User.Role.MEMBER,
            'instrument': self.other_family.pk,
            'grad_year': 113,
        })
        self.assertRedirects(r, reverse('accounts:member_directory'))
        self.member.refresh_from_db()
        self.assertEqual(self.member.name, '改名後的人')
        self.assertEqual(self.member.instrument, self.other_family)

    def test_officer_can_promote_to_officer_role(self):
        """一般幹部可以把團員改成幹部角色"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'name': self.member.name, 'email': self.member.email,
            'role': User.Role.OFFICER,
        })
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, User.Role.OFFICER)

    def test_regular_officer_cannot_grant_admin_role(self):
        """一般幹部（非管理員）不能把角色設為管理員"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'name': self.member.name, 'email': self.member.email,
            'role': User.Role.ADMIN,
        })
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, User.Role.MEMBER)

    def test_superuser_can_grant_admin_role(self):
        """超級管理員可以把角色設為管理員"""
        self.client.force_login(self.superuser)
        self.client.post(self.url, {
            'name': self.member.name, 'email': self.member.email,
            'role': User.Role.ADMIN,
        })
        self.member.refresh_from_db()
        self.assertEqual(self.member.role, User.Role.ADMIN)

    def test_invalid_pk_returns_404(self):
        """不存在的團員 pk 應回 404"""
        self.client.force_login(self.officer)
        r = self.client.get(reverse('accounts:member_edit', args=[99999]))
        self.assertEqual(r.status_code, 404)


class MemberStatusTest(TestCase):
    """團員退團／恢復在團狀態（軟刪除）"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='status_officer', password='x', name='狀態幹部',
            email='status_officer@test.local', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='status_member', password='x', name='要退團的人',
            email='status_member@test.local', role=User.Role.MEMBER,
        )
        self.other_member = User.objects.create_user(
            username='status_other', password='x', name='一般團員',
            email='status_other@test.local', role=User.Role.MEMBER,
        )

    def test_officer_can_deactivate_member(self):
        """幹部可將團員標記為退團，is_active 變 False"""
        self.client.force_login(self.officer)
        self.client.post(reverse('accounts:member_deactivate', args=[self.member.pk]))
        self.member.refresh_from_db()
        self.assertFalse(self.member.is_active)

    def test_deactivate_does_not_delete_record(self):
        """退團不會真的刪除資料"""
        self.client.force_login(self.officer)
        self.client.post(reverse('accounts:member_deactivate', args=[self.member.pk]))
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())

    def test_officer_cannot_deactivate_self(self):
        """幹部不能把自己標記為退團"""
        self.client.force_login(self.officer)
        self.client.post(reverse('accounts:member_deactivate', args=[self.officer.pk]))
        self.officer.refresh_from_db()
        self.assertTrue(self.officer.is_active)

    def test_member_cannot_deactivate_others(self):
        """一般團員無法將他人標記為退團"""
        self.client.force_login(self.other_member)
        self.client.post(reverse('accounts:member_deactivate', args=[self.member.pk]))
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)

    def test_officer_can_reactivate_member(self):
        """幹部可將已退團的團員恢復在團"""
        self.member.is_active = False
        self.member.save()
        self.client.force_login(self.officer)
        self.client.post(reverse('accounts:member_reactivate', args=[self.member.pk]))
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_active)


class MemberDeleteTest(TestCase):
    """團員帳號刪除：僅無任何關聯紀錄時允許真的刪除"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='del_officer', password='x', name='刪除幹部',
            email='del_officer@test.local', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='del_member', password='x', name='要刪除的人',
            email='del_member@test.local', role=User.Role.MEMBER,
        )
        self.other_member = User.objects.create_user(
            username='del_other', password='x', name='一般團員',
            email='del_other@test.local', role=User.Role.MEMBER,
        )

    def test_officer_can_delete_member_with_no_history(self):
        """沒有任何關聯紀錄的帳號（例如剛新增打錯）可以真的被刪除"""
        self.client.force_login(self.officer)
        self.client.post(reverse('accounts:member_delete', args=[self.member.pk]))
        self.assertFalse(User.objects.filter(pk=self.member.pk).exists())

    def test_member_with_related_records_cannot_be_deleted(self):
        """已有關聯紀錄（如出席紀錄）的帳號不可刪除，應顯示錯誤訊息並保留資料"""
        from apps.events.models import PerformanceEvent, Rehearsal, RehearsalAttendance
        from apps.public.models import Venue

        venue = Venue.objects.create(name='測試場地', type='rehearsal')
        event = PerformanceEvent.objects.create(
            name='測試演出', type='concert', performance_date=timezone.now(), performance_venue=venue,
        )
        rehearsal = Rehearsal.objects.create(event=event, sequence=1, date=timezone.now(), venue=venue)
        RehearsalAttendance.objects.create(rehearsal=rehearsal, member=self.member, status='present')

        self.client.force_login(self.officer)
        r = self.client.post(reverse('accounts:member_delete', args=[self.member.pk]), follow=True)
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())
        self.assertContains(r, '無法直接刪除')

    def test_officer_cannot_delete_self(self):
        """幹部不能刪除自己的帳號"""
        self.client.force_login(self.officer)
        self.client.post(reverse('accounts:member_delete', args=[self.officer.pk]))
        self.assertTrue(User.objects.filter(pk=self.officer.pk).exists())

    def test_member_cannot_delete_others(self):
        """一般團員無法刪除他人帳號"""
        self.client.force_login(self.other_member)
        self.client.post(reverse('accounts:member_delete', args=[self.member.pk]))
        self.assertTrue(User.objects.filter(pk=self.member.pk).exists())


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


class RegistrationManageTest(TestCase):
    """校友報到申請的完整管理功能：查詢、重新審核、新增、編輯、刪除"""

    def setUp(self):
        self.family = InstrumentFamily.objects.create(
            name='長號族', category=InstrumentFamily.Category.BRASS
        )
        self.instrument = InstrumentType.objects.create(name='長號', family=self.family)
        self.other_instrument = InstrumentType.objects.create(name='低音號', family=self.family)
        self.officer = User.objects.create_user(
            username='mng_officer', password='x', name='管理幹部',
            email='mng_officer@test.local', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='mng_member', password='x', name='一般團員',
            email='mng_member@test.local', role=User.Role.MEMBER,
        )
        self.review_url = reverse('accounts:registration_review')
        self.create_url = reverse('accounts:registration_create')

    # ── 查詢／篩選 ──────────────────────────────────────

    def test_search_by_name(self):
        """依姓名關鍵字搜尋"""
        from .models import Registration
        Registration.objects.create(
            name='搜尋目標', instrument=self.instrument, grad_year=110, email='findme@test.local',
        )
        Registration.objects.create(
            name='不相關的人', instrument=self.instrument, grad_year=110, email='other@test.local',
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.review_url, {'q': '搜尋目標'})
        self.assertContains(r, '搜尋目標')
        self.assertNotContains(r, '不相關的人')

    def test_filter_by_status(self):
        """依審核狀態篩選"""
        from .models import Registration
        Registration.objects.create(
            name='待審的人', instrument=self.instrument, grad_year=110,
            email='pending_person@test.local', status=Registration.Status.PENDING,
        )
        Registration.objects.create(
            name='已拒絕的人', instrument=self.instrument, grad_year=110,
            email='rejected_person@test.local', status=Registration.Status.REJECTED,
        )
        self.client.force_login(self.officer)
        r = self.client.get(self.review_url, {'status': 'rejected'})
        self.assertContains(r, '已拒絕的人')
        self.assertNotContains(r, '待審的人')

    # ── 重新開放審核 ────────────────────────────────────

    def test_reopen_rejected_registration(self):
        """已拒絕的申請可重新開放為待審核"""
        from .models import Registration
        reg = Registration.objects.create(
            name='想再給機會', instrument=self.instrument, grad_year=110,
            email='reopen@test.local', status=Registration.Status.REJECTED,
            reviewed_by=self.officer, reviewed_at=timezone.now(),
        )
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'reg_id': reg.pk, 'action': 'reopen'})
        reg.refresh_from_db()
        self.assertEqual(reg.status, Registration.Status.PENDING)
        self.assertIsNone(reg.reviewed_by)

    def test_cannot_reopen_approved_registration(self):
        """已核准的申請不能被重新開放（帳號已建立，狀態不該再變動）"""
        from .models import Registration
        reg = Registration.objects.create(
            name='已核准的人', instrument=self.instrument, grad_year=110,
            email='already_approved@test.local', status=Registration.Status.APPROVED,
        )
        self.client.force_login(self.officer)
        self.client.post(self.review_url, {'reg_id': reg.pk, 'action': 'reopen'})
        reg.refresh_from_db()
        self.assertEqual(reg.status, Registration.Status.APPROVED)

    # ── 新增申請紀錄 ────────────────────────────────────

    def test_member_cannot_access_create(self):
        """
        一般團員無法新增申請紀錄。權限檢查導向 registration_review，
        但團員在那邊一樣沒有權限，會再被導向通訊錄，所以最終落點是通訊錄頁。
        """
        self.client.force_login(self.member)
        r = self.client.get(self.create_url, follow=True)
        self.assertRedirects(r, reverse('accounts:member_directory'))
        self.assertContains(r, '權限不足')

    def test_officer_post_creates_registration(self):
        """幹部送出有效資料應成功建立申請紀錄，狀態預設待審核"""
        from .models import Registration
        self.client.force_login(self.officer)
        r = self.client.post(self.create_url, {
            'name': '電話報到的人',
            'instrument': self.instrument.pk,
            'grad_year': 112,
            'email': 'phonecall@test.local',
            'phone': '0900000000',
        })
        self.assertRedirects(r, self.review_url)
        reg = Registration.objects.get(email='phonecall@test.local')
        self.assertEqual(reg.name, '電話報到的人')
        self.assertEqual(reg.status, Registration.Status.PENDING)

    def test_create_empty_name_does_not_create_record(self):
        """姓名空白時應擋下，不建立紀錄"""
        from .models import Registration
        self.client.force_login(self.officer)
        self.client.post(self.create_url, {
            'name': '',
            'instrument': self.instrument.pk,
            'grad_year': 112,
            'email': 'blank_name@test.local',
        })
        self.assertFalse(Registration.objects.filter(email='blank_name@test.local').exists())

    # ── 編輯申請紀錄 ────────────────────────────────────

    def test_officer_post_edits_registration(self):
        """幹部編輯應更新資料，不影響審核狀態"""
        from .models import Registration
        reg = Registration.objects.create(
            name='打錯字的人', instrument=self.instrument, grad_year=110, email='typo@test.local',
        )
        edit_url = reverse('accounts:registration_edit', args=[reg.pk])
        self.client.force_login(self.officer)
        r = self.client.post(edit_url, {
            'name': '修正後的姓名',
            'instrument': self.other_instrument.pk,
            'grad_year': 111,
            'email': 'typo@test.local',
        })
        self.assertRedirects(r, self.review_url)
        reg.refresh_from_db()
        self.assertEqual(reg.name, '修正後的姓名')
        self.assertEqual(reg.instrument, self.other_instrument)
        self.assertEqual(reg.status, Registration.Status.PENDING)

    def test_edit_invalid_pk_returns_404(self):
        """不存在的申請 pk 應回 404"""
        self.client.force_login(self.officer)
        r = self.client.get(reverse('accounts:registration_edit', args=[99999]))
        self.assertEqual(r.status_code, 404)

    # ── 刪除申請紀錄 ────────────────────────────────────

    def test_officer_can_delete_pending_registration(self):
        """待審核的申請紀錄可被刪除"""
        from .models import Registration
        reg = Registration.objects.create(
            name='要刪除的人', instrument=self.instrument, grad_year=110, email='todelete@test.local',
        )
        self.client.force_login(self.officer)
        self.client.post(reverse('accounts:registration_delete', args=[reg.pk]))
        self.assertFalse(Registration.objects.filter(pk=reg.pk).exists())

    def test_approved_registration_cannot_be_deleted(self):
        """已核准的申請紀錄不可刪除，需保留稽核軌跡"""
        from .models import Registration
        reg = Registration.objects.create(
            name='已核准不可刪', instrument=self.instrument, grad_year=110,
            email='approved_keep@test.local', status=Registration.Status.APPROVED,
        )
        self.client.force_login(self.officer)
        self.client.post(reverse('accounts:registration_delete', args=[reg.pk]))
        self.assertTrue(Registration.objects.filter(pk=reg.pk).exists())

    def test_member_cannot_delete_registration(self):
        """一般團員無法刪除申請紀錄"""
        from .models import Registration
        reg = Registration.objects.create(
            name='團員不能刪這個', instrument=self.instrument, grad_year=110, email='member_cant@test.local',
        )
        self.client.force_login(self.member)
        self.client.post(reverse('accounts:registration_delete', args=[reg.pk]))
        self.assertTrue(Registration.objects.filter(pk=reg.pk).exists())


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
