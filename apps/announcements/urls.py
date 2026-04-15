from django.urls import path

from . import views

app_name = 'announcements'

urlpatterns = [
    path('', views.announcement_list, name='announcement_list'),
    path('<int:pk>/', views.announcement_detail, name='announcement_detail'),
    path('manage/', views.announcement_manage, name='announcement_manage'),
    path('create/', views.announcement_create, name='announcement_create'),
    path('<int:pk>/edit/', views.announcement_edit, name='announcement_edit'),
    path('<int:pk>/delete/', views.announcement_delete, name='announcement_delete'),
    path('<int:pk>/publish/', views.announcement_publish, name='announcement_publish'),
]
