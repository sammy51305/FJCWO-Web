from django.urls import path

from . import views

app_name = 'finance'

urlpatterns = [
    path('membership/', views.membership_fee_report, name='membership_fee_report'),
    path('membership/fee/edit/', views.fee_edit, name='fee_edit'),
    path('records/', views.finance_list, name='finance_list'),
    path('records/create/', views.finance_create, name='finance_create'),
    path('records/<int:pk>/edit/', views.finance_edit, name='finance_edit'),
    path('records/<int:pk>/delete/', views.finance_delete, name='finance_delete'),
    path('records/<int:pk>/receipt/', views.receipt_download, name='receipt_download'),
]
