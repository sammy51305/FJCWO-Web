from django.urls import path

from . import views

app_name = 'finance'

urlpatterns = [
    path('membership/', views.membership_fee_report, name='membership_fee_report'),
]
