from django.urls import path

from . import views

app_name = 'assets'

urlpatterns = [
    path('borrows/', views.borrow_status_report, name='borrow_status_report'),
]
