from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('password/change/', views.change_password_view, name='change_password'),
    path('directory/', views.member_directory, name='member_directory'),
    path('directory/create/', views.member_create, name='member_create'),
    path('directory/<int:pk>/edit/', views.member_edit, name='member_edit'),
    path('directory/<int:pk>/deactivate/', views.member_deactivate, name='member_deactivate'),
    path('directory/<int:pk>/reactivate/', views.member_reactivate, name='member_reactivate'),
    path('directory/<int:pk>/delete/', views.member_delete, name='member_delete'),
    path('register/', views.registration_apply, name='registration_apply'),
    path('register/status/', views.registration_status, name='registration_status'),
    path('register/review/', views.registration_review, name='registration_review'),
    path('register/create/', views.registration_create, name='registration_create'),
    path('register/<int:pk>/edit/', views.registration_edit, name='registration_edit'),
    path('register/<int:pk>/delete/', views.registration_delete, name='registration_delete'),
]
