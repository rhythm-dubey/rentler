from decimal import Decimal

from django.core.management.base import BaseCommand
from django.core.management import call_command

from accounts.models import User
from catalog.models import Category, Product, ProductVariant


DEMO_PRODUCTS = [
    {
        'name': 'Pro Audio Headphones',
        'category_slug': 'electronics-audio',
        'fallback_category': 'electronics',
        'daily_price': Decimal('15.00'),
        'hourly_price': Decimal('5.00'),
        'city': 'San Francisco',
        'state': 'CA',
        'description': 'Premium studio headphones for recording and mixing.',
        'is_featured': True,
    },
    {
        'name': 'Carbon Fiber Mountain Bike',
        'category_slug': 'vehicles',
        'fallback_category': 'vehicles',
        'daily_price': Decimal('45.00'),
        'hourly_price': Decimal('12.00'),
        'city': 'Marin County',
        'state': 'CA',
        'description': 'Lightweight carbon mountain bike for weekend trails.',
        'is_featured': True,
    },
    {
        'name': 'Rotary Hammer Drill',
        'category_slug': 'tools_and_machinery-power-tools',
        'fallback_category': 'tools_and_machinery',
        'daily_price': Decimal('22.00'),
        'city': 'Oakland',
        'state': 'CA',
        'description': 'Heavy-duty rotary hammer for concrete and masonry.',
        'is_featured': True,
    },
]


class Command(BaseCommand):
    help = 'Seed a demo owner and featured products for local browse/home'

    def handle(self, *args, **options):
        call_command('seed_roles')
        call_command('seed_categories')

        owner, created = User.objects.get_or_create(
            email='demo-owner@rentler.example',
            defaults={
                'name': 'Demo Owner',
                'is_active': True,
                'stripe_charges_enabled': True,
                'stripe_connected_account_id': 'acct_demo',
            },
        )
        if created:
            owner.set_password('demo-password-change-me')
            owner.save()
            self.stdout.write('Created demo owner: demo-owner@rentler.example')
        owner.assign_role('owner')
        if not owner.stripe_charges_enabled:
            owner.stripe_charges_enabled = True
            owner.save(update_fields=['stripe_charges_enabled'])

        for data in DEMO_PRODUCTS:
            category = Category.objects.filter(slug=data['category_slug']).first()
            if not category:
                category = Category.objects.filter(slug=data['fallback_category']).first()
            if not category:
                self.stdout.write(self.style.WARNING(f"Skip {data['name']}: no category"))
                continue

            product, created = Product.objects.get_or_create(
                slug=data['name'].lower().replace(' ', '-'),
                defaults={
                    'owner': owner,
                    'category': category,
                    'name': data['name'],
                    'description': data['description'],
                    'daily_price': data['daily_price'],
                    'hourly_price': data.get('hourly_price', Decimal('0')),
                    'city': data['city'],
                    'state': data['state'],
                    'owner_pickup': True,
                    'is_active': True,
                    'is_featured': data.get('is_featured', False),
                    'is_admin_approved': True,
                    'available_on_days': [
                        'monday',
                        'tuesday',
                        'wednesday',
                        'thursday',
                        'friday',
                    ],
                    'total_items': 1,
                    'images': [],
                },
            )
            if created:
                ProductVariant.create_variants(product, count=1)
                # Keep approval/featured after create_variants path
                product.is_admin_approved = True
                product.is_featured = data.get('is_featured', False)
                product.is_active = True
                product.save(skip_approval_reset=True)
                self.stdout.write(f'Created product: {product.name}')
            else:
                self.stdout.write(f'Exists product: {product.name}')

        self.stdout.write(self.style.SUCCESS('Demo products seeded.'))
