from django.db import models
from django.utils import timezone


ACTIVE_STATUSES = (
    'new-order',
    'delivered',
    'request-cancellation',
    'request-return',
)

OCCUPYING_STATUSES = (
    'new-order',
    'delivered',
    'request-cancellation',
    'request-return',
)


class OrderQuerySet(models.QuerySet):
    def for_renter(self, user):
        return self.filter(user=user)

    def for_owner(self, user):
        return self.filter(product__owner=user)

    def active(self):
        return self.filter(order_status__in=ACTIVE_STATUSES)

    def due_back(self):
        return self.filter(
            order_status='delivered',
            end_date_time__lt=timezone.now(),
        )

    def occupying(self):
        return self.filter(order_status__in=OCCUPYING_STATUSES)


class OrderManager(models.Manager):
    def get_queryset(self):
        return OrderQuerySet(self.model, using=self._db)

    def for_renter(self, user):
        return self.get_queryset().for_renter(user)

    def for_owner(self, user):
        return self.get_queryset().for_owner(user)

    def active(self):
        return self.get_queryset().active()

    def due_back(self):
        return self.get_queryset().due_back()

    def occupying(self):
        return self.get_queryset().occupying()
