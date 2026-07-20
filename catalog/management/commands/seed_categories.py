from django.core.management.base import BaseCommand
from django.utils.text import slugify

from catalog.models import Category

# Legacy categoryMap() mains (excluding "all")
MAIN_CATEGORIES = [
    ('electronics', 'Electronics'),
    ('vehicles', 'Vehicles'),
    ('party_and_events', 'Party and Events'),
    ('tools_and_machinery', 'Tools and Machinery'),
    ('sporting_and_recreation', 'Sporting and Recreation'),
    ('health_and_mobility', 'Health and Mobility'),
    ('furniture', 'Furniture'),
    ('formal_and_costume', 'Formal and Costume'),
    ('accommodation', 'Accommodation'),
    ('musical_instruments', 'Musical Instruments'),
    ('experiences', 'Experiences'),
]

SAMPLE_SUBCATEGORIES = {
    'electronics': ['Cameras', 'Audio', 'Computers'],
    'vehicles': ['Cars', 'Vans', 'Scooters'],
    'tools_and_machinery': ['Power Tools', 'Hand Tools'],
    'furniture': ['Office', 'Home'],
}


class Command(BaseCommand):
    help = 'Seed legacy main categories and sample subcategories (idempotent)'

    def handle(self, *args, **options):
        for order, (slug, name) in enumerate(MAIN_CATEGORIES):
            category, created = Category.objects.get_or_create(
                slug=slug,
                defaults={
                    'name': name,
                    'parent': None,
                    'is_active': True,
                    'sort_order': order,
                },
            )
            action = 'Created' if created else 'Exists'
            self.stdout.write(f'{action} category: {slug}')

            for sub_order, sub_name in enumerate(SAMPLE_SUBCATEGORIES.get(slug, [])):
                sub_slug = f'{slug}-{slugify(sub_name)}'
                _, sub_created = Category.objects.get_or_create(
                    slug=sub_slug,
                    defaults={
                        'name': sub_name,
                        'parent': category,
                        'is_active': True,
                        'sort_order': sub_order,
                    },
                )
                if sub_created:
                    self.stdout.write(f'  Created subcategory: {sub_slug}')

        self.stdout.write(self.style.SUCCESS('Categories seeded.'))
