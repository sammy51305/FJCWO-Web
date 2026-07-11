from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from .models import CharterContent, Venue, VenueTimeSlot


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


class VenueManageTest(TestCase):
    """場地管理（新增/編輯/刪除/查詢，含時段管理）"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='venue_member', password='x', name='一般團員',
            email='venue_member@test.local', role=User.Role.MEMBER,
        )
        self.officer = User.objects.create_user(
            username='venue_officer', password='x', name='場地幹部',
            email='venue_officer@test.local', role=User.Role.OFFICER,
        )
        self.admin = User.objects.create_user(
            username='venue_admin', password='x', name='場地管理員',
            email='venue_admin@test.local', role=User.Role.ADMIN,
        )
        self.venue = Venue.objects.create(
            name='測試場地', type=Venue.Type.REHEARSAL, address='測試地址',
        )
        self.list_url = reverse('public:venue_list')

    # ── 列表：存取控制／查詢／篩選 ────────────────────────

    def test_unauthenticated_redirects_to_login(self):
        """未登入應導向登入頁"""
        r = self.client.get(self.list_url)
        self.assertEqual(r.status_code, 302)
        self.assertIn('/accounts/login/', r['Location'])

    def test_member_redirects_with_error_message(self):
        """一般團員無法進入場地管理頁"""
        self.client.force_login(self.member)
        r = self.client.get(self.list_url, follow=True)
        self.assertRedirects(r, reverse('public:index'))
        self.assertContains(r, '權限不足')

    def test_officer_can_view_list(self):
        """幹部可看到場地列表"""
        self.client.force_login(self.officer)
        r = self.client.get(self.list_url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '測試場地')

    def test_search_by_name(self):
        """依名稱搜尋"""
        Venue.objects.create(name='不相關場地', type=Venue.Type.PERFORMANCE)
        self.client.force_login(self.officer)
        r = self.client.get(self.list_url, {'q': '測試場地'})
        self.assertContains(r, '測試場地')
        self.assertNotContains(r, '不相關場地')

    def test_filter_by_type(self):
        """依類別篩選"""
        Venue.objects.create(name='演出場地甲', type=Venue.Type.PERFORMANCE)
        self.client.force_login(self.officer)
        r = self.client.get(self.list_url, {'type': 'performance'})
        self.assertContains(r, '演出場地甲')
        self.assertNotContains(r, '測試場地')

    # ── 新增 ────────────────────────────────────────────

    def test_officer_post_creates_venue(self):
        """幹部送出有效資料應成功建立場地"""
        self.client.force_login(self.officer)
        r = self.client.post(reverse('public:venue_create'), {
            'name': '新場地', 'type': Venue.Type.PERFORMANCE, 'address': '某路 100 號',
        })
        venue = Venue.objects.get(name='新場地')
        self.assertRedirects(r, reverse('public:venue_edit', args=[venue.pk]))

    def test_empty_name_does_not_create_venue(self):
        """場地名稱空白時應擋下，不建立記錄"""
        self.client.force_login(self.officer)
        self.client.post(reverse('public:venue_create'), {'name': '', 'type': Venue.Type.PERFORMANCE})
        self.assertFalse(Venue.objects.filter(name='').exists())

    # ── 編輯與時段管理 ──────────────────────────────────

    def test_officer_get_edit_returns_200_with_prefilled_data(self):
        """幹部 GET 編輯頁應正常顯示，且既有資料已預先帶入"""
        self.client.force_login(self.officer)
        r = self.client.get(reverse('public:venue_edit', args=[self.venue.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'value="測試場地"')

    def test_officer_post_updates_venue(self):
        """幹部送出修改後的資料應成功更新"""
        self.client.force_login(self.officer)
        self.client.post(reverse('public:venue_edit', args=[self.venue.pk]), {
            'name': '改名後的場地', 'type': Venue.Type.REHEARSAL, 'address': '新地址',
        })
        self.venue.refresh_from_db()
        self.assertEqual(self.venue.name, '改名後的場地')

    def test_add_timeslot(self):
        """新增時段應成功建立 VenueTimeSlot"""
        self.client.force_login(self.officer)
        self.client.post(reverse('public:venue_edit', args=[self.venue.pk]), {
            'add_timeslot': '1', 'is_sat': 'on', 'start_time': '09:00', 'end_time': '12:00', 'fee': '3000',
        })
        self.assertEqual(self.venue.time_slots.count(), 1)
        slot = self.venue.time_slots.first()
        self.assertTrue(slot.is_sat)
        self.assertEqual(slot.fee, 3000)

    def test_add_timeslot_without_weekday_does_not_create(self):
        """沒有勾選任何星期時應擋下，不建立時段"""
        self.client.force_login(self.officer)
        self.client.post(reverse('public:venue_edit', args=[self.venue.pk]), {
            'add_timeslot': '1', 'start_time': '09:00', 'end_time': '12:00',
        })
        self.assertEqual(self.venue.time_slots.count(), 0)

    def test_delete_timeslot(self):
        """可刪除既有時段"""
        slot = VenueTimeSlot.objects.create(
            venue=self.venue, is_sat=True, start_time='09:00', end_time='12:00',
        )
        self.client.force_login(self.officer)
        self.client.post(reverse('public:venue_timeslot_delete', args=[slot.pk]))
        self.assertFalse(VenueTimeSlot.objects.filter(pk=slot.pk).exists())

    # ── 刪除場地：限管理員 ──────────────────────────────

    def test_officer_cannot_delete_venue(self):
        """一般幹部無法刪除場地"""
        self.client.force_login(self.officer)
        r = self.client.post(reverse('public:venue_delete', args=[self.venue.pk]), follow=True)
        self.assertTrue(Venue.objects.filter(pk=self.venue.pk).exists())
        self.assertContains(r, '權限不足')

    def test_admin_can_delete_venue(self):
        """管理員可刪除沒有被引用的場地"""
        self.client.force_login(self.admin)
        self.client.post(reverse('public:venue_delete', args=[self.venue.pk]))
        self.assertFalse(Venue.objects.filter(pk=self.venue.pk).exists())

    def test_admin_cannot_delete_venue_referenced_by_event(self):
        """
        場地被演出活動引用（PROTECT）時，即使是管理員也無法刪除，
        應顯示友善錯誤訊息並保留資料，而不是讓伺服器噴 500。
        """
        from django.utils import timezone
        from apps.events.models import PerformanceEvent

        PerformanceEvent.objects.create(
            name='測試演出', type='concert', performance_date=timezone.now(),
            performance_venue=self.venue,
        )
        self.client.force_login(self.admin)
        r = self.client.post(reverse('public:venue_delete', args=[self.venue.pk]), follow=True)
        self.assertTrue(Venue.objects.filter(pk=self.venue.pk).exists())
        self.assertContains(r, '已被演出活動或排練引用')
