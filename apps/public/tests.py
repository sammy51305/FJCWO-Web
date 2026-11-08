import datetime as dt
import io
import logging
import re
from pathlib import Path

from django.conf import settings
from django.test import Client, TestCase, override_settings
from django.urls import path, reverse
from django.utils import timezone

from apps.accounts.models import User
from .models import CharterContent, Venue, VenueTimeSlot


class IndexDashboardLeaveResultTest(TestCase):
    """首頁 Dashboard 顯示請假審核結果通知"""

    def setUp(self):
        from apps.events.models import LeaveRequest, PerformanceEvent, Rehearsal

        self.member = User.objects.create_user(
            username='dash_member', password='x', name='首頁測試團員',
            email='dash_member@test.local', role=User.Role.MEMBER,
        )
        venue = Venue.objects.create(name='首頁測試場地', type=Venue.Type.REHEARSAL)
        event = PerformanceEvent.objects.create(
            name='首頁測試演出', type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now(), performance_venue=venue,
        )
        self.rehearsal = Rehearsal.objects.create(
            event=event, sequence=1, date=timezone.now(), venue=venue,
        )
        self.url = reverse('public:index')

    def test_unseen_approved_leave_shown_on_dashboard(self):
        """核准但團員還沒看過的請假結果，應出現在首頁"""
        from apps.events.models import LeaveRequest

        LeaveRequest.objects.create(
            member=self.member, rehearsal=self.rehearsal, reason='請假',
            status=LeaveRequest.Status.APPROVED, result_seen=False,
        )
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '已核准')

    def test_unseen_rejected_leave_shown_on_dashboard(self):
        """拒絕但團員還沒看過的請假結果，應出現在首頁"""
        from apps.events.models import LeaveRequest

        LeaveRequest.objects.create(
            member=self.member, rehearsal=self.rehearsal, reason='請假',
            status=LeaveRequest.Status.REJECTED, result_seen=False,
        )
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '被拒絕')

    def test_pending_leave_not_shown_as_result(self):
        """待審核的請假不應出現在審核結果通知裡"""
        from apps.events.models import LeaveRequest

        LeaveRequest.objects.create(
            member=self.member, rehearsal=self.rehearsal, reason='請假',
            status=LeaveRequest.Status.PENDING,
        )
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertNotContains(r, '已核准')
        self.assertNotContains(r, '被拒絕')

    def test_result_marked_seen_after_dashboard_view(self):
        """看過一次首頁後，result_seen 應變 True，之後查詢就是「已讀」"""
        from apps.events.models import LeaveRequest

        leave = LeaveRequest.objects.create(
            member=self.member, rehearsal=self.rehearsal, reason='請假',
            status=LeaveRequest.Status.APPROVED, result_seen=False,
        )
        self.client.force_login(self.member)
        self.client.get(self.url)
        leave.refresh_from_db()
        self.assertTrue(leave.result_seen)

    def test_already_seen_result_not_shown_again(self):
        """已經看過的審核結果，第二次進首頁不應再顯示"""
        from apps.events.models import LeaveRequest

        LeaveRequest.objects.create(
            member=self.member, rehearsal=self.rehearsal, reason='請假',
            status=LeaveRequest.Status.APPROVED, result_seen=True,
        )
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertNotContains(r, '已核准')

    def test_other_members_result_not_shown(self):
        """不會看到其他團員的請假審核結果"""
        from apps.events.models import LeaveRequest

        other_member = User.objects.create_user(
            username='dash_other', password='x', name='別的團員',
            email='dash_other@test.local', role=User.Role.MEMBER,
        )
        LeaveRequest.objects.create(
            member=other_member, rehearsal=self.rehearsal, reason='請假',
            status=LeaveRequest.Status.APPROVED, result_seen=False,
        )
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertNotContains(r, '已核准')


class IndexOfficerPendingReviewTest(TestCase):
    """首頁「待我處理的事項」：幹部待審排練請假筆數，與團員視角「我的請假」分開（#12）"""

    def setUp(self):
        from apps.events.models import PerformanceEvent, Rehearsal

        self.officer = User.objects.create_user(
            username='dash_officer', password='x', name='首頁幹部',
            email='dash_officer@test.local', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='dash_mem', password='x', name='首頁團員',
            email='dash_mem@test.local', role=User.Role.MEMBER,
        )
        venue = Venue.objects.create(name='待審場地', type=Venue.Type.REHEARSAL)
        event = PerformanceEvent.objects.create(
            name='待審演出', type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now(), performance_venue=venue,
        )
        self.rehearsal = Rehearsal.objects.create(
            event=event, sequence=1, date=timezone.now(), venue=venue,
        )
        self.url = reverse('public:index')

    def _make_pending_leave(self, member):
        from apps.events.models import LeaveRequest
        return LeaveRequest.objects.create(
            member=member, rehearsal=self.rehearsal, reason='請假',
            status=LeaveRequest.Status.PENDING,
        )

    def test_officer_sees_todo_block_with_leave_review_link(self):
        """有待審排練請假時，首頁出現「待我處理的事項」並連到請假審核頁"""
        self._make_pending_leave(self.member)
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '待我處理的事項')
        self.assertContains(r, '排練請假待審核')
        self.assertContains(r, reverse('events:leave_review_list'))

    def test_member_does_not_see_todo_block(self):
        """一般團員看不到「待我處理的事項」，也沒有 pending_leaves_count"""
        self._make_pending_leave(self.member)
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertNotContains(r, '待我處理的事項')
        self.assertIsNone(r.context.get('pending_leaves_count'))

    def test_officer_with_no_pending_hides_todo_block(self):
        """沒有任何待審／待確認時，不顯示「待我處理的事項」"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.context['pending_leaves_count'], 0)
        self.assertNotContains(r, '待我處理的事項')

    def test_my_leaves_card_is_own_only_review_count_is_all(self):
        """「我的請假」只含自己送的；「待我處理」的排練請假筆數是全團（視角分開）"""
        self._make_pending_leave(self.officer)   # 自己送的
        self._make_pending_leave(self.member)    # 別人送的
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '我的請假（待審核）')
        self.assertEqual(r.context['pending_leaves'].count(), 1)   # 我的卡片：只有自己
        self.assertEqual(r.context['pending_leaves_count'], 2)     # 待我處理：全團


class IndexNextRehearsalTest(TestCase):
    """首頁「下次排練」卡片挑哪一場（當天的排練整天都要留著）"""

    def setUp(self):
        from apps.events.models import PerformanceEvent

        self.member = User.objects.create_user(
            username='card_member', password='x', name='卡片測試團員',
            email='card_member@test.local', role=User.Role.MEMBER,
        )
        self.venue = Venue.objects.create(name='卡片測試場地', type=Venue.Type.REHEARSAL)
        self.event = PerformanceEvent.objects.create(
            name='卡片測試演出', type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now(), performance_venue=self.venue,
        )
        self.today = timezone.localdate()

    def _at(self, day_offset, hour):
        """回傳「今天 + day_offset 天」的 hour 點整（本地時區）。

        測試不看真實時鐘幾點——時間一律由今天的日期推算、再把 now 直接餵給
        `_dashboard_rehearsal`，否則清晨或深夜跑測試會因為跨日而飄。
        """
        return timezone.make_aware(
            dt.datetime.combine(self.today + dt.timedelta(days=day_offset),
                                dt.time(hour, 0)),
            timezone.get_current_timezone(),
        )

    def _rehearsal(self, sequence, moment):
        from apps.events.models import Rehearsal

        return Rehearsal.objects.create(
            event=self.event, sequence=sequence, date=moment, venue=self.venue,
        )

    def test_rehearsal_already_started_today_stays_on_card(self):
        """排練開始時刻一過，卡片仍要顯示這場，不能跳成下一場

        這是團員最需要簽到、看排練日誌的時間點（2026-09-19 幹部回饋）。
        """
        from apps.public.views import _dashboard_rehearsal

        today_rehearsal = self._rehearsal(1, self._at(0, 19))
        self._rehearsal(2, self._at(7, 19))

        rehearsal, started = _dashboard_rehearsal(self._at(0, 20))
        self.assertEqual(rehearsal, today_rehearsal)
        self.assertTrue(started)

    def test_upcoming_rehearsal_shown_when_none_started_today(self):
        """今天還沒有任何排練開始時，顯示最近一場未來的排練"""
        from apps.public.views import _dashboard_rehearsal

        soon = self._rehearsal(1, self._at(7, 19))
        self._rehearsal(2, self._at(14, 19))

        rehearsal, started = _dashboard_rehearsal(self._at(0, 20))
        self.assertEqual(rehearsal, soon)
        self.assertFalse(started)

    def test_today_rehearsal_wins_over_later_same_day(self):
        """同一天多場時取最近開始的那場，不是早上已結束的那場"""
        from apps.public.views import _dashboard_rehearsal

        self._rehearsal(1, self._at(0, 9))
        evening = self._rehearsal(2, self._at(0, 19))

        rehearsal, started = _dashboard_rehearsal(self._at(0, 20))
        self.assertEqual(rehearsal, evening)
        self.assertTrue(started)

    def test_yesterday_rehearsal_not_shown(self):
        """昨天的排練隔天就要換掉，不會賴在首頁"""
        from apps.public.views import _dashboard_rehearsal

        self._rehearsal(1, self._at(-1, 19))

        rehearsal, started = _dashboard_rehearsal(self._at(0, 20))
        self.assertIsNone(rehearsal)
        self.assertFalse(started)

    def test_no_rehearsal_at_all(self):
        """完全沒有排練時回傳 None，不炸掉"""
        from apps.public.views import _dashboard_rehearsal

        rehearsal, started = _dashboard_rehearsal(self._at(0, 20))
        self.assertIsNone(rehearsal)
        self.assertFalse(started)

    def test_card_renders_path_hint(self):
        """卡片要標出這場排練平常自己要從哪裡點進去"""
        self._rehearsal(1, self._at(0, 0))
        self.client.force_login(self.member)

        r = self.client.get(reverse('public:index'))
        self.assertContains(r, '路徑：演出活動')
        self.assertContains(r, '第 1 次排練')

    def test_card_marks_today_rehearsal_in_progress(self):
        """當天已開始的排練，卡片標題改成「今天的排練」並標進行中"""
        self._rehearsal(1, self._at(0, 0))
        self.client.force_login(self.member)

        r = self.client.get(reverse('public:index'))
        self.assertContains(r, '今天的排練')
        self.assertContains(r, '進行中')


class IndexPerformanceBlockTest(TestCase):
    """首頁「演出活動」區塊：下次排練、我的請假、下載音樂會譜包在一起"""

    def setUp(self):
        from apps.events.models import PerformanceEvent

        self.member = User.objects.create_user(
            username='perf_member', password='x', name='區塊測試團員',
            email='perf_member@test.local', role=User.Role.MEMBER,
        )
        self.venue = Venue.objects.create(name='區塊測試場地', type=Venue.Type.PERFORMANCE)
        self.PerformanceEvent = PerformanceEvent

    def _event(self, name, days, status=None):
        return self.PerformanceEvent.objects.create(
            name=name, type=self.PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now() + dt.timedelta(days=days),
            performance_venue=self.venue,
            status=status or self.PerformanceEvent.Status.CONFIRMED,
        )

    def test_block_contains_the_three_cards(self):
        """首頁有「演出活動」區塊，內含下次排練、我的請假、下載音樂會譜"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('public:index'))
        for text in ('演出活動', '下次排練', '我的請假', '下載音樂會譜'):
            self.assertContains(r, text)

    def test_download_card_links_to_each_upcoming_event(self):
        """下載卡片列出近期演出，並連到該場的分譜下載頁"""
        ev = self._event('秋季公演', 30)
        self.client.force_login(self.member)
        r = self.client.get(reverse('public:index'))
        self.assertContains(r, '秋季公演')
        self.assertContains(r, reverse('scores:performance_parts', args=[ev.pk]))

    def test_download_card_skips_finished_and_cancelled(self):
        """已結束、已取消的演出不列在下載卡片"""
        S = self.PerformanceEvent.Status
        self._event('已結束的演出', -30, S.FINISHED)
        self._event('已取消的演出', 10, S.CANCELLED)
        self.client.force_login(self.member)
        r = self.client.get(reverse('public:index'))
        self.assertNotContains(r, '已結束的演出')
        self.assertNotContains(r, '已取消的演出')
        self.assertContains(r, '近期沒有演出活動')

    def test_download_card_shows_at_most_three_nearest(self):
        """最多列最近的 3 場"""
        for i in range(5):
            self._event(f'第{i}場演出', 10 + i)
        self.client.force_login(self.member)
        r = self.client.get(reverse('public:index'))
        self.assertEqual(len(r.context['download_events']), 3)
        self.assertEqual(r.context['download_events'][0].name, '第0場演出')


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

    # ── 列表：用途說明與使用次數 ──────────────────────────

    def test_list_explains_what_the_page_is_for(self):
        """頁面要寫清楚用途與時機（幹部回饋：看不出這功能要幹嘛）"""
        self.client.force_login(self.officer)
        r = self.client.get(self.list_url)
        self.assertContains(r, '場地主檔')
        self.assertContains(r, '不是預約系統')

    def test_list_shows_usage_counts(self):
        """列出每個場地被幾場演出／排練用到

        兩個 annotate 各自 JOIN，沒有 `distinct=True` 的話 1 場演出 × 2 場排練
        會互相相乘、兩邊都變成 2——這個測試就是要擋住那種算法。
        """
        from apps.events.models import PerformanceEvent, Rehearsal

        event = PerformanceEvent.objects.create(
            name='使用次數測試演出', type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now(), performance_venue=self.venue,
        )
        for sequence in (1, 2):
            Rehearsal.objects.create(
                event=event, sequence=sequence, date=timezone.now(), venue=self.venue,
            )

        self.client.force_login(self.officer)
        r = self.client.get(self.list_url)

        venue = r.context['venues'][0]
        self.assertEqual(venue.event_count, 1)
        self.assertEqual(venue.rehearsal_count, 2)
        self.assertContains(r, '演出 1')
        self.assertContains(r, '排練 2')

    def test_unused_venue_marked_as_unused(self):
        """沒被任何演出／排練用到的場地標「尚未使用」"""
        self.client.force_login(self.officer)
        r = self.client.get(self.list_url)
        self.assertContains(r, '尚未使用')

    def test_empty_state_guides_first_venue(self):
        """一筆場地都沒有時，給引導而不是「沒有符合條件」"""
        Venue.objects.all().delete()
        self.client.force_login(self.officer)
        r = self.client.get(self.list_url)
        self.assertContains(r, '新增第一個場地')
        self.assertNotContains(r, '沒有符合條件的場地')

    def test_no_search_result_is_not_empty_state(self):
        """搜尋不到跟一筆都沒有是兩回事，提示不能互換"""
        self.client.force_login(self.officer)
        r = self.client.get(self.list_url, {'q': '不存在的場地'})
        self.assertContains(r, '沒有符合條件的場地')
        self.assertNotContains(r, '新增第一個場地')

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


class DemoCommandTest(TestCase):
    """
    demo 資料的建立與清除指令（seed_demo / clear_demo）。
    重點在驗證 clear_demo 的刪除順序能通過各處的 PROTECT 限制，
    以及 seed_demo 可重複執行不會產生重複資料。
    """

    @classmethod
    def setUpTestData(cls):
        # fixtures 放在專案根目錄（非 app 內），故用 loaddata 帶路徑載入
        from django.core.management import call_command
        call_command('loaddata', 'fixtures/instruments.json',
                     'fixtures/sections.json', 'fixtures/venues.json', verbosity=0)

    def _demo_user_qs(self):
        from apps.accounts.models import User
        return User.objects.filter(username__startswith='demo_')

    def test_seed_creates_demo_data(self):
        """seed_demo 建立帳號、演出、樂譜、財產、會費等展示資料"""
        from django.core.management import call_command
        from apps.events.models import PerformanceEvent
        from apps.finance.models import MembershipFee
        from apps.scores.models import Score

        call_command('seed_demo', '--no-files', verbosity=0)

        self.assertEqual(self._demo_user_qs().count(), 13)   # 1 幹部 + 12 團員
        self.assertTrue(PerformanceEvent.objects.filter(
            name='2026 秋季公演「聲之所向」').exists())
        self.assertEqual(Score.objects.count(), 6)
        self.assertTrue(MembershipFee.objects.filter(status='reported').exists())

    def test_seed_is_idempotent(self):
        """seed_demo 重複執行不會產生重複資料"""
        from django.core.management import call_command
        from apps.scores.models import Score

        call_command('seed_demo', '--no-files', verbosity=0)
        first_users = self._demo_user_qs().count()
        first_scores = Score.objects.count()

        call_command('seed_demo', '--no-files', verbosity=0)
        self.assertEqual(self._demo_user_qs().count(), first_users)
        self.assertEqual(Score.objects.count(), first_scores)

    def test_clear_removes_everything_seeded(self):
        """
        clear_demo 能完整清除 seed_demo 建立的資料。
        刪除順序必須先處理 PROTECT 的引用方（Announcement.created_by、
        MembershipFee.period、Setlist.score），否則會拋 ProtectedError。
        """
        from django.core.management import call_command
        from apps.announcements.models import Announcement
        from apps.assets.models import BandProperty
        from apps.events.models import PerformanceEvent, Rehearsal
        from apps.finance.models import FeePeriod, MembershipFee
        from apps.scores.models import Score

        call_command('seed_demo', '--no-files', verbosity=0)
        call_command('clear_demo', '--noinput', verbosity=0)

        self.assertEqual(self._demo_user_qs().count(), 0)
        self.assertEqual(PerformanceEvent.objects.filter(
            name='2026 秋季公演「聲之所向」').count(), 0)
        self.assertEqual(Rehearsal.objects.count(), 0)
        self.assertEqual(Score.objects.count(), 0)
        self.assertEqual(BandProperty.objects.count(), 0)
        self.assertEqual(MembershipFee.objects.count(), 0)
        self.assertEqual(Announcement.objects.count(), 0)
        self.assertEqual(FeePeriod.objects.filter(year=2026, term='second').count(), 0)

    def test_clear_keeps_master_data_and_other_users(self):
        """clear_demo 只刪 demo 資料，不動主檔與非 demo 帳號"""
        from django.core.management import call_command
        from apps.accounts.models import InstrumentFamily, SectionType, User
        from apps.public.models import Venue

        keeper = User.objects.create_user(
            username='real_officer', password='x', name='真實幹部',
            email='real@test.local', role=User.Role.OFFICER,
        )
        fam_before = InstrumentFamily.objects.count()
        sec_before = SectionType.objects.count()
        venue_before = Venue.objects.count()

        call_command('seed_demo', '--no-files', verbosity=0)
        call_command('clear_demo', '--noinput', verbosity=0)

        self.assertTrue(User.objects.filter(pk=keeper.pk).exists())
        self.assertEqual(InstrumentFamily.objects.count(), fam_before)
        self.assertEqual(SectionType.objects.count(), sec_before)
        self.assertEqual(Venue.objects.count(), venue_before)

    def test_clear_dry_run_changes_nothing(self):
        """--dry-run 只列出將刪除的資料，不動資料庫"""
        from django.core.management import call_command

        call_command('seed_demo', '--no-files', verbosity=0)
        before = self._demo_user_qs().count()

        call_command('clear_demo', '--dry-run', verbosity=0)
        self.assertEqual(self._demo_user_qs().count(), before)


class RobotsTxtTest(TestCase):
    """robots.txt 與 X-Robots-Tag（測試站禁止收錄、正式站只擋內部路徑）"""

    def setUp(self):
        self.url = reverse('robots_txt')

    def test_served_at_site_root_as_plain_text(self):
        """robots.txt 掛在網站根目錄、回純文字（爬蟲只認這個位置）"""
        r = self.client.get('/robots.txt')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/plain')

    def test_unauthenticated_can_read(self):
        """未登入可讀——爬蟲不會登入"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'User-agent: *')

    @override_settings(ROBOTS_NOINDEX=True)
    def test_noindex_mode_disallows_everything(self):
        """測試站模式：整站禁止收錄"""
        r = self.client.get(self.url)
        self.assertContains(r, 'Disallow: /')
        self.assertNotContains(r, 'Disallow: /admin/')

    @override_settings(ROBOTS_NOINDEX=False)
    def test_normal_mode_only_blocks_internal_paths(self):
        """正式站模式：只擋內部路徑，公開頁仍可被收錄"""
        r = self.client.get(self.url)
        body = r.content.decode()
        self.assertIn('Disallow: /accounts/', body)
        self.assertIn('Disallow: /finance/', body)
        # 沒有「整站禁止」那一行，否則公開頁也會被擋
        self.assertNotIn('Disallow: /\n', body)

    @override_settings(ROBOTS_NOINDEX=True)
    def test_noindex_header_added_to_every_response(self):
        """測試站模式：每個回應都帶 X-Robots-Tag（robots.txt 只擋爬取、不擋收錄）"""
        for url in ('/', reverse('public:about'), self.url):
            with self.subTest(url=url):
                self.assertEqual(
                    self.client.get(url)['X-Robots-Tag'], 'noindex, nofollow'
                )

    @override_settings(ROBOTS_NOINDEX=False)
    def test_no_header_in_normal_mode(self):
        """正式站模式不加 header，公開頁才收錄得到"""
        self.assertNotIn('X-Robots-Tag', self.client.get('/'))


def _raise_boom(request):
    """故意噴例外的 view，只給 LoggingConfigTest 用。"""
    raise RuntimeError('LOGGING 測試用的例外')


class _BoomUrlConf:
    """臨時 URLConf：Django 只要求這個物件有 `urlpatterns`。

    用 class 而不是 `SimpleNamespace`——`get_resolver` 會對它做 lru_cache，
    參數必須可雜湊。
    """

    urlpatterns = [path('boom/', _raise_boom)]


class LoggingConfigTest(TestCase):
    """DEBUG=False 時 500 的 traceback 要印得出來（Render Logs 才查得到線上錯誤）"""

    def _console_handler(self):
        handlers = logging.getLogger('django.request').handlers
        self.assertTrue(handlers, 'django.request 沒有掛任何 handler')
        return handlers[0]

    def test_console_handler_is_not_limited_to_debug(self):
        """handler 不能帶 require_debug_true——那正是 Django 預設值的問題所在

        預設設定的 console handler 有 `require_debug_true` 過濾器，`DEBUG=False`
        的線上站噴 500 時什麼都不會印，等於出錯無從查起。
        """
        handler = self._console_handler()
        self.assertIsInstance(handler, logging.StreamHandler)
        self.assertEqual(handler.filters, [])

    @override_settings(
        DEBUG=False,
        ROOT_URLCONF=_BoomUrlConf,
    )
    def test_unhandled_exception_traceback_written_to_console(self):
        """DEBUG=False 時，未捕捉的例外要連 traceback 一起寫進 stderr"""
        handler = self._console_handler()
        buffer = io.StringIO()
        original = handler.setStream(buffer)
        # raise_request_exception 只能在 Client 建構時指定；預設的 self.client
        # 會把 view 的例外往外丟，測不到「伺服器回 500 並記 log」的行為。
        client = Client(raise_request_exception=False)
        try:
            r = client.get('/boom/')
        finally:
            handler.setStream(original)

        self.assertEqual(r.status_code, 500)
        written = buffer.getvalue()
        self.assertIn('RuntimeError', written)
        self.assertIn('LOGGING 測試用的例外', written)


class TemplateCommentSyntaxTest(TestCase):
    """模板註解語法檢查：`{# #}` 只能單行，多行會整段印在頁面上"""

    # 換行夾在 {# 與 #} 之間 → Django 不視為註解，原樣輸出給使用者看
    MULTILINE_HASH_COMMENT = re.compile(r'\{#(?:(?!#\}).)*?\n(?:(?!#\}).)*?#\}', re.S)

    def test_no_multiline_hash_comments(self):
        """
        Django 的 `{# #}` **只支援單行**，中間有換行就不是註解，
        整段（含 `{#`、`#}`）會原樣渲染到頁面上被使用者看到。多行註解要用
        `{% comment %}...{% endcomment %}`。

        2026-09-09 一次抓到 5 處，橫跨 #11／#13-4／#13-8／#13-9 與入團申請刪除權限，
        其中幾處已經漏在畫面上一段時間——一般的 view 測試抓不到（頁面照樣 200、
        該有的元素也都在），只有真的用眼睛看才會發現，所以改用這種結構檢查釘住。
        """
        offenders = []
        for template_dir in settings.TEMPLATES[0]['DIRS']:
            for path in sorted(Path(template_dir).rglob('*.html')):
                text = path.read_text(encoding='utf-8')
                for match in self.MULTILINE_HASH_COMMENT.finditer(text):
                    line = text[:match.start()].count('\n') + 1
                    offenders.append(f'{path}:{line}')
        self.assertEqual(
            offenders, [],
            '以下位置用了多行 {# #}，會直接印在頁面上，請改成 '
            '{% comment %}...{% endcomment %}：\n  ' + '\n  '.join(offenders)
        )


class ImportSheetCommandTest(TestCase):
    """manage.py import_sheet：團練紀錄試算表（.xlsx）匯入系統"""

    def setUp(self):
        import tempfile

        from apps.events.models import PerformanceEvent

        self.officer = User.objects.create_user(
            username='sheet_officer', password='x', name='匯入幹部',
            email='sheet_officer@test.local', role=User.Role.OFFICER,
        )
        self.member = User.objects.create_user(
            username='sheet_member', password='x', name='已有帳號',
            email='has_account@test.local', role=User.Role.MEMBER,
        )
        self.venue = Venue.objects.create(name='匯入測試場地', type=Venue.Type.REHEARSAL)
        self.event = PerformanceEvent.objects.create(
            name='匯入測試演出', type=PerformanceEvent.Type.CONCERT,
            performance_date=timezone.now() + dt.timedelta(days=60), performance_venue=self.venue,
        )
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    def _workbook(self, *, rehearsal_event='匯入測試演出'):
        """依試算表範本的欄位建一份 .xlsx，回傳路徑。"""
        import openpyxl

        wb = openpyxl.Workbook()
        wb.remove(wb.active)

        ws = wb.create_sheet('團員名冊')
        ws.append(['姓名', '身分', '樂器', '聲部', '手機', 'Email', '狀態', 'LINE ID', '備註'])
        ws.append(['已有帳號', '團員', '長笛', '', '', 'HAS_ACCOUNT@test.local', '在團', '', ''])
        ws.append(['新團員', '團員', '小號', '', '0912000000', 'new_member@test.local', '在團', '', ''])
        ws.append(['沒有信箱', '團員', '豎笛', '', '', '', '在團', '', ''])

        ws = wb.create_sheet('排練日程')
        ws.append(['排練日期', '開始時間', '場地', '所屬演出', '第幾次排練', '今日進度', '備註'])
        ws.append([dt.datetime(2026, 11, 7), dt.time(19, 0), '匯入測試場地', rehearsal_event, 1, '', ''])
        ws.append([dt.datetime(2026, 11, 14), None, '匯入測試場地', rehearsal_event, None, '', ''])
        ws.append([dt.datetime(2026, 11, 21), dt.time(19, 0), '不存在的場地', rehearsal_event, None, '', ''])

        ws = wb.create_sheet('請假紀錄')
        ws.append(['申請時間', '姓名', '排練日期', '請假原因', '審核狀態', '審核幹部', '審核時間', '是否逾時'])
        ws.append([dt.datetime(2026, 11, 10, 20, 0), '已有帳號', dt.datetime(2026, 11, 14),
                   '出差', '核准', '匯入幹部', dt.datetime(2026, 11, 10, 21, 0), ''])
        ws.append([dt.datetime(2026, 11, 6, 9, 0), '新團員', dt.datetime(2026, 11, 7),
                   '考試', '待審核', '', None, ''])

        ws = wb.create_sheet('出席紀錄')
        # 12/05 這欄還沒點名、系統也沒有這場排練：不該被報錯
        header = ['姓名', '樂器', '出席', '請假', '缺席', '出席率', dt.datetime(2026, 11, 7), dt.datetime(2026, 12, 5)]
        ws.append(header)
        for label in ('本次出席人數', '本次請假人數', '本次缺席人數'):
            ws.append([label])
        ws.append(['已有帳號', '長笛', 1, 0, 0, 1, '出席'])
        ws.append(['新團員', '小號', 0, 0, 1, 0, '缺席'])

        ws = wb.create_sheet('團費期別')
        ws.append(['期別', '年份', '期', '團費金額', '繳費開始日', '繳費截止日'])
        ws.append(['2026 下期', 2026, '下期', 4500, dt.datetime(2026, 11, 1), dt.datetime(2026, 12, 31)])

        ws = wb.create_sheet('團費收繳')
        ws.append(['姓名', '期別', '應繳金額', '實收金額', '繳費方式', '帳號末五碼',
                   '繳費日期', '收款幹部', '狀態', '備註'])
        ws.append(['已有帳號', '2026 下期', 4500, 4500, '轉帳', '01234',
                   dt.datetime(2026, 11, 2), '匯入幹部', '已繳', ''])
        # 先填了姓名、還沒收錢的列：狀態空白＝還沒繳，連還沒帳號的人也不該報錯
        ws.append(['新團員', '2026 下期', 4500, None, None, None, None, None, None, ''])

        ws = wb.create_sheet('支出紀錄')
        ws.append(['日期', '項目', '金額', '說明', '經手人', '收據'])
        ws.append([dt.datetime(2026, 11, 1), '團練室', 3000, '11/1 團練', '匯入幹部', True])
        ws.append([dt.datetime(2026, 11, 1), '團練室', 3000, '11/1 團練', '匯入幹部', True])
        ws.append([dt.datetime(2026, 11, 3), '指揮費用', 3000, '', '', False])
        ws.append([dt.datetime(2026, 11, 4), '茶水', 200, '', '', False])
        for _ in range(3):      # 真實試算表：空白列的勾選框是 FALSE，不能被當成資料
            ws.append([None, None, None, None, None, False])

        path = Path(self.tmpdir.name) / 'sheet.xlsx'
        wb.save(path)
        return str(path)

    def _run(self, *extra):
        from django.core.management import call_command

        out = io.StringIO()
        call_command('import_sheet', self._workbook(), '--operator', 'sheet_officer', *extra, stdout=out)
        return out.getvalue()

    def test_dry_run_writes_nothing(self):
        """沒加 --commit 是試跑：報告照出，但資料庫完全不變"""
        from apps.accounts.models import Registration
        from apps.events.models import Rehearsal
        from apps.finance.models import FeePeriod

        output = self._run()
        self.assertIn('這是試跑', output)
        self.assertIn('新增 2 筆', output)       # 排練日程那段的報告照樣算得出來
        self.assertFalse(Rehearsal.objects.exists())
        self.assertFalse(Registration.objects.exists())
        self.assertFalse(FeePeriod.objects.exists())

    def test_roster_creates_registration_only_for_members_without_account(self):
        """名冊：Email（不分大小寫）對到的人不動；沒帳號有 Email → 待審核入團申請；都沒有 → 列入報告"""
        from apps.accounts.models import Registration

        output = self._run('--commit')
        regs = list(Registration.objects.values_list('email', 'status'))
        self.assertEqual(regs, [('new_member@test.local', Registration.Status.PENDING)])
        self.assertEqual(User.objects.count(), 2)       # 不直接建帳號（DESIGN §4.2）
        self.assertIn('沒有信箱 沒有帳號也沒有 Email', output)

    def test_rehearsals_created_with_default_time_and_sequence(self):
        """排練：沒填時間用預設 19:00、沒填次數接在最後；場地找不到列入報告不建立"""
        from apps.events.models import Rehearsal

        output = self._run('--commit')
        rehearsals = list(Rehearsal.objects.order_by('date'))
        self.assertEqual([r.sequence for r in rehearsals], [1, 2])
        second = timezone.localtime(rehearsals[1].date)
        self.assertEqual((second.date(), second.hour), (dt.date(2026, 11, 14), 19))
        self.assertIn('場地「不存在的場地」在系統找不到', output)

    def test_missing_event_is_reported(self):
        """所屬演出在系統找不到就不建排練，並指出要先建演出活動"""
        from django.core.management import call_command

        from apps.events.models import Rehearsal

        out = io.StringIO()
        call_command('import_sheet', self._workbook(rehearsal_event='沒這場'),
                     '--operator', 'sheet_officer', '--commit', stdout=out)
        self.assertFalse(Rehearsal.objects.exists())
        self.assertIn('所屬演出「沒這場」在系統找不到', out.getvalue())

    def test_attendance_and_leaves(self):
        """出席照矩陣寫入；核准的請假同步出席為請假；還沒帳號的人略過並提示核准後重跑；尚未點名的日期欄不報錯"""
        from apps.events.models import LeaveRequest, RehearsalAttendance

        output = self._run('--commit')
        att = {(timezone.localtime(a.rehearsal.date).date(), a.member.name): a.status
               for a in RehearsalAttendance.objects.select_related('rehearsal', 'member')}
        self.assertEqual(att, {
            (dt.date(2026, 11, 7), '已有帳號'): RehearsalAttendance.Status.PRESENT,
            (dt.date(2026, 11, 14), '已有帳號'): RehearsalAttendance.Status.LEAVE,
        })
        leave = LeaveRequest.objects.get()
        self.assertEqual(leave.status, LeaveRequest.Status.APPROVED)
        self.assertEqual(leave.reviewed_by, self.officer)
        self.assertEqual(timezone.localtime(leave.created_at).date(), dt.date(2026, 11, 10))
        self.assertIn('新團員 尚無系統帳號（入團申請核准後再匯入一次）', output)
        self.assertNotIn('12/05', output)     # 尚未點名的日期欄不對照、不報錯

    def test_paid_fee_creates_income_record(self):
        """團費：建立期別；已繳的那筆比照系統操作產生收支明細收入，登記者是 --operator；狀態空白的列不匯入、不報錯"""
        from apps.finance.models import FeePeriod, FinanceRecord, MembershipFee

        output = self._run('--commit')
        period = FeePeriod.objects.get()
        self.assertEqual((period.year, period.term, period.amount), (2026, 'second', 4500))
        fee = MembershipFee.objects.get()
        self.assertEqual((fee.status, fee.payment_method, fee.account_last5),
                         ('paid', 'transfer', '01234'))
        self.assertEqual(fee.collected_by, self.officer)
        record = FinanceRecord.objects.get(type=FinanceRecord.Type.INCOME)
        self.assertEqual((record.amount, record.date, record.created_by),
                         (4500, dt.date(2026, 11, 2), self.officer))
        self.assertEqual(fee.finance_record, record)
        self.assertIn('狀態空白＝尚未繳費 1 列', output)
        self.assertNotIn('新團員 尚無系統帳號', output.split('■ 團費收繳')[1].split('■')[0])

    def test_student_fee_uses_sheet_amount_due(self):
        """學生團費：沒填實收時用試算表算好的應繳金額（學生 1,000），不被期別金額 4,500 蓋掉"""
        import openpyxl
        from django.core.management import call_command

        from apps.finance.models import FinanceRecord, MembershipFee

        path = self._workbook()
        wb = openpyxl.load_workbook(path)
        wb['團費收繳'].append(['匯入幹部', '2026 下期', 1000, None, '現金', None,
                              dt.datetime(2026, 11, 3), '匯入幹部', '已繳', ''])
        wb.save(path)
        call_command('import_sheet', path, '--operator', 'sheet_officer', '--commit', stdout=io.StringIO())
        fee = MembershipFee.objects.get(member=self.officer)
        self.assertEqual(fee.amount, 1000)
        self.assertEqual(fee.finance_record.amount, 1000)
        self.assertEqual(FinanceRecord.objects.filter(type=FinanceRecord.Type.INCOME).count(), 2)

    def test_expenses_become_finance_records(self):
        """支出紀錄：預算項目對到系統分類、描述保留原項目；兩筆一模一樣的支出各建一筆；對不上的項目歸其他並報告"""
        from apps.finance.models import FinanceRecord

        output = self._run('--commit')
        expenses = list(
            FinanceRecord.objects.filter(type=FinanceRecord.Type.EXPENSE)
            .order_by('date', 'id').values_list('date', 'category', 'amount', 'description')
        )
        self.assertEqual(expenses, [
            (dt.date(2026, 11, 1), 'venue', 3000, '團練室：11/1 團練（經手人：匯入幹部）'),
            (dt.date(2026, 11, 1), 'venue', 3000, '團練室：11/1 團練（經手人：匯入幹部）'),
            (dt.date(2026, 11, 3), 'instructor', 3000, '指揮費用'),
            (dt.date(2026, 11, 4), 'other', 200, '茶水'),
        ])
        self.assertTrue(all(
            r.created_by == self.officer
            for r in FinanceRecord.objects.filter(type=FinanceRecord.Type.EXPENSE)
        ))
        self.assertIn('項目「茶水」不在預算項目裡，歸為「其他」', output)
        self.assertNotIn('日期無法辨識', output)     # 只有未勾選勾選框的空白列要被略過

    def test_advanced_expenses_record_officer_advance(self):
        """幹部先墊付：支出照記，再多記一筆「幹部代墊」收入；已歸墊再記一筆「歸還幹部代墊」支出；重跑不重複"""
        import openpyxl
        from django.core.management import call_command

        from apps.finance.models import FinanceRecord

        path = self._workbook()
        wb = openpyxl.load_workbook(path)
        del wb['支出紀錄']
        ws = wb.create_sheet('支出紀錄')
        ws.append(['日期', '項目', '金額', '說明', '經手人', '收據', '經手人先墊付', '已歸墊'])
        ws.append([dt.datetime(2026, 3, 14), '創團行政費', 600, '租會議室', '匯入幹部', False, True, False])
        ws.append([dt.datetime(2026, 3, 16), '創團行政費', 400, '社團章', '匯入幹部', False, True, True])
        ws.append([dt.datetime(2026, 3, 20), '團練室', 100, '', '匯入幹部', False, False, True])
        wb.save(path)

        out = io.StringIO()
        call_command('import_sheet', path, '--operator', 'sheet_officer', '--commit', stdout=out)
        records = FinanceRecord.objects.exclude(category_id='membership')   # 範本裡另有一筆已繳會費
        rows = sorted((t, c, d, int(a)) for t, c, d, a in
                      records.values_list('type', 'category_id', 'date', 'amount'))
        self.assertEqual(rows, sorted([
            ('expense', 'other', dt.date(2026, 3, 14), 600),            # 創團行政費歸「其他」
            ('income', 'officer_advance', dt.date(2026, 3, 14), 600),   # 墊進團帳
            ('expense', 'other', dt.date(2026, 3, 16), 400),
            ('income', 'officer_advance', dt.date(2026, 3, 16), 400),
            ('expense', 'officer_advance', dt.date(2026, 3, 16), 400),  # 已歸墊：歸還
            ('expense', 'venue', dt.date(2026, 3, 20), 100),            # 沒墊付就不產生代墊紀錄
        ]))
        self.assertNotIn('不在預算項目裡', out.getvalue())             # 創團行政費是認得的項目
        self.assertIn('勾了「已歸墊」但沒勾「經手人先墊付」', out.getvalue())
        self.assertTrue(FinanceRecord.objects.get(
            type='income', category_id='officer_advance', amount=600).description.startswith('幹部代墊：'))

        call_command('import_sheet', path, '--operator', 'sheet_officer', '--commit', stdout=io.StringIO())
        self.assertEqual(records.count(), 6)                           # 重跑不重複

    def test_repayment_date_column_is_optional_and_used(self):
        """支出紀錄若有「歸墊日期」欄，歸還那筆用它的日期；沒填才用支出日期"""
        import openpyxl
        from django.core.management import call_command

        from apps.finance.models import FinanceRecord

        path = self._workbook()
        wb = openpyxl.load_workbook(path)
        del wb['支出紀錄']
        ws = wb.create_sheet('支出紀錄')
        ws.append(['日期', '項目', '金額', '說明', '經手人', '收據', '經手人先墊付', '已歸墊', '歸墊日期'])
        ws.append([dt.datetime(2026, 3, 14), '創團行政費', 600, '租會議室', '匯入幹部',
                   False, True, True, dt.datetime(2026, 11, 8)])
        wb.save(path)
        call_command('import_sheet', path, '--operator', 'sheet_officer', '--commit', stdout=io.StringIO())
        repay = FinanceRecord.objects.get(type='expense', category_id='officer_advance')
        self.assertEqual(repay.date, dt.date(2026, 11, 8))

    def test_left_member_without_account_gets_no_registration(self):
        """名冊狀態「離團」且沒有帳號的人：不建入團申請，報告說明原因"""
        import openpyxl
        from django.core.management import call_command

        from apps.accounts.models import Registration

        path = self._workbook()
        wb = openpyxl.load_workbook(path)
        wb['團員名冊'].append(['已離團者', '團員', '其他', '', '', 'left@test.local', '離團', '', ''])
        wb.save(path)
        out = io.StringIO()
        call_command('import_sheet', path, '--operator', 'sheet_officer', '--commit', stdout=out)
        self.assertFalse(Registration.objects.filter(email='left@test.local').exists())
        self.assertIn('已離團者 已離團且沒有帳號', out.getvalue())

    def test_venues_and_events_imported_and_existing_reused(self):
        """場地、演出活動分頁：沒有的建立、系統已有同名的沿用不覆蓋；排練日程可直接用新建的場地與演出"""
        import openpyxl
        from django.core.management import call_command

        from apps.events.models import PerformanceEvent, Rehearsal

        path = self._workbook(rehearsal_event='輔韻之聲')
        wb = openpyxl.load_workbook(path)
        ws = wb.create_sheet('場地')
        ws.append(['場地名稱', '類別', '地址', '聯絡人', '聯絡電話', 'Google Maps 網址', '備註'])
        ws.append(['新排練場', '排練場地', '新北市某路 1 號', '芊雅', '0222690229', 'https://maps.example/x', '團練室'])
        ws.append(['匯入測試場地', '演出場地', '不該覆蓋的地址', '', '', '', ''])      # 系統已有同名：沿用
        ws.append(['類別亂填', '舞台', '', '', '', '', ''])
        ws = wb.create_sheet('演出活動')
        ws.append(['演出名稱', '類型', '演出日期', '演出時間', '演出場地', '狀態', '備註'])
        ws.append(['輔韻之聲', '音樂會', dt.datetime(2027, 1, 24), dt.time(19, 30), '新排練場', '籌備中', ''])
        ws.append(['匯入測試演出', '音樂會', dt.datetime(2027, 3, 1), dt.time(19, 0), '新排練場', '確認', ''])
        ws.append(['找不到場地的演出', '音樂會', dt.datetime(2027, 3, 1), None, '不存在的場地', '籌備中', ''])
        wb.save(path)

        out = io.StringIO()
        call_command('import_sheet', path, '--operator', 'sheet_officer', '--commit', stdout=out)

        venue = Venue.objects.get(name='新排練場')
        self.assertEqual((venue.type, venue.address, venue.contact_person, venue.contact_phone),
                         ('rehearsal', '新北市某路 1 號', '芊雅', '0222690229'))
        old = Venue.objects.get(name='匯入測試場地')
        self.assertEqual((old.type, old.address), ('rehearsal', ''))                   # 沒被覆蓋
        self.assertFalse(Venue.objects.filter(name='類別亂填').exists())
        self.assertIn('不是排練場地／演出場地', out.getvalue())

        event = PerformanceEvent.objects.get(name='輔韻之聲')
        self.assertEqual((event.type, event.status, event.performance_venue), ('concert', 'planning', venue))
        self.assertEqual(timezone.localtime(event.performance_date).strftime('%Y-%m-%d %H:%M'),
                         '2027-01-24 19:30')
        self.assertEqual(PerformanceEvent.objects.filter(name='匯入測試演出').count(), 1)   # 沿用
        self.assertEqual(PerformanceEvent.objects.get(name='匯入測試演出').status, 'planning')
        self.assertFalse(PerformanceEvent.objects.filter(name='找不到場地的演出').exists())
        self.assertIn('演出場地「不存在的場地」', out.getvalue())
        # 排練日程用得到剛建的演出（11/7 這場的場地是 setUp 的舊場地，不受影響）
        self.assertTrue(Rehearsal.objects.filter(event=event).exists())

    def test_officer_loans_become_officer_advance_records(self):
        """幹部借款：借入＝「幹部代墊／借款」收入、還款＝同分類支出；右側統計欄不混進資料；重跑不重複"""
        import openpyxl
        from django.core.management import call_command

        from apps.finance.models import FinanceRecord

        path = self._workbook()
        wb = openpyxl.load_workbook(path)
        ws = wb.create_sheet('幹部借款')
        ws.append(['日期', '幹部', '類型', '金額', '說明', '經手人', '備註', None,
                   '幹部', '借給樂團', '已還', '還欠'])     # 右側有一欄也叫「幹部」
        ws.append([dt.datetime(2026, 8, 19), '林怡君', '借入', 15000, '創團資金', '榮昕緯', '', None,
                   '林怡君', 15000, 5000, 10000])
        ws.append([dt.datetime(2026, 8, 24), '榮昕緯', '借入', 30000, '創團資金', '榮昕緯', '', None,
                   '榮昕緯', 30000, 0, 30000])
        ws.append([dt.datetime(2026, 11, 20), '林怡君', '還款', 5000, '第一次還款', '榮昕緯', '', None,
                   '合計', 45000, 5000, 40000])
        ws.append([None, '林怡君', '借入', 1000, '忘了填日期', '', '', None])
        wb.save(path)

        out = io.StringIO()
        call_command('import_sheet', path, '--operator', 'sheet_officer', '--commit', stdout=out)
        loans = FinanceRecord.objects.filter(category_id='officer_advance')
        self.assertEqual(
            sorted((r.type, int(r.amount), r.date.isoformat()) for r in loans),
            [('expense', 5000, '2026-11-20'), ('income', 15000, '2026-08-19'),
             ('income', 30000, '2026-08-24')],
        )
        self.assertIn('林怡君借給樂團', FinanceRecord.objects.get(amount=15000, category_id='officer_advance').description)
        self.assertIn('歸還幹部借款：樂團還給林怡君', FinanceRecord.objects.get(type='expense', amount=5000).description)
        self.assertIn('日期無法辨識', out.getvalue())               # 沒填日期的列不匯入、列入報告
        self.assertNotIn('類型「', out.getvalue())                  # 統計欄沒被當成資料

        call_command('import_sheet', path, '--operator', 'sheet_officer', '--commit', stdout=io.StringIO())
        self.assertEqual(loans.count(), 3)

    def test_student_flag_and_student_amount_imported(self):
        """名冊勾「學生」→ 已有帳號者標為學生；團費期別「學生團費」→ FeePeriod.student_amount"""
        import openpyxl
        from django.core.management import call_command

        from apps.finance.models import FeePeriod

        path = self._workbook()
        wb = openpyxl.load_workbook(path)
        roster = wb['團員名冊']
        roster.cell(row=1, column=10, value='學生')
        roster.cell(row=2, column=10, value=True)       # 已有帳號
        periods = wb['團費期別']
        periods.cell(row=1, column=7, value='學生團費')
        periods.cell(row=2, column=7, value=1000)
        wb.save(path)
        out = io.StringIO()
        call_command('import_sheet', path, '--operator', 'sheet_officer', '--commit', stdout=out)
        self.member.refresh_from_db()
        self.assertTrue(self.member.is_student)
        self.assertIn('已將 1 人標為學生：已有帳號', out.getvalue())
        self.assertEqual(FeePeriod.objects.get().student_amount, 1000)

    def test_rerun_is_idempotent(self):
        """重跑不會產生重複資料，已存在的一律略過"""
        from apps.accounts.models import Registration
        from apps.events.models import LeaveRequest, Rehearsal, RehearsalAttendance
        from apps.finance.models import FinanceRecord, MembershipFee

        self._run('--commit')
        counts = [m.objects.count() for m in (Registration, Rehearsal, RehearsalAttendance,
                                              LeaveRequest, MembershipFee, FinanceRecord)]
        self._run('--commit')
        self.assertEqual(
            [m.objects.count() for m in (Registration, Rehearsal, RehearsalAttendance,
                                         LeaveRequest, MembershipFee, FinanceRecord)],
            counts,
        )

    def test_operator_must_be_officer(self):
        """--operator 必須是幹部，一般團員帳號直接拒絕"""
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with self.assertRaises(CommandError):
            call_command('import_sheet', self._workbook(), '--operator', 'sheet_member',
                         stdout=io.StringIO())

    def test_changed_headers_rejected(self):
        """欄位名稱被改過就整份拒絕，不猜著對位"""
        import openpyxl
        from django.core.management import call_command
        from django.core.management.base import CommandError

        path = self._workbook()
        wb = openpyxl.load_workbook(path)
        wb['團費收繳']['B1'] = '期數'
        wb.save(path)
        with self.assertRaises(CommandError):
            call_command('import_sheet', path, '--operator', 'sheet_officer', stdout=io.StringIO())
