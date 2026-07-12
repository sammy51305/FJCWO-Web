from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    path('', views.event_list, name='event_list'),
    path('create/', views.event_create, name='event_create'),
    path('<int:pk>/', views.event_detail, name='event_detail'),
    path('<int:pk>/edit/', views.event_edit, name='event_edit'),
    path('<int:pk>/delete/', views.event_delete, name='event_delete'),
    path('<int:event_pk>/rehearsal/create/', views.rehearsal_create, name='rehearsal_create'),
    path('rehearsal/<int:pk>/', views.rehearsal_detail, name='rehearsal_detail'),
    path('rehearsal/<int:pk>/edit/', views.rehearsal_edit, name='rehearsal_edit'),
    path('rehearsal/<int:rehearsal_pk>/leave/', views.leave_request_create, name='leave_request_create'),
    path('leave/mine/', views.my_leave_requests, name='my_leave_requests'),
    path('leave/review/', views.leave_review_list, name='leave_review_list'),
    path('leave/<int:pk>/delete/', views.leave_delete, name='leave_delete'),
    path('rehearsal/<int:pk>/qr/', views.qr_manage, name='qr_manage'),
    path('rehearsal/<int:pk>/qr/generate/', views.qr_generate, name='qr_generate'),
    path('rehearsal/<int:pk>/qr/toggle/', views.qr_toggle, name='qr_toggle'),
    path('checkin/<uuid:token>/', views.qr_checkin, name='qr_checkin'),
    path('checkin/<uuid:token>/confirm/', views.qr_checkin_confirm, name='qr_checkin_confirm'),
    path('<int:pk>/setlist/', views.setlist_manage, name='setlist_manage'),
    path('<int:pk>/attendance/', views.attendance_report, name='attendance_report'),
    path('leave/stats/', views.leave_stats, name='leave_stats'),
]
