from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('password/change/', views.change_password_view, name='change_password'),
    path('directory/', views.member_directory, name='member_directory'),
    path('directory/report/', views.member_directory_report, name='member_directory_report'),
    path('directory/create/', views.member_create, name='member_create'),
    path('directory/<int:pk>/edit/', views.member_edit, name='member_edit'),
    path('directory/<int:pk>/deactivate/', views.member_deactivate, name='member_deactivate'),
    path('directory/<int:pk>/reactivate/', views.member_reactivate, name='member_reactivate'),
    path('directory/<int:pk>/delete/', views.member_delete, name='member_delete'),
    path('guests/', views.guest_list, name='guest_list'),
    path('guests/create/', views.guest_create, name='guest_create'),
    path('guests/<int:pk>/edit/', views.guest_edit, name='guest_edit'),
    path('guests/<int:pk>/promote/', views.guest_promote, name='guest_promote'),
    path('guests/<int:pk>/delete/', views.guest_delete, name='guest_delete'),
    path('register/', views.registration_apply, name='registration_apply'),
    path('register/status/', views.registration_status, name='registration_status'),
    path('register/review/', views.registration_review, name='registration_review'),
    path('register/create/', views.registration_create, name='registration_create'),
    path('register/<int:pk>/edit/', views.registration_edit, name='registration_edit'),
    path('register/<int:pk>/delete/', views.registration_delete, name='registration_delete'),
]
