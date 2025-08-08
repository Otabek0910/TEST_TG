# roster/urls.py

from django.urls import path
from . import views

app_name = 'roster'

urlpatterns = [
    path('', views.roster_form, name='form'),
    path('update-role/', views.update_role_count, name='update_role'),
    path('save/', views.save_roster, name='save'),
    path('clear/', views.clear_roster, name='clear'),
]