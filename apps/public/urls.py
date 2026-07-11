from django.urls import path

from . import views

app_name = 'public'

urlpatterns = [
    path('', views.index, name='index'),
    path('about/', views.about, name='about'),
    path('about/manage/', views.about_manage, name='about_manage'),
    path('about/create/', views.about_create, name='about_create'),
    path('about/<int:pk>/edit/', views.about_edit, name='about_edit'),
    path('about/<int:pk>/delete/', views.about_delete, name='about_delete'),
    path('rules/', views.rules, name='rules'),
    path('rules/edit/', views.rules_edit, name='rules_edit'),
    path('venues/', views.venue_list, name='venue_list'),
    path('venues/create/', views.venue_create, name='venue_create'),
    path('venues/<int:pk>/edit/', views.venue_edit, name='venue_edit'),
    path('venues/<int:pk>/delete/', views.venue_delete, name='venue_delete'),
    path('venues/timeslot/<int:pk>/delete/', views.venue_timeslot_delete, name='venue_timeslot_delete'),
]
