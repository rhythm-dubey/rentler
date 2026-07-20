from django.contrib import admin

from .models import Setting


@admin.register(Setting)
class SettingAdmin(admin.ModelAdmin):
    list_display = ('site', 'name', 'short_value', 'updated_at')
    list_filter = ('site',)
    search_fields = ('name', 'value')
    ordering = ('site', 'name')

    @admin.display(description='value')
    def short_value(self, obj: Setting) -> str:
        text = obj.value or ''
        if len(text) > 80:
            return f'{text[:80]}…'
        return text
