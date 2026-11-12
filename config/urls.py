from django.conf import settings
from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.urls import include, path, re_path
from django.views.static import serve as media_serve

from apps.public import views as public_views

urlpatterns = [
    # 爬蟲只認網站根目錄的 /robots.txt，故掛在這裡而非 public 的 urls.py
    path('robots.txt', public_views.robots_txt, name='robots_txt'),
    path('admin/', admin.site.urls),
    path('accounts/', include('apps.accounts.urls')),
    path('events/', include('apps.events.urls')),
    path('scores/', include('apps.scores.urls')),
    path('assets/', include('apps.assets.urls')),
    path('finance/', include('apps.finance.urls')),
    path('announcements/', include('apps.announcements.urls')),
    path('', include('apps.public.urls')),
]

# 使用者上傳檔（收款 QR Code、收據掃描檔）：DEBUG=False 時 Django 不會自己提供 media，
# 圖會破掉；這裡由 Django 直接送檔，且限登入者才能讀（收據屬內部資料）。
# 本站流量小、單機部署，不另架 nginx 也夠用。
@login_required
def serve_media(request, path):
    # 每次請求才讀 MEDIA_ROOT（不在載入時固定），測試的暫存目錄才會生效
    return media_serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns += [re_path(r'^media/(?P<path>.*)$', serve_media)]
