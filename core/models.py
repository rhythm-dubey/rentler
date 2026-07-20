from django.db import models
from django.utils.html import mark_safe
from django.utils.safestring import SafeString


class Setting(models.Model):
    """Key-value site configuration (legacy Setting table)."""

    site = models.CharField(max_length=64, default='website', db_index=True)
    name = models.CharField(max_length=128, db_index=True)
    value = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ('site', 'name')
        constraints = [
            models.UniqueConstraint(fields=('site', 'name'), name='core_setting_site_name_uniq'),
        ]

    def __str__(self) -> str:
        return f'{self.site}:{self.name}'

    @classmethod
    def get_value(cls, name: str, default=None, site: str | None = None):
        qs = cls.objects.filter(name=name)
        if site is not None:
            qs = qs.filter(site=site)
        setting = qs.first()
        if setting is None or setting.value == '':
            return default
        return setting.value

    @classmethod
    def set_value(cls, name: str, value, site: str = 'website') -> 'Setting':
        setting, _ = cls.objects.update_or_create(
            site=site,
            name=name,
            defaults={'value': '' if value is None else str(value)},
        )
        return setting

    @classmethod
    def get_str(cls, name: str, default: str = '', site: str | None = None) -> str:
        value = cls.get_value(name, default=None, site=site)
        if value is None:
            return default
        return str(value)

    @classmethod
    def get_int(cls, name: str, default: int = 0, site: str | None = None) -> int:
        value = cls.get_value(name, default=None, site=site)
        if value is None:
            return default
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return default

    @classmethod
    def get_bool(cls, name: str, default: bool = False, site: str | None = None) -> bool:
        value = cls.get_value(name, default=None, site=site)
        if value is None:
            return default
        return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}

    @classmethod
    def get_html(cls, name: str, default: str = '', site: str | None = None) -> SafeString:
        value = cls.get_value(name, default=None, site=site)
        if value is None:
            return mark_safe(default)
        return mark_safe(str(value))
