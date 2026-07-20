import uuid

from django.conf import settings
from django.db import models

from .managers import OrderManager


class Order(models.Model):
    class PlanType(models.TextChoices):
        HOURLY = 'hourly', 'Hourly'
        DAILY = 'daily', 'Daily'
        WEEKLY = 'weekly', 'Weekly'
        MONTHLY = 'monthly', 'Monthly'

    class MakePayment(models.TextChoices):
        ONE_TIME = 'one_time', 'One time'
        PER_PERIOD = 'per_period', 'Per period'

    class DeliveryBy(models.TextChoices):
        RENTER = 'renter', 'Renter pickup'
        OWNER = 'owner', 'Owner delivery'
        POSTAGE = 'postage', 'Postage'

    class Status(models.TextChoices):
        NEW_ORDER = 'new-order', 'New order'
        DELIVERED = 'delivered', 'Delivered'
        REQUEST_RETURN = 'request-return', 'Return requested'
        RETURNED = 'returned', 'Returned'
        REQUEST_CANCELLATION = 'request-cancellation', 'Cancellation requested'
        CANCELLED = 'cancelled', 'Cancelled'

    id_label = models.CharField(max_length=32, unique=True, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='orders',
    )
    product = models.ForeignKey(
        'catalog.Product',
        on_delete=models.PROTECT,
        related_name='orders',
    )

    user_name = models.CharField(max_length=150, blank=True)
    user_address = models.TextField(blank=True)

    product_variant_sku = models.JSONField(default=list, blank=True)
    description_while_renting = models.TextField(blank=True)
    description_while_return = models.TextField(blank=True)

    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    late_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    processing_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_due_date = models.DateField(null=True, blank=True)

    plan_type = models.CharField(max_length=20, choices=PlanType.choices)
    period = models.PositiveIntegerField(default=1)
    make_payment = models.CharField(
        max_length=20,
        choices=MakePayment.choices,
        default=MakePayment.PER_PERIOD,
    )
    quantity = models.PositiveIntegerField(default=1)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    pickup_address = models.TextField(blank=True)
    return_address = models.TextField(blank=True)
    start_date_time = models.DateTimeField()
    end_date_time = models.DateTimeField()

    delivery_by = models.CharField(
        max_length=20,
        choices=DeliveryBy.choices,
        default=DeliveryBy.RENTER,
    )
    delivery_address = models.TextField(blank=True)

    cancellation_reason = models.CharField(max_length=255, blank=True)
    cancellation_comment = models.TextField(blank=True)
    owner_cancellation_notes = models.TextField(blank=True)
    refund_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    order_status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.NEW_ORDER,
        db_index=True,
    )

    is_autopay_enabled = models.BooleanField(default=False)
    autopay_disabled_at = models.DateTimeField(null=True, blank=True)
    requested_bill_at = models.DateTimeField(null=True, blank=True)
    received_bill_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    last_autopaid_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = OrderManager()

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.id_label

    def save(self, *args, **kwargs):
        if not self.id_label:
            self.id_label = uuid.uuid4().hex[:16]
            while Order.objects.filter(id_label=self.id_label).exists():
                self.id_label = uuid.uuid4().hex[:16]
        super().save(*args, **kwargs)
