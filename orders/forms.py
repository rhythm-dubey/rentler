from django import forms

from catalog.models import Product, ProductVariant

from .models import Order


class BookingStartForm(forms.Form):
    """Posted from product detail to begin the shipping session."""

    product_slug = forms.SlugField()
    plan_type = forms.ChoiceField(choices=Order.PlanType.choices)
    selected_date = forms.DateField()
    start_duration = forms.IntegerField(required=False, min_value=0)
    end_duration = forms.IntegerField(required=False, min_value=0)
    period = forms.IntegerField(required=False, min_value=1, initial=1)
    quantity = forms.IntegerField(min_value=1, initial=1)
    delivery_by = forms.ChoiceField(choices=Order.DeliveryBy.choices)

    def clean(self):
        cleaned = super().clean()
        plan = cleaned.get('plan_type')
        if plan in (Order.PlanType.HOURLY, Order.PlanType.DAILY):
            if cleaned.get('start_duration') is None or cleaned.get('end_duration') is None:
                raise forms.ValidationError('Start and end duration are required.')
        elif plan in (Order.PlanType.WEEKLY, Order.PlanType.MONTHLY):
            if not cleaned.get('period'):
                cleaned['period'] = 1
            if cleaned.get('start_duration') is None and cleaned.get('selected_date'):
                cleaned['start_duration'] = cleaned['selected_date'].day
        return cleaned


class ShippingReviewForm(forms.Form):
    delivery_by = forms.ChoiceField(choices=Order.DeliveryBy.choices)
    delivery_address = forms.CharField(required=False, max_length=255)
    city = forms.CharField(required=False, max_length=100)
    state = forms.CharField(required=False, max_length=100)
    post_code = forms.CharField(required=False, max_length=20)
    quantity = forms.IntegerField(min_value=1)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('delivery_by') != Order.DeliveryBy.RENTER:
            for field in ('delivery_address', 'city', 'state', 'post_code'):
                if not (cleaned.get(field) or '').strip():
                    self.add_error(field, 'This field is required for delivery.')
        return cleaned


class CancelRequestForm(forms.Form):
    reason = forms.CharField(max_length=255, required=False)
    comment = forms.CharField(widget=forms.Textarea, required=False)


class OwnerCancelForm(forms.Form):
    notes = forms.CharField(widget=forms.Textarea, required=False)
    refund_amount = forms.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        min_value=0,
    )


class DeliverOrderForm(forms.Form):
    variant_skus = forms.MultipleChoiceField(choices=[], required=False)

    def __init__(self, *args, order: Order, **kwargs):
        super().__init__(*args, **kwargs)
        free = ProductVariant.objects.filter(
            product_id=order.product_id,
            is_sold=False,
        ).order_by('id')
        self.fields['variant_skus'].choices = [(v.sku, v.sku) for v in free]
        self.order = order
        self.has_variants = ProductVariant.objects.filter(
            product_id=order.product_id
        ).exists()
        if self.has_variants:
            self.fields['variant_skus'].required = True

    def clean_variant_skus(self):
        skus = self.cleaned_data.get('variant_skus') or []
        if self.has_variants and len(skus) != self.order.quantity:
            raise forms.ValidationError(
                f'Select exactly {self.order.quantity} variant(s).'
            )
        return skus


def delivery_choices_for_product(product: Product) -> list[tuple[str, str]]:
    choices = []
    if product.owner_pickup:
        choices.append((Order.DeliveryBy.RENTER, 'Pick up myself'))
    if product.owner_delivery_pickup:
        choices.append((Order.DeliveryBy.OWNER, 'Owner delivery'))
    if product.owner_postage:
        choices.append((Order.DeliveryBy.POSTAGE, 'Postage'))
    if not choices:
        choices.append((Order.DeliveryBy.RENTER, 'Pick up myself'))
    return choices


def plan_choices_for_product(product: Product) -> list[tuple[str, str]]:
    choices = []
    if product.hourly_price and product.hourly_price > 0:
        choices.append((Order.PlanType.HOURLY, f'Hourly (${product.hourly_price})'))
    if product.daily_price and product.daily_price > 0:
        choices.append((Order.PlanType.DAILY, f'Daily (${product.daily_price})'))
    if product.weekly_price and product.weekly_price > 0:
        choices.append((Order.PlanType.WEEKLY, f'Weekly (${product.weekly_price})'))
    if product.monthly_price and product.monthly_price > 0:
        choices.append((Order.PlanType.MONTHLY, f'Monthly (${product.monthly_price})'))
    return choices
