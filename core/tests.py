from django.test import Client, TestCase
from django.urls import reverse


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
