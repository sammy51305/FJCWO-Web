from django.urls import path

from . import views

app_name = 'events'

urlpatterns = [
    path('', views.event_list, name='event_list'),
    path('<int:pk>/', views.event_detail, name='event_detail'),
    path('rehearsal/<int:pk>/', views.rehearsal_detail, name='rehearsal_detail'),
]
