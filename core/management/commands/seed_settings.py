from django.core.management.base import BaseCommand

from core.models import Setting

DEFAULT_SETTINGS = [
    (
        'website',
        'tnc',
        '<p>Welcome to Rentler. By using this website you agree to these terms and conditions.</p>',
    ),
    (
        'website',
        'rental_tnc',
        '<p>Standard rental terms apply to all bookings made through Rentler.</p>',
    ),
    ('website', 'support_email', 'support@rentler.example'),
    ('website', 'support_phone', ''),
    ('website', 'company_name', 'Rentler'),
    (
        'website',
        'owner_information',
        '<p>Information for owners listing items on Rentler.</p>',
    ),
]


class Command(BaseCommand):
    help = 'Seed default website settings (idempotent; does not overwrite existing values)'

    def handle(self, *args, **options):
        for site, name, value in DEFAULT_SETTINGS:
            setting, created = Setting.objects.get_or_create(
                site=site,
                name=name,
                defaults={'value': value},
            )
            action = 'Created' if created else 'Exists'
            self.stdout.write(f'{action} setting: {site}:{name}')

        self.stdout.write(self.style.SUCCESS('Website settings seeded.'))
