from django.contrib.auth import authenticate
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from accounts.decorators import permission_required_codename, role_required
from accounts.models import User


class AccountsModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command('seed_roles')

    def test_create_user_with_email_login(self):
        user = User.objects.create_user(
            email='renter@example.com',
            password='testpass123',
            name='Renter One',
        )
        auth_user = authenticate(username='renter@example.com', password='testpass123')
        self.assertEqual(auth_user, user)

    def test_assign_role_and_permissions(self):
        user = User.objects.create_user(
            email='owner@example.com',
            password='testpass123',
            name='Owner One',
        )
        user.assign_role('owner')
        user.refresh_from_db()

        self.assertTrue(user.has_role('owner'))
        self.assertTrue(user.has_permission('product.manage_own'))
        self.assertFalse(user.has_permission('product.approve'))
        self.assertTrue(user.import_token)

    def test_admin_role_sets_is_staff(self):
        user = User.objects.create_user(
            email='admin@example.com',
            password='testpass123',
            name='Admin One',
        )
        user.assign_role('admin')
        user.refresh_from_db()
        self.assertTrue(user.is_staff)

        user.remove_role('admin')
        user.refresh_from_db()
        self.assertFalse(user.is_staff)

    def test_soft_deleted_user_hidden_and_cannot_auth(self):
        user = User.objects.create_user(
            email='gone@example.com',
            password='testpass123',
            name='Gone',
        )
        user.delete()
        self.assertIsNone(User.objects.filter(email='gone@example.com').first())
        self.assertIsNotNone(User.all_objects.filter(email='gone@example.com').first())
        self.assertIsNone(authenticate(username='gone@example.com', password='testpass123'))


class AccountsAuthViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command('seed_roles')

    def setUp(self):
        self.client = Client()

    def test_register_assigns_role_and_owner_import_token(self):
        response = self.client.post(
            reverse('accounts:register'),
            {
                'email': 'newowner@example.com',
                'name': 'New Owner',
                'role': 'owner',
                'password1': 'ComplexPass123!',
                'password2': 'ComplexPass123!',
                'terms': True,
            },
        )
        self.assertEqual(response.status_code, 302)
        user = User.objects.get(email='newowner@example.com')
        self.assertTrue(user.has_role('owner'))
        self.assertTrue(user.import_token)

    def test_blocked_user_rejected_at_login(self):
        user = User.objects.create_user(
            email='blocked@example.com',
            password='testpass123',
            name='Blocked',
        )
        user.is_blocked = True
        user.save(update_fields=['is_blocked'])

        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'blocked@example.com', 'password': 'testpass123'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_soft_deleted_user_rejected_at_login(self):
        user = User.objects.create_user(
            email='deleted@example.com',
            password='testpass123',
            name='Deleted',
        )
        user.delete()

        response = self.client.post(
            reverse('accounts:login'),
            {'username': 'deleted@example.com', 'password': 'testpass123'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'no longer active')


class DecoratorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command

        call_command('seed_roles')

    def setUp(self):
        self.factory = RequestFactory()

    def test_role_required(self):
        @role_required('owner')
        def sample(request):
            return HttpResponse('ok')

        owner = User.objects.create_user(
            email='dec-owner@example.com',
            password='testpass123',
            name='Owner',
        )
        owner.assign_role('owner')
        request = self.factory.get('/')
        request.user = owner
        self.assertEqual(sample(request).status_code, 200)

        renter = User.objects.create_user(
            email='dec-renter@example.com',
            password='testpass123',
            name='Renter',
        )
        renter.assign_role('renter')
        request.user = renter
        with self.assertRaises(PermissionDenied):
            sample(request)

    def test_permission_required_codename(self):
        @permission_required_codename('product.approve')
        def sample(request):
            return HttpResponse('ok')

        admin = User.objects.create_user(
            email='dec-admin@example.com',
            password='testpass123',
            name='Admin',
        )
        admin.assign_role('admin')
        request = self.factory.get('/')
        request.user = admin
        self.assertEqual(sample(request).status_code, 200)
