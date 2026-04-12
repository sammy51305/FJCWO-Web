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
]
