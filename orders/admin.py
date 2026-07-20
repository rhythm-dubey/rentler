from django.contrib import admin

from .models import Order


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id_label',
        'user_name',
        'product',
        'plan_type',
        'order_status',
        'total',
        'start_date_time',
        'end_date_time',
        'created_at',
    )
    list_filter = ('order_status', 'plan_type', 'delivery_by', 'make_payment')
    search_fields = ('id_label', 'user_name', 'user__email', 'product__name', 'product__slug')
    readonly_fields = (
        'id_label',
        'created_at',
        'updated_at',
        'subtotal',
        'shipping_charge',
        'amount',
        'processing_fee',
        'total',
        'delivered_at',
        'returned_at',
        'cancelled_at',
        'refunded_at',
    )
    raw_id_fields = ('user', 'product')
    date_hierarchy = 'created_at'
