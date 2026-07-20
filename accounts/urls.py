from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.AccountLoginView.as_view(), name='login'),
    path('logout/', views.AccountLogoutView.as_view(), name='logout'),
    path('profile/', views.profile, name='profile'),
    path('password-reset/', views.AccountPasswordResetView.as_view(), name='password_reset'),
    path(
        'password-reset/done/',
        views.AccountPasswordResetDoneView.as_view(),
        name='password_reset_done',
    ),
    path(
        'password-reset/<uidb64>/<token>/',
        views.AccountPasswordResetConfirmView.as_view(),
        name='password_reset_confirm',
    ),
    path(
        'password-reset/complete/',
        views.AccountPasswordResetCompleteView.as_view(),
        name='password_reset_complete',
    ),
]
