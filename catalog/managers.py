from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    def delete(self):
        return super().update(deleted_at=timezone.now())

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(deleted_at__isnull=True)

    def deleted(self):
        return self.exclude(deleted_at__isnull=True)

    def listed(self):
        """Public marketplace listings: active, approved, Stripe-ready owner."""
        return self.filter(
            is_active=True,
            is_admin_approved=True,
            owner__stripe_charges_enabled=True,
            owner__deleted_at__isnull=True,
            owner__is_active=True,
        )


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()

    def listed(self):
        return self.get_queryset().listed()


class AllObjectsManager(models.Manager):
    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)
