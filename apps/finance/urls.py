from django.urls import path

from . import views

app_name = 'finance'

urlpatterns = [
    path('membership/', views.membership_fee_report, name='membership_fee_report'),
    path('membership/fee/edit/', views.fee_edit, name='fee_edit'),
    path('membership/periods/', views.fee_period_list, name='fee_period_list'),
    path('membership/periods/create/', views.fee_period_create, name='fee_period_create'),
    path('membership/periods/<int:pk>/edit/', views.fee_period_edit, name='fee_period_edit'),
    path('membership/periods/<int:pk>/delete/', views.fee_period_delete, name='fee_period_delete'),
    path('membership/mine/', views.my_fees, name='my_fees'),
    path('membership/report/<int:period_pk>/', views.fee_report_create, name='fee_report_create'),
    path('membership/report/<int:pk>/withdraw/', views.fee_report_withdraw, name='fee_report_withdraw'),
    path('membership/review/', views.fee_review_list, name='fee_review_list'),
    path('membership/fee/<int:pk>/delete/', views.fee_delete, name='fee_delete'),
    path('annual/', views.annual_report, name='annual_report'),
    path('membership/payment-config/', views.payment_config_edit, name='payment_config_edit'),
    path('records/', views.finance_list, name='finance_list'),
    path('records/create/', views.finance_create, name='finance_create'),
    path('records/<int:pk>/edit/', views.finance_edit, name='finance_edit'),
    path('records/<int:pk>/delete/', views.finance_delete, name='finance_delete'),
    path('records/<int:pk>/receipt/', views.receipt_download, name='receipt_download'),
]
