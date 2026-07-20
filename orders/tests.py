from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from catalog.models import Category, Product, ProductVariant
from orders.availability import assert_slot_available, occupied_days, occupied_hours
from orders.models import Order
from orders.pricing import compute_pricing
from orders.services import (
    TransitionError,
    accept_cancellation,
    create_order_from_checkout,
    mark_delivered,
    mark_returned,
    request_cancellation,
    request_return,
)


class OrdersBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_roles')
        cls.owner = User.objects.create_user(
            email='owner-orders@example.com',
            password='pass12345',
            name='Owner',
            stripe_charges_enabled=True,
            address='1 Owner St',
            city='Sydney',
            state='NSW',
            post_code='2000',
        )
        cls.owner.assign_role('owner')
        cls.renter = User.objects.create_user(
            email='renter-orders@example.com',
            password='pass12345',
            name='Renter',
            address='2 Renter Ave',
            city='Sydney',
            state='NSW',
            post_code='2001',
        )
        cls.renter.assign_role('renter')
        cls.category = Category.objects.create(
            name='Electronics',
            slug='electronics-orders',
            is_active=True,
        )

    def _make_product(self, **kwargs):
        defaults = {
            'owner': self.owner,
            'category': self.category,
            'name': 'Test Camera',
            'hourly_price': Decimal('10.00'),
            'daily_price': Decimal('40.00'),
            'weekly_price': Decimal('150.00'),
            'monthly_price': Decimal('400.00'),
            'make_payment': Product.MakePayment.PER_PERIOD,
            'is_active': True,
            'is_admin_approved': True,
            'total_items': 2,
            'owner_pickup': True,
            'owner_delivery_pickup': True,
            'owner_delivery_pickup_cost': '15',
            'owner_postage': True,
            'owner_postage_cost': '10',
        }
        defaults.update(kwargs)
        product = Product(**defaults)
        product.save(skip_approval_reset=True)
        return product

    def _checkout_payload(self, product, **overrides):
        start = timezone.make_aware(datetime.combine(date.today() + timedelta(days=2), time(9, 0)))
        end = timezone.make_aware(datetime.combine(date.today() + timedelta(days=2), time(17, 59, 59)))
        data = {
            'product_id': product.pk,
            'plan_type': Order.PlanType.HOURLY,
            'start_date_time': start.isoformat(),
            'end_date_time': end.isoformat(),
            'period': 9,
            'quantity': 1,
            'delivery_by': Order.DeliveryBy.RENTER,
            'delivery_address': '',
        }
        data.update(overrides)
        return data


class PricingTests(OrdersBaseTestCase):
    def test_hourly_subtotal(self):
        product = self._make_product()
        pricing = compute_pricing(
            product,
            plan_type='hourly',
            period=3,
            quantity=2,
            delivery_by='renter',
        )
        self.assertEqual(pricing['subtotal'], Decimal('60.00'))
        self.assertEqual(pricing['shipping_charge'], Decimal('0.00'))
        self.assertEqual(pricing['total'], Decimal('60.00'))

    def test_weekly_per_period_first_period_only(self):
        product = self._make_product(make_payment=Product.MakePayment.PER_PERIOD)
        pricing = compute_pricing(
            product,
            plan_type='weekly',
            period=4,
            quantity=1,
            delivery_by='postage',
        )
        self.assertEqual(pricing['subtotal'], Decimal('150.00'))
        self.assertEqual(pricing['shipping_charge'], Decimal('10.00'))
        self.assertEqual(pricing['total'], Decimal('160.00'))

    def test_weekly_one_time_multiplies_period(self):
        product = self._make_product(make_payment=Product.MakePayment.ONE_TIME)
        pricing = compute_pricing(
            product,
            plan_type='weekly',
            period=3,
            quantity=1,
            delivery_by='owner',
        )
        self.assertEqual(pricing['subtotal'], Decimal('450.00'))
        self.assertEqual(pricing['shipping_charge'], Decimal('15.00'))


class OrderLifecycleTests(OrdersBaseTestCase):
    def test_create_order_and_transitions(self):
        product = self._make_product()
        variants = ProductVariant.create_variants(product, count=2)
        order = create_order_from_checkout(
            self.renter,
            self._checkout_payload(product),
        )
        product.refresh_from_db()
        self.assertEqual(order.order_status, Order.Status.NEW_ORDER)
        self.assertEqual(product.total_sold, 1)
        self.assertTrue(order.id_label)

        request_cancellation(order, reason='changed plans')
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.Status.REQUEST_CANCELLATION)

        accept_cancellation(order, notes='ok', refund_amount=Decimal('10'))
        order.refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(order.order_status, Order.Status.CANCELLED)
        self.assertEqual(product.total_sold, 0)
        self.assertEqual(order.refund_amount, Decimal('10'))

        # Fresh order for deliver/return
        order2 = create_order_from_checkout(
            self.renter,
            self._checkout_payload(
                product,
                start_date_time=(
                    timezone.make_aware(
                        datetime.combine(date.today() + timedelta(days=5), time(9, 0))
                    ).isoformat()
                ),
                end_date_time=(
                    timezone.make_aware(
                        datetime.combine(date.today() + timedelta(days=5), time(12, 59, 59))
                    ).isoformat()
                ),
            ),
        )
        mark_delivered(order2, [variants[0].sku])
        order2.refresh_from_db()
        variants[0].refresh_from_db()
        self.assertEqual(order2.order_status, Order.Status.DELIVERED)
        self.assertTrue(variants[0].is_sold)

        request_return(order2)
        mark_returned(order2)
        order2.refresh_from_db()
        variants[0].refresh_from_db()
        product.refresh_from_db()
        self.assertEqual(order2.order_status, Order.Status.RETURNED)
        self.assertFalse(variants[0].is_sold)
        self.assertEqual(product.total_sold, 0)

    def test_invalid_transition(self):
        product = self._make_product()
        order = create_order_from_checkout(
            self.renter,
            self._checkout_payload(product),
        )
        with self.assertRaises(TransitionError):
            request_return(order)

    def test_occupancy_blocks_overlap(self):
        product = self._make_product(total_items=1)
        create_order_from_checkout(self.renter, self._checkout_payload(product))
        with self.assertRaises(ValueError):
            create_order_from_checkout(self.renter, self._checkout_payload(product))

    def test_occupied_hours_and_days(self):
        product = self._make_product(total_items=1)
        day = date.today() + timedelta(days=3)
        start = timezone.make_aware(datetime.combine(day, time(10, 0)))
        end = timezone.make_aware(datetime.combine(day, time(14, 59, 59)))
        create_order_from_checkout(
            self.renter,
            self._checkout_payload(
                product,
                start_date_time=start.isoformat(),
                end_date_time=end.isoformat(),
                period=5,
            ),
        )
        hours = occupied_hours(product, day)
        self.assertIn(10, hours)
        self.assertIn(14, hours)
        days = occupied_days(product, day.year, day.month)
        self.assertIn(day.isoformat(), days)

        with self.assertRaises(ValueError):
            assert_slot_available(product, start, end, quantity=1)


class OrderViewTests(OrdersBaseTestCase):
    def setUp(self):
        self.client = Client()
        self.product = self._make_product()
        ProductVariant.create_variants(self.product, count=2)

    def test_renter_checkout_flow(self):
        self.client.login(email='renter-orders@example.com', password='pass12345')
        selected = (date.today() + timedelta(days=7)).isoformat()
        response = self.client.post(
            reverse('orders:shipping_process'),
            {
                'product_slug': self.product.slug,
                'plan_type': 'daily',
                'selected_date': selected,
                'start_duration': date.today().day if False else int(selected.split('-')[2]),
                'end_duration': int(selected.split('-')[2]),
                'period': 1,
                'quantity': 1,
                'delivery_by': 'renter',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('orders:shipping'))

        response = self.client.post(
            reverse('orders:checkout_process'),
            {
                'delivery_by': 'renter',
                'quantity': 1,
                'delivery_address': '',
                'city': '',
                'state': '',
                'post_code': '',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('orders:checkout'))

        response = self.client.post(reverse('orders:create'))
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(user=self.renter)
        self.assertIn(order.id_label, response.url)
        self.assertEqual(order.order_status, Order.Status.NEW_ORDER)

    def test_owner_manage_requires_permission(self):
        self.client.login(email='renter-orders@example.com', password='pass12345')
        response = self.client.get(reverse('orders:owner_list'))
        self.assertEqual(response.status_code, 403)

    def test_owner_deliver(self):
        order = create_order_from_checkout(
            self.renter,
            self._checkout_payload(self.product),
        )
        variant = self.product.variants.filter(is_sold=False).first()
        self.client.login(email='owner-orders@example.com', password='pass12345')
        response = self.client.post(
            reverse('orders:owner_deliver', kwargs={'id_label': order.id_label}),
            {'variant_skus': [variant.sku]},
        )
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.order_status, Order.Status.DELIVERED)

    def test_product_detail_shows_booking_form(self):
        self.client.login(email='renter-orders@example.com', password='pass12345')
        response = self.client.get(
            reverse('catalog:detail', kwargs={'slug': self.product.slug})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Book this rental')
        self.assertContains(response, 'orders:shipping_process'.split(':')[0])
        self.assertContains(response, reverse('orders:shipping_process'))
