from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('about-us/', views.about, name='about'),
    path('privacy-policy/', views.privacy, name='privacy'),
    path('web-terms-and-conditions/', views.terms, name='terms'),
    path('account-deletion-guide/', views.account_deletion, name='account_deletion'),
]
