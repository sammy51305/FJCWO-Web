from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
