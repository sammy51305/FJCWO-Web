from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from .models import Announcement


class AnnouncementListTest(TestCase):
    """公告列表頁的可見性控制"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='ann_member', email='ann_member@test.local',
            password='testpass123', name='測試團員', role=User.Role.MEMBER,
        )
        self.officer = User.objects.create_user(
            username='ann_officer', email='ann_officer@test.local',
            password='testpass123', name='測試幹部', role=User.Role.OFFICER,
        )
        now = timezone.now()
        self.pub_public = Announcement.objects.create(
            title='公開公告', content='內容', visibility=Announcement.Visibility.PUBLIC,
            created_by=self.officer, published_at=now,
        )
        self.pub_member = Announcement.objects.create(
            title='團員公告', content='內容', visibility=Announcement.Visibility.MEMBER_ONLY,
            created_by=self.officer, published_at=now,
        )
        self.pub_officer = Announcement.objects.create(
            title='幹部公告', content='內容', visibility=Announcement.Visibility.OFFICER_ONLY,
            created_by=self.officer, published_at=now,
        )
        self.draft = Announcement.objects.create(
            title='草稿公告', content='內容', visibility=Announcement.Visibility.PUBLIC,
            created_by=self.officer,
        )
        self.url = reverse('announcements:announcement_list')

    def test_unauthenticated_sees_only_public(self):
        """未登入只看到公開公告"""
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '公開公告')
        self.assertNotContains(r, '團員公告')
        self.assertNotContains(r, '幹部公告')

    def test_unauthenticated_cannot_see_draft(self):
        """未登入看不到草稿"""
        r = self.client.get(self.url)
        self.assertNotContains(r, '草稿公告')

    def test_member_sees_public_and_member(self):
        """一般團員看到公開 + 團員限定"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertContains(r, '公開公告')
        self.assertContains(r, '團員公告')
        self.assertNotContains(r, '幹部公告')

    def test_member_cannot_see_draft(self):
        """一般團員看不到草稿"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertNotContains(r, '草稿公告')

    def test_officer_sees_all_published(self):
        """幹部看到全部已發布公告（含幹部限定）"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '公開公告')
        self.assertContains(r, '團員公告')
        self.assertContains(r, '幹部公告')

    def test_officer_cannot_see_draft_in_list(self):
        """幹部在列表頁看不到草稿（草稿只在管理頁）"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertNotContains(r, '草稿公告')


class AnnouncementDetailTest(TestCase):
    """公告詳情頁的存取控制"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='det_member', email='det_member@test.local',
            password='testpass123', name='測試團員', role=User.Role.MEMBER,
        )
        self.officer = User.objects.create_user(
            username='det_officer', email='det_officer@test.local',
            password='testpass123', name='測試幹部', role=User.Role.OFFICER,
        )
        now = timezone.now()
        self.public_ann = Announcement.objects.create(
            title='公開詳情', content='詳細內容', visibility=Announcement.Visibility.PUBLIC,
            created_by=self.officer, published_at=now,
        )
        self.officer_ann = Announcement.objects.create(
            title='幹部詳情', content='幹部內容', visibility=Announcement.Visibility.OFFICER_ONLY,
            created_by=self.officer, published_at=now,
        )
        self.draft_ann = Announcement.objects.create(
            title='草稿詳情', content='草稿內容', visibility=Announcement.Visibility.PUBLIC,
            created_by=self.officer,
        )

    def test_unauthenticated_can_view_public(self):
        """未登入可查看公開公告詳情"""
        r = self.client.get(reverse('announcements:announcement_detail', args=[self.public_ann.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, '詳細內容')

    def test_member_cannot_view_officer_only(self):
        """一般團員無法查看幹部限定公告詳情（404）"""
        self.client.force_login(self.member)
        r = self.client.get(reverse('announcements:announcement_detail', args=[self.officer_ann.pk]))
        self.assertEqual(r.status_code, 404)

    def test_officer_can_view_officer_only(self):
        """幹部可查看幹部限定公告詳情"""
        self.client.force_login(self.officer)
        r = self.client.get(reverse('announcements:announcement_detail', args=[self.officer_ann.pk]))
        self.assertEqual(r.status_code, 200)

    def test_draft_returns_404(self):
        """草稿對任何人都回 404"""
        self.client.force_login(self.officer)
        r = self.client.get(reverse('announcements:announcement_detail', args=[self.draft_ann.pk]))
        self.assertEqual(r.status_code, 404)


class AnnouncementManageTest(TestCase):
    """幹部公告管理頁"""

    def setUp(self):
        self.member = User.objects.create_user(
            username='mgr_member', email='mgr_member@test.local',
            password='testpass123', name='測試團員', role=User.Role.MEMBER,
        )
        self.officer = User.objects.create_user(
            username='mgr_officer', email='mgr_officer@test.local',
            password='testpass123', name='測試幹部', role=User.Role.OFFICER,
        )
        self.draft = Announcement.objects.create(
            title='草稿測試', content='內容', visibility=Announcement.Visibility.PUBLIC,
            created_by=self.officer,
        )
        self.url = reverse('announcements:announcement_manage')

    def test_unauthenticated_redirects(self):
        """未登入導向登入頁"""
        r = self.client.get(self.url)
        self.assertRedirects(r, f'/accounts/login/?next={self.url}', fetch_redirect_response=False)

    def test_member_redirects(self):
        """一般團員無權限，導向公告列表"""
        self.client.force_login(self.member)
        r = self.client.get(self.url)
        self.assertRedirects(r, reverse('announcements:announcement_list'), fetch_redirect_response=False)

    def test_officer_can_access(self):
        """幹部可進入管理頁"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 200)

    def test_manage_shows_draft(self):
        """管理頁顯示草稿"""
        self.client.force_login(self.officer)
        r = self.client.get(self.url)
        self.assertContains(r, '草稿測試')


class AnnouncementCreateTest(TestCase):
    """新增公告"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='cre_officer', email='cre_officer@test.local',
            password='testpass123', name='測試幹部', role=User.Role.OFFICER,
        )
        self.url = reverse('announcements:announcement_create')

    def test_officer_can_create(self):
        """幹部可新增公告，預設為草稿"""
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {
            'title': '新公告標題',
            'content': '公告內容',
            'visibility': Announcement.Visibility.MEMBER_ONLY,
        })
        self.assertRedirects(r, reverse('announcements:announcement_manage'), fetch_redirect_response=False)
        ann = Announcement.objects.get(title='新公告標題')
        self.assertIsNone(ann.published_at)
        self.assertEqual(ann.created_by, self.officer)

    def test_empty_title_is_rejected(self):
        """空標題應被擋回"""
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {
            'title': '',
            'content': '內容',
            'visibility': Announcement.Visibility.PUBLIC,
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Announcement.objects.exists())

    def test_empty_content_is_rejected(self):
        """空內容應被擋回"""
        self.client.force_login(self.officer)
        r = self.client.post(self.url, {
            'title': '標題',
            'content': '',
            'visibility': Announcement.Visibility.PUBLIC,
        })
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Announcement.objects.exists())


class AnnouncementEditTest(TestCase):
    """編輯公告"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='edt_officer', email='edt_officer@test.local',
            password='testpass123', name='測試幹部', role=User.Role.OFFICER,
        )
        self.ann = Announcement.objects.create(
            title='原標題', content='原內容', visibility=Announcement.Visibility.PUBLIC,
            created_by=self.officer,
        )
        self.url = reverse('announcements:announcement_edit', args=[self.ann.pk])

    def test_officer_can_edit(self):
        """幹部可編輯公告"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'title': '新標題',
            'content': '新內容',
            'visibility': Announcement.Visibility.MEMBER_ONLY,
        })
        self.ann.refresh_from_db()
        self.assertEqual(self.ann.title, '新標題')
        self.assertEqual(self.ann.visibility, Announcement.Visibility.MEMBER_ONLY)

    def test_invalid_edit_does_not_save(self):
        """空標題的編輯不儲存"""
        self.client.force_login(self.officer)
        self.client.post(self.url, {
            'title': '',
            'content': '新內容',
            'visibility': Announcement.Visibility.PUBLIC,
        })
        self.ann.refresh_from_db()
        self.assertEqual(self.ann.title, '原標題')


class AnnouncementPublishTest(TestCase):
    """發布 / 取消發布"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='pub_officer', email='pub_officer@test.local',
            password='testpass123', name='測試幹部', role=User.Role.OFFICER,
        )
        self.draft = Announcement.objects.create(
            title='草稿', content='內容', visibility=Announcement.Visibility.PUBLIC,
            created_by=self.officer,
        )
        self.published = Announcement.objects.create(
            title='已發布', content='內容', visibility=Announcement.Visibility.PUBLIC,
            created_by=self.officer, published_at=timezone.now(),
        )

    def test_publish_draft_sets_published_at(self):
        """發布草稿後 published_at 有值"""
        self.client.force_login(self.officer)
        self.client.post(reverse('announcements:announcement_publish', args=[self.draft.pk]))
        self.draft.refresh_from_db()
        self.assertIsNotNone(self.draft.published_at)

    def test_unpublish_clears_published_at(self):
        """取消發布後 published_at 為 None"""
        self.client.force_login(self.officer)
        self.client.post(reverse('announcements:announcement_publish', args=[self.published.pk]))
        self.published.refresh_from_db()
        self.assertIsNone(self.published.published_at)


class AnnouncementDeleteTest(TestCase):
    """刪除公告"""

    def setUp(self):
        self.officer = User.objects.create_user(
            username='del_officer', email='del_officer@test.local',
            password='testpass123', name='測試幹部', role=User.Role.OFFICER,
        )
        self.ann = Announcement.objects.create(
            title='待刪公告', content='內容', visibility=Announcement.Visibility.PUBLIC,
            created_by=self.officer,
        )

    def test_officer_can_delete(self):
        """幹部可刪除公告"""
        self.client.force_login(self.officer)
        self.client.post(reverse('announcements:announcement_delete', args=[self.ann.pk]))
        self.assertFalse(Announcement.objects.filter(pk=self.ann.pk).exists())

    def test_get_request_does_not_delete(self):
        """GET 請求不刪除"""
        self.client.force_login(self.officer)
        self.client.get(reverse('announcements:announcement_delete', args=[self.ann.pk]))
        self.assertTrue(Announcement.objects.filter(pk=self.ann.pk).exists())
