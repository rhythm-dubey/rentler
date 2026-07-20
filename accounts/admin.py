from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.utils.translation import gettext_lazy as _

from .models import Permission, Role, RolePermission, User, UserRole


class UserRoleInline(admin.TabularInline):
    model = UserRole
    extra = 0


class RolePermissionInline(admin.TabularInline):
    model = RolePermission
    extra = 0


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ('email',)
    list_display = (
        'email',
        'name',
        'is_blocked',
        'is_staff',
        'is_active',
        'is_identity_verified',
    )
    list_filter = ('is_blocked', 'is_staff', 'is_active', 'is_identity_verified', 'roles')
    search_fields = ('email', 'name', 'phone', 'business_name')
    filter_horizontal = ()
    inlines = [UserRoleInline]

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (
            _('Personal info'),
            {
                'fields': (
                    'name',
                    'phone',
                    'country_code',
                    'gender',
                    'profile',
                    'address',
                    'state',
                    'city',
                    'post_code',
                )
            },
        ),
        (
            _('Owner'),
            {
                'fields': (
                    'business_name',
                    'abn',
                    'platform_fee',
                    'import_token',
                )
            },
        ),
        (
            _('Bank / Stripe'),
            {
                'fields': (
                    'bsb',
                    'account_number',
                    'bank_account_id',
                    'stripe_customer_id',
                    'stripe_connected_account_id',
                    'stripe_charges_enabled',
                )
            },
        ),
        (
            _('Verification'),
            {
                'fields': (
                    'id_proof',
                    'utility_bill',
                    'address_verification',
                    'scanned_profile',
                    'documents',
                    'is_identity_verified',
                    'email_verified_at',
                )
            },
        ),
        (
            _('Permissions'),
            {
                'fields': (
                    'is_active',
                    'is_blocked',
                    'is_staff',
                    'is_superuser',
                    'groups',
                    'user_permissions',
                )
            },
        ),
        (_('Important dates'), {'fields': ('last_login', 'date_joined', 'deleted_at')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('email', 'name', 'password1', 'password2', 'is_staff', 'is_superuser'),
            },
        ),
    )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('slug', 'name')
    search_fields = ('slug', 'name')
    inlines = [RolePermissionInline]
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('codename', 'name')
    search_fields = ('codename', 'name')
