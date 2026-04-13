from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    path('', views.event_list, name='event_list'),
    path('<int:pk>/', views.event_detail, name='event_detail'),
    path('rehearsal/<int:pk>/', views.rehearsal_detail, name='rehearsal_detail'),
    path('rehearsal/<int:rehearsal_pk>/leave/', views.leave_request_create, name='leave_request_create'),
    path('leave/mine/', views.my_leave_requests, name='my_leave_requests'),
    path('leave/review/', views.leave_review_list, name='leave_review_list'),
    path('rehearsal/<int:pk>/qr/', views.qr_manage, name='qr_manage'),
    path('rehearsal/<int:pk>/qr/generate/', views.qr_generate, name='qr_generate'),
    path('rehearsal/<int:pk>/qr/toggle/', views.qr_toggle, name='qr_toggle'),
    path('checkin/<uuid:token>/', views.qr_checkin, name='qr_checkin'),
    path('checkin/<uuid:token>/confirm/', views.qr_checkin_confirm, name='qr_checkin_confirm'),
    path('<int:pk>/setlist/', views.setlist_manage, name='setlist_manage'),
    path('<int:pk>/attendance/', views.attendance_report, name='attendance_report'),
    path('leave/stats/', views.leave_stats, name='leave_stats'),
]
