from django.urls import path

from . import views

app_name = 'scores'

urlpatterns = [
    path('', views.score_list, name='score_list'),
    path('<int:pk>/', views.score_detail, name='score_detail'),
]
