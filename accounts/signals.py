import hashlib
import secrets
import time

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import User, UserRole


def _generate_import_token() -> str:
    raw = f'{secrets.token_hex(8)}{time.time()}{secrets.randbelow(10_000)}'
    return hashlib.md5(raw.encode()).hexdigest()


def _sync_staff_flag(user: User) -> None:
    if user.is_superuser:
        if not user.is_staff:
            user.is_staff = True
            user.save(update_fields=['is_staff'])
        return

    should_be_staff = user.roles.filter(slug='admin').exists()
    if user.is_staff != should_be_staff:
        user.is_staff = should_be_staff
        user.save(update_fields=['is_staff'])


def _on_owner_assigned(user: User) -> None:
    if user.roles.filter(slug='owner').exists() and not user.import_token:
        user.import_token = _generate_import_token()
        user.save(update_fields=['import_token'])


@receiver(post_save, sender=UserRole)
def user_role_saved(sender, instance: UserRole, **kwargs):
    user = instance.user
    if instance.role.slug == 'owner':
        _on_owner_assigned(user)
    if instance.role.slug == 'admin':
        _sync_staff_flag(user)


@receiver(post_delete, sender=UserRole)
def user_role_deleted(sender, instance: UserRole, **kwargs):
    _sync_staff_flag(instance.user)
