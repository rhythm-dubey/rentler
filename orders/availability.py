from calendar import monthrange
from datetime import date, datetime, time, timedelta

from django.utils import timezone

from catalog.models import Product

from .models import Order


def _aware(dt: datetime) -> datetime:
    if timezone.is_naive(dt):
        return timezone.make_aware(dt, timezone.get_current_timezone())
    return dt


def overlapping_orders(product: Product, start_dt: datetime, end_dt: datetime):
    start_dt = _aware(start_dt)
    end_dt = _aware(end_dt)
    return Order.objects.occupying().filter(
        product=product,
        start_date_time__lt=end_dt,
        end_date_time__gt=start_dt,
    )


def assert_slot_available(
    product: Product,
    start_dt: datetime,
    end_dt: datetime,
    quantity: int = 1,
) -> None:
    """Raise ValueError if booking would exceed product.total_items."""
    concurrent = 0
    for order in overlapping_orders(product, start_dt, end_dt):
        concurrent += order.quantity
    if concurrent + quantity > (product.total_items or 1):
        raise ValueError('Selected dates are not available for this quantity.')


def occupied_hours(product: Product, day: date) -> list[int]:
    """Hours (0-23) on ``day`` where concurrent bookings >= total_items."""
    day_start = _aware(datetime.combine(day, time(0, 0, 0)))
    day_end = _aware(datetime.combine(day, time(23, 59, 59)))
    hour_slots = [0] * 24

    for order in overlapping_orders(product, day_start, day_end):
        order_start = max(order.start_date_time, day_start)
        order_end = min(order.end_date_time, day_end)
        if order_start > order_end:
            continue
        start_h = timezone.localtime(order_start).hour
        end_h = timezone.localtime(order_end).hour
        for hour in range(start_h, end_h + 1):
            hour_slots[hour] += order.quantity

    total = product.total_items or 1
    return [h for h, count in enumerate(hour_slots) if count >= total]


def occupied_days(product: Product, year: int, month: int) -> list[str]:
    """YYYY-MM-DD dates in month where concurrent bookings >= total_items."""
    last_day = monthrange(year, month)[1]
    month_start = _aware(datetime(year, month, 1, 0, 0, 0))
    month_end = _aware(datetime(year, month, last_day, 23, 59, 59))
    day_counts: dict[str, int] = {}

    for order in overlapping_orders(product, month_start, month_end):
        cur = max(timezone.localtime(order.start_date_time).date(), date(year, month, 1))
        end = min(
            timezone.localtime(order.end_date_time).date(),
            date(year, month, last_day),
        )
        while cur <= end:
            key = cur.isoformat()
            day_counts[key] = day_counts.get(key, 0) + order.quantity
            cur += timedelta(days=1)

    total = product.total_items or 1
    return [d for d, count in sorted(day_counts.items()) if count >= total]
