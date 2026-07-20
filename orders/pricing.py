from decimal import Decimal, InvalidOperation

from catalog.models import Product

from .models import Order


def _as_decimal(value) -> Decimal:
    if value is None or value == '':
        return Decimal('0')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal('0')


def unit_rent(product: Product, plan_type: str) -> Decimal:
    mapping = {
        Order.PlanType.HOURLY: product.hourly_price,
        Order.PlanType.DAILY: product.daily_price,
        Order.PlanType.WEEKLY: product.weekly_price,
        Order.PlanType.MONTHLY: product.monthly_price,
    }
    return _as_decimal(mapping.get(plan_type, 0))


def shipping_charge_for(product: Product, delivery_by: str) -> Decimal:
    if delivery_by == Order.DeliveryBy.POSTAGE:
        return _as_decimal(product.owner_postage_cost)
    if delivery_by == Order.DeliveryBy.OWNER:
        return _as_decimal(product.owner_delivery_pickup_cost)
    return Decimal('0')


def compute_pricing(
    product: Product,
    *,
    plan_type: str,
    period: int,
    quantity: int,
    delivery_by: str,
) -> dict:
    """
    Server-side pricing (no Stripe gross-up until payments app).
    total == amount for Step 4.
    """
    rent = unit_rent(product, plan_type)
    if rent <= 0:
        raise ValueError('Invalid rent price for the selected plan type.')

    period = max(1, int(period or 1))
    quantity = max(1, int(quantity or 1))

    if plan_type in (Order.PlanType.HOURLY, Order.PlanType.DAILY):
        subtotal = rent * period * quantity
    elif product.make_payment == Product.MakePayment.PER_PERIOD:
        subtotal = rent * quantity
    else:
        subtotal = rent * period * quantity

    shipping = shipping_charge_for(product, delivery_by)
    amount = subtotal + shipping

    return {
        'unit_rent': rent,
        'subtotal': subtotal.quantize(Decimal('0.01')),
        'shipping_charge': shipping.quantize(Decimal('0.01')),
        'amount': amount.quantize(Decimal('0.01')),
        'processing_fee': Decimal('0.00'),
        'total': amount.quantize(Decimal('0.01')),
        'period': period,
        'quantity': quantity,
    }
