from django.urls import path

from . import views

app_name = 'scores'

urlpatterns = [
    path('', views.score_list, name='score_list'),
    path('create/', views.score_create, name='score_create'),
    path('<int:pk>/', views.score_detail, name='score_detail'),
    path('<int:pk>/edit/', views.score_edit, name='score_edit'),
    path('<int:pk>/delete/', views.score_delete, name='score_delete'),
    path('<int:pk>/parts/', views.score_parts_manage, name='score_parts_manage'),
    path('<int:pk>/download/', views.score_download, name='score_download'),
]
