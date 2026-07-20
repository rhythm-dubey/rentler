from decimal import Decimal

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User
from catalog.models import Category, Product, ProductVariant


class CatalogModelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_roles')
        cls.owner = User.objects.create_user(
            email='owner@example.com',
            password='pass12345',
            name='Owner',
            stripe_charges_enabled=True,
        )
        cls.owner.assign_role('owner')
        cls.category = Category.objects.create(
            name='Electronics',
            slug='electronics',
            is_active=True,
        )
        cls.sub = Category.objects.create(
            name='Cameras',
            slug='electronics-cameras',
            parent=cls.category,
            is_active=True,
        )

    def _make_product(self, **kwargs):
        defaults = {
            'owner': self.owner,
            'category': self.sub,
            'name': 'Test Camera',
            'daily_price': Decimal('25.00'),
            'hourly_price': Decimal('0'),
            'is_active': True,
            'is_admin_approved': True,
            'total_items': 2,
        }
        defaults.update(kwargs)
        product = Product(**defaults)
        product.save(skip_approval_reset=True)
        return product

    def test_category_tree_and_descendants(self):
        self.assertEqual(self.sub.get_root(), self.category)
        self.assertIn(self.sub.pk, self.category.get_descendant_ids())
        self.assertIn(self.category.pk, self.category.get_descendant_ids())

    def test_min_price_and_availability(self):
        product = self._make_product(
            hourly_price=Decimal('0'),
            daily_price=Decimal('10'),
            weekly_price=Decimal('50'),
            total_items=3,
            total_sold=1,
        )
        self.assertEqual(product.min_price, Decimal('10'))
        self.assertEqual(product.is_available, 2)

    def test_listed_requires_stripe_and_approval(self):
        product = self._make_product()
        self.assertEqual(Product.objects.listed().count(), 1)

        product.is_admin_approved = False
        product.save(skip_approval_reset=True)
        self.assertEqual(Product.objects.listed().count(), 0)

        product.is_admin_approved = True
        product.save(skip_approval_reset=True)
        self.owner.stripe_charges_enabled = False
        self.owner.save(update_fields=['stripe_charges_enabled'])
        self.assertEqual(Product.objects.listed().count(), 0)

    def test_soft_delete(self):
        product = self._make_product()
        product.delete()
        self.assertEqual(Product.objects.count(), 0)
        self.assertEqual(Product.all_objects.filter(deleted_at__isnull=False).count(), 1)

    def test_owner_edit_resets_approval(self):
        product = self._make_product()
        self.assertTrue(product.is_admin_approved)
        product.name = 'Updated Camera'
        product.save()
        product.refresh_from_db()
        self.assertFalse(product.is_admin_approved)

    def test_create_variants(self):
        product = self._make_product(total_items=3)
        variants = ProductVariant.create_variants(product, count=3)
        self.assertEqual(len(variants), 3)
        self.assertEqual(product.variants.count(), 3)
        self.assertTrue(all(v.sku for v in variants))


class CatalogViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_roles')
        call_command('seed_categories')
        cls.owner = User.objects.create_user(
            email='owner2@example.com',
            password='pass12345',
            name='Owner Two',
            stripe_charges_enabled=True,
        )
        cls.owner.assign_role('owner')
        cls.renter = User.objects.create_user(
            email='renter@example.com',
            password='pass12345',
            name='Renter',
        )
        cls.renter.assign_role('renter')
        cls.category = Category.objects.get(slug='electronics')
        cls.product = Product(
            owner=cls.owner,
            category=cls.category,
            name='Listed Lens',
            slug='listed-lens',
            daily_price=Decimal('18.00'),
            city='Sydney',
            state='NSW',
            is_active=True,
            is_admin_approved=True,
            is_featured=True,
        )
        cls.product.save(skip_approval_reset=True)
        cls.hidden = Product(
            owner=cls.owner,
            category=cls.category,
            name='Hidden Item',
            slug='hidden-item',
            daily_price=Decimal('9.00'),
            is_active=True,
            is_admin_approved=False,
        )
        cls.hidden.save(skip_approval_reset=True)

    def test_browse_lists_approved_products(self):
        response = Client().get(reverse('catalog:browse'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Listed Lens')
        self.assertNotContains(response, 'Hidden Item')

    def test_browse_filter_by_category(self):
        response = Client().get(reverse('catalog:browse'), {'category': 'electronics'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Listed Lens')

    def test_detail_and_terms(self):
        client = Client()
        detail = client.get(reverse('catalog:detail', args=['listed-lens']))
        self.assertEqual(detail.status_code, 200)
        self.assertContains(detail, 'Listed Lens')

        terms = client.get(reverse('catalog:terms', args=['listed-lens']))
        self.assertEqual(terms.status_code, 200)

        missing = client.get(reverse('catalog:detail', args=['hidden-item']))
        self.assertEqual(missing.status_code, 404)

    def test_subcategories_json(self):
        response = Client().get(
            reverse('catalog:subcategories'),
            {'parent': 'electronics'},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('subcategories', data)
        self.assertTrue(any(s['slug'].startswith('electronics-') for s in data['subcategories']))

    def test_owner_manage_requires_permission(self):
        client = Client()
        url = reverse('catalog:manage_list')
        self.assertEqual(client.get(url).status_code, 302)

        client.login(email='renter@example.com', password='pass12345')
        self.assertEqual(client.get(url).status_code, 403)

        client.logout()
        client.login(email='owner2@example.com', password='pass12345')
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Listed Lens')

    def test_owner_can_create_product(self):
        client = Client()
        client.login(email='owner2@example.com', password='pass12345')
        response = client.post(
            reverse('catalog:manage_create'),
            {
                'category': self.category.pk,
                'name': 'Brand New Drill',
                'description': 'A drill',
                'make_payment': 'per_period',
                'hourly_price': '0',
                'daily_price': '20',
                'weekly_price': '0',
                'monthly_price': '0',
                'has_multiple_items': False,
                'total_items': 2,
                'which_tnc': 'default',
                'is_active': True,
                'owner_pickup': True,
            },
        )
        self.assertEqual(response.status_code, 302)
        product = Product.objects.get(name='Brand New Drill')
        self.assertEqual(product.owner, self.owner)
        self.assertFalse(product.is_admin_approved)
        self.assertEqual(product.variants.count(), 2)

    def test_home_shows_featured_product(self):
        response = Client().get(reverse('core:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Listed Lens')
        self.assertContains(response, reverse('catalog:browse'))
