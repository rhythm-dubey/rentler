from django.core.management.base import BaseCommand

from accounts.models import Permission, Role, RolePermission

PERMISSIONS = [
    ('impersonate', 'Impersonate users', 'Act as another user'),
    ('product.approve', 'Approve products', 'Approve products for listing'),
    ('product.feature', 'Feature products', 'Mark products as featured'),
    ('user.block', 'Block users', 'Block or unblock user accounts'),
    ('settings.manage', 'Manage settings', 'Edit site settings'),
    ('ticket.manage', 'Manage tickets', 'Administer support tickets'),
    ('product.manage_own', 'Manage own products', 'Create and edit own products'),
    ('order.manage_own', 'Manage own orders', 'Manage orders for own products'),
    ('ticket.create', 'Create tickets', 'Open support tickets'),
    ('withdrawal.request', 'Request withdrawal', 'Request owner withdrawals'),
    ('order.create', 'Create orders', 'Place rental orders'),
    ('profile.verify', 'Verify profile', 'Submit identity verification'),
]

ROLE_PERMISSIONS = {
    'admin': [
        'impersonate',
        'product.approve',
        'product.feature',
        'user.block',
        'settings.manage',
        'ticket.manage',
    ],
    'owner': [
        'product.manage_own',
        'order.manage_own',
        'ticket.create',
        'withdrawal.request',
    ],
    'renter': [
        'order.create',
        'ticket.create',
        'profile.verify',
    ],
}

ROLES = {
    'admin': ('Admin', 'Platform administrator'),
    'owner': ('Owner', 'Product owner / lessor'),
    'renter': ('Renter', 'Product renter / lessee'),
}


class Command(BaseCommand):
    help = 'Seed default roles and permissions (idempotent)'

    def handle(self, *args, **options):
        permission_map = {}
        for codename, name, description in PERMISSIONS:
            perm, created = Permission.objects.get_or_create(
                codename=codename,
                defaults={'name': name, 'description': description},
            )
            permission_map[codename] = perm
            action = 'Created' if created else 'Exists'
            self.stdout.write(f'{action} permission: {codename}')

        for slug, (name, description) in ROLES.items():
            role, created = Role.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'description': description},
            )
            action = 'Created' if created else 'Exists'
            self.stdout.write(f'{action} role: {slug}')

            for codename in ROLE_PERMISSIONS[slug]:
                RolePermission.objects.get_or_create(
                    role=role,
                    permission=permission_map[codename],
                )

        self.stdout.write(self.style.SUCCESS('Roles and permissions seeded.'))
