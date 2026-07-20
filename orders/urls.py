from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('shipping/process/', views.shipping_process, name='shipping_process'),
    path('shipping/', views.shipping, name='shipping'),
    path('checkout/process/', views.checkout_process, name='checkout_process'),
    path('checkout/', views.checkout, name='checkout'),
    path('create/', views.order_create, name='create'),
    path('success/<str:id_label>/', views.order_success, name='success'),
    path('', views.renter_list, name='renter_list'),
    path('detail/<str:id_label>/', views.renter_detail, name='renter_detail'),
    path('manage-status/', views.manage_status, name='manage_status'),
    path('manage/', views.owner_list, name='owner_list'),
    path('manage/<str:id_label>/', views.owner_detail, name='owner_detail'),
    path('manage/<str:id_label>/deliver/', views.owner_deliver, name='owner_deliver'),
    path('manage/<str:id_label>/return/', views.owner_return, name='owner_return'),
    path(
        'manage/<str:id_label>/accept-cancel/',
        views.owner_accept_cancel,
        name='owner_accept_cancel',
    ),
]
