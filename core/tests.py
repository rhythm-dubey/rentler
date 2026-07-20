from django.test import Client, TestCase
from django.urls import reverse

from core.models import Setting


class CoreHomeTests(TestCase):
    def test_home_renders(self):
        response = Client().get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Rentler')
        self.assertContains(response, 'Rent Anything')

    def test_login_page_renders_stitch_layout(self):
        response = Client().get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Authenticate Access')

    def test_register_page_renders_stitch_layout(self):
        response = Client().get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Create Account')
        self.assertContains(response, 'I am a')


class SettingModelTests(TestCase):
    def test_get_and_set_value(self):
        Setting.set_value('company_name', 'Rentler Co')
        self.assertEqual(Setting.get_value('company_name'), 'Rentler Co')
        self.assertEqual(Setting.get_str('company_name'), 'Rentler Co')

    def test_typed_accessors(self):
        Setting.set_value('platform_fee', '12', site='stripe')
        Setting.set_value('stripe_status', 'true', site='stripe')
        Setting.set_value('tnc', '<p>Hello terms</p>')

        self.assertEqual(Setting.get_int('platform_fee', site='stripe'), 12)
        self.assertTrue(Setting.get_bool('stripe_status', site='stripe'))
        self.assertIn('Hello terms', Setting.get_html('tnc'))

    def test_defaults_when_missing(self):
        self.assertIsNone(Setting.get_value('missing_key'))
        self.assertEqual(Setting.get_str('missing_key', default='fallback'), 'fallback')
        self.assertEqual(Setting.get_int('missing_key', default=7), 7)
        self.assertFalse(Setting.get_bool('missing_key'))


class CoreStaticPageTests(TestCase):
    def test_about_privacy_and_deletion_pages(self):
        client = Client()
        for name in ('core:about', 'core:privacy', 'core:account_deletion'):
            response = client.get(reverse(name))
            self.assertEqual(response.status_code, 200, msg=name)

    def test_terms_page_shows_seeded_tnc(self):
        Setting.set_value('tnc', '<p>Unique seeded TNC content</p>')
        response = Client().get(reverse('core:terms'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Unique seeded TNC content')

    def test_nav_and_footer_links_on_about(self):
        response = Client().get(reverse('core:about'))
        self.assertContains(response, reverse('core:privacy'))
        self.assertContains(response, reverse('core:terms'))
        self.assertContains(response, reverse('core:account_deletion'))
