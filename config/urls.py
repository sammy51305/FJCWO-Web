from pathlib import Path

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


# 公開頁用的圖（關於百韻的人物照片）放在 media/public/，不需登入。
# document_root 鎖在 public/ 子目錄：`media/public/../finance/x` 會被 safe_join 擋成 404，
# 不能拿這條路繞過上面的登入限制去讀收據。
def serve_public_media(request, path):
    return media_serve(request, path, document_root=Path(settings.MEDIA_ROOT) / 'public')


urlpatterns += [
    re_path(r'^media/public/(?P<path>.*)$', serve_public_media),
    re_path(r'^media/(?P<path>.*)$', serve_media),
]
