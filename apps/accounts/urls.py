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
    path('register/', views.registration_apply, name='registration_apply'),
    path('register/status/', views.registration_status, name='registration_status'),
    path('register/review/', views.registration_review, name='registration_review'),
]
