from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from catalog.models import Product, ProductVariant

from .availability import assert_slot_available
from .models import Order
from .pricing import compute_pricing


class TransitionError(Exception):
    """Raised when an order status transition is not allowed."""


TRANSITIONS = {
    Order.Status.NEW_ORDER: {
        Order.Status.REQUEST_CANCELLATION,
        Order.Status.DELIVERED,
    },
    Order.Status.REQUEST_CANCELLATION: {
        Order.Status.NEW_ORDER,
        Order.Status.CANCELLED,
    },
    Order.Status.DELIVERED: {
        Order.Status.REQUEST_RETURN,
    },
    Order.Status.REQUEST_RETURN: {
        Order.Status.DELIVERED,
        Order.Status.RETURNED,
    },
}


def _ensure_transition(order: Order, new_status: str) -> None:
    allowed = TRANSITIONS.get(order.order_status, set())
    if new_status not in allowed:
        raise TransitionError(
            f'Cannot move order from {order.order_status} to {new_status}.'
        )


def _user_address_snapshot(user) -> str:
    parts = [user.address, user.city, user.state, user.post_code]
    return ', '.join(p for p in parts if p)


def build_rental_window(
    product: Product,
    *,
    plan_type: str,
    selected_date,
    start_duration: int | None = None,
    end_duration: int | None = None,
    period: int = 1,
) -> tuple[datetime, datetime, int]:
    """Build start/end datetimes and period count from booking form fields."""
    if isinstance(selected_date, str):
        selected_date = datetime.strptime(selected_date, '%Y-%m-%d').date()

    tz = timezone.get_current_timezone()
    period = max(1, int(period or 1))

    if plan_type == Order.PlanType.HOURLY:
        start_h = int(start_duration)
        end_h = int(end_duration)
        if end_h < start_h:
            raise ValueError('End hour must be after start hour.')
        start_dt = timezone.make_aware(
            datetime.combine(selected_date, time(start_h, 0, 0)),
            tz,
        )
        end_dt = timezone.make_aware(
            datetime.combine(selected_date, time(end_h, 59, 59)),
            tz,
        )
        return start_dt, end_dt, end_h - start_h + 1

    if plan_type == Order.PlanType.DAILY:
        start_day = int(start_duration)
        end_day = int(end_duration)
        if end_day < start_day:
            raise ValueError('End day must be on or after start day.')
        start_dt = timezone.make_aware(
            datetime.combine(
                selected_date.replace(day=start_day),
                time(0, 0, 0),
            ),
            tz,
        )
        end_dt = timezone.make_aware(
            datetime.combine(
                selected_date.replace(day=end_day),
                time(23, 59, 59),
            ),
            tz,
        )
        return start_dt, end_dt, end_day - start_day + 1

    if plan_type == Order.PlanType.WEEKLY:
        start_day = int(start_duration or selected_date.day)
        start_dt = timezone.make_aware(
            datetime.combine(
                selected_date.replace(day=start_day),
                time(0, 0, 0),
            ),
            tz,
        )
        end_date = (start_dt + timedelta(weeks=period)).date()
        end_dt = timezone.make_aware(
            datetime.combine(end_date, time(23, 59, 59)),
            tz,
        )
        return start_dt, end_dt, period

    if plan_type == Order.PlanType.MONTHLY:
        start_day = int(start_duration or selected_date.day)
        start_dt = timezone.make_aware(
            datetime.combine(
                selected_date.replace(day=start_day),
                time(0, 0, 0),
            ),
            tz,
        )
        # Approximate +N months then subtract 1 second via end-of-day prior day
        month = start_dt.month - 1 + period
        year = start_dt.year + month // 12
        month = month % 12 + 1
        day = min(start_dt.day, 28)
        end_anchor = start_dt.replace(year=year, month=month, day=day)
        end_dt = end_anchor - timedelta(seconds=1)
        return start_dt, end_dt, period

    raise ValueError(f'Unsupported plan type: {plan_type}')


@transaction.atomic
def create_order_from_checkout(user, checkout_data: dict) -> Order:
    """
    Create an Order from validated checkout session data.
    Recomputes pricing server-side. Stripe charging is Step 5.
    """
    product = (
        Product.objects.select_for_update()
        .select_related('owner')
        .get(pk=checkout_data['product_id'])
    )
    if not Product.objects.listed().filter(pk=product.pk).exists():
        raise ValueError('This product is not available for booking.')

    plan_type = checkout_data['plan_type']
    quantity = int(checkout_data.get('quantity') or 1)
    delivery_by = checkout_data['delivery_by']
    start_dt = checkout_data['start_date_time']
    end_dt = checkout_data['end_date_time']
    if isinstance(start_dt, str):
        start_dt = datetime.fromisoformat(start_dt)
        if timezone.is_naive(start_dt):
            start_dt = timezone.make_aware(start_dt)
    if isinstance(end_dt, str):
        end_dt = datetime.fromisoformat(end_dt)
        if timezone.is_naive(end_dt):
            end_dt = timezone.make_aware(end_dt)

    period = int(checkout_data.get('period') or 1)
    pricing = compute_pricing(
        product,
        plan_type=plan_type,
        period=period,
        quantity=quantity,
        delivery_by=delivery_by,
    )
    assert_slot_available(product, start_dt, end_dt, quantity)

    available = max(0, (product.total_items or 0) - (product.total_sold or 0))
    if quantity > available:
        raise ValueError('Not enough units available for this booking.')

    delivery_address = checkout_data.get('delivery_address') or ''
    if delivery_by != Order.DeliveryBy.RENTER and not delivery_address.strip():
        raise ValueError('Delivery address is required.')

    order = Order(
        user=user,
        product=product,
        user_name=user.name or user.email,
        user_address=_user_address_snapshot(user),
        plan_type=plan_type,
        period=pricing['period'],
        make_payment=product.make_payment,
        quantity=pricing['quantity'],
        subtotal=pricing['subtotal'],
        shipping_charge=pricing['shipping_charge'],
        amount=pricing['amount'],
        processing_fee=pricing['processing_fee'],
        total=pricing['total'],
        start_date_time=start_dt,
        end_date_time=end_dt,
        delivery_by=delivery_by,
        delivery_address=delivery_address,
        order_status=Order.Status.NEW_ORDER,
    )
    order.save()

    product.total_sold = (product.total_sold or 0) + quantity
    product.save(update_fields=['total_sold', 'updated_at'], skip_approval_reset=True)

    return order


def request_cancellation(order: Order, *, reason: str = '', comment: str = '') -> Order:
    _ensure_transition(order, Order.Status.REQUEST_CANCELLATION)
    order.order_status = Order.Status.REQUEST_CANCELLATION
    order.cancellation_reason = reason
    order.cancellation_comment = comment
    order.is_autopay_enabled = False
    order.autopay_disabled_at = timezone.now()
    order.save()
    return order


def revert_cancellation(order: Order) -> Order:
    _ensure_transition(order, Order.Status.NEW_ORDER)
    order.order_status = Order.Status.NEW_ORDER
    order.cancellation_reason = ''
    order.cancellation_comment = ''
    order.save()
    return order


@transaction.atomic
def accept_cancellation(
    order: Order,
    *,
    notes: str = '',
    refund_amount: Decimal | None = None,
) -> Order:
    _ensure_transition(order, Order.Status.CANCELLED)
    product = Product.objects.select_for_update().get(pk=order.product_id)
    product.total_sold = max(0, (product.total_sold or 0) - order.quantity)
    product.save(update_fields=['total_sold', 'updated_at'], skip_approval_reset=True)

    order.order_status = Order.Status.CANCELLED
    order.owner_cancellation_notes = notes
    order.cancelled_at = timezone.now()
    if refund_amount is not None:
        order.refund_amount = refund_amount
        order.refunded_at = timezone.now()
    order.save()
    return order


@transaction.atomic
def mark_delivered(order: Order, variant_skus: list[str] | None = None) -> Order:
    _ensure_transition(order, Order.Status.DELIVERED)
    variant_skus = list(variant_skus or [])
    variant_count = ProductVariant.objects.filter(product_id=order.product_id).count()

    if variant_count:
        if len(variant_skus) != order.quantity:
            raise ValueError(
                f'Select exactly {order.quantity} variant(s) for this order.'
            )
        variants = list(
            ProductVariant.objects.select_for_update().filter(
                product_id=order.product_id,
                sku__in=variant_skus,
                is_sold=False,
            )
        )
        if len(variants) != len(set(variant_skus)):
            raise ValueError('One or more selected variants are unavailable.')
        for variant in variants:
            variant.is_sold = True
            variant.save(update_fields=['is_sold', 'updated_at'])
        order.product_variant_sku = list(variant_skus)
    else:
        order.product_variant_sku = []

    order.order_status = Order.Status.DELIVERED
    order.delivered_at = timezone.now()

    if (
        order.plan_type in (Order.PlanType.WEEKLY, Order.PlanType.MONTHLY)
        and order.make_payment == Order.MakePayment.PER_PERIOD
    ):
        order.is_autopay_enabled = True
        order.last_autopaid_at = timezone.now()

    order.save()
    return order


def request_return(order: Order) -> Order:
    _ensure_transition(order, Order.Status.REQUEST_RETURN)
    order.order_status = Order.Status.REQUEST_RETURN
    order.save(update_fields=['order_status', 'updated_at'])
    return order


def revert_return(order: Order) -> Order:
    _ensure_transition(order, Order.Status.DELIVERED)
    order.order_status = Order.Status.DELIVERED
    order.save(update_fields=['order_status', 'updated_at'])
    return order


@transaction.atomic
def mark_returned(order: Order) -> Order:
    _ensure_transition(order, Order.Status.RETURNED)
    skus = order.product_variant_sku or []
    if skus:
        ProductVariant.objects.filter(
            product_id=order.product_id,
            sku__in=skus,
        ).update(is_sold=False)

    product = Product.objects.select_for_update().get(pk=order.product_id)
    released = len(skus) if skus else order.quantity
    product.total_sold = max(0, (product.total_sold or 0) - released)
    product.save(update_fields=['total_sold', 'updated_at'], skip_approval_reset=True)

    order.order_status = Order.Status.RETURNED
    order.returned_at = timezone.now()
    order.is_autopay_enabled = False
    order.save()
    return order
