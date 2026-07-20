from django.urls import path

from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.browse, name='browse'),
    path('subcategories/', views.subcategories, name='subcategories'),
    path('manage/', views.manage_list, name='manage_list'),
    path('manage/new/', views.manage_create, name='manage_create'),
    path('manage/<slug:slug>/', views.manage_edit, name='manage_edit'),
    path('manage/<slug:slug>/delete/', views.manage_delete, name='manage_delete'),
    path('manage/<slug:slug>/variants/', views.manage_variants, name='manage_variants'),
    path(
        'manage/<slug:slug>/variants/<int:variant_id>/toggle/',
        views.manage_variant_toggle,
        name='manage_variant_toggle',
    ),
    path('<slug:slug>/', views.detail, name='detail'),
    path('<slug:slug>/terms/', views.terms, name='terms'),
]
