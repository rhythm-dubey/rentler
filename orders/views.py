from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from accounts.decorators import permission_required_codename
from catalog.models import Product, ProductVariant

from .forms import (
    BookingStartForm,
    CancelRequestForm,
    DeliverOrderForm,
    OwnerCancelForm,
    ShippingReviewForm,
    delivery_choices_for_product,
    plan_choices_for_product,
)
from .models import Order
from .pricing import compute_pricing
from .services import (
    TransitionError,
    accept_cancellation,
    build_rental_window,
    create_order_from_checkout,
    mark_delivered,
    mark_returned,
    request_cancellation,
    request_return,
    revert_cancellation,
    revert_return,
)


def _serialize_dt(dt):
    if hasattr(dt, 'isoformat'):
        return dt.isoformat()
    return str(dt)


@permission_required_codename('order.create')
@require_POST
def shipping_process(request):
    form = BookingStartForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Please fix the booking details and try again.')
        slug = request.POST.get('product_slug')
        if slug:
            return redirect('catalog:detail', slug=slug)
        return redirect('catalog:browse')

    data = form.cleaned_data
    product = get_object_or_404(Product.objects.listed(), slug=data['product_slug'])
    plan_choices = plan_choices_for_product(product)
    if data['plan_type'] not in dict(plan_choices):
        messages.error(request, 'Selected plan is not available for this product.')
        return redirect('catalog:detail', slug=product.slug)

    delivery_choices = delivery_choices_for_product(product)
    if data['delivery_by'] not in dict(delivery_choices):
        messages.error(request, 'Selected delivery option is not available.')
        return redirect('catalog:detail', slug=product.slug)

    try:
        start_dt, end_dt, period = build_rental_window(
            product,
            plan_type=data['plan_type'],
            selected_date=data['selected_date'],
            start_duration=data.get('start_duration'),
            end_duration=data.get('end_duration'),
            period=data.get('period') or 1,
        )
        pricing = compute_pricing(
            product,
            plan_type=data['plan_type'],
            period=period,
            quantity=data['quantity'],
            delivery_by=data['delivery_by'],
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('catalog:detail', slug=product.slug)

    request.session['shipping_data'] = {
        'product_id': product.pk,
        'product_slug': product.slug,
        'plan_type': data['plan_type'],
        'start_date_time': _serialize_dt(start_dt),
        'end_date_time': _serialize_dt(end_dt),
        'period': period,
        'quantity': data['quantity'],
        'delivery_by': data['delivery_by'],
        'subtotal': str(pricing['subtotal']),
        'shipping_charge': str(pricing['shipping_charge']),
        'total': str(pricing['total']),
    }
    request.session.pop('checkout_data', None)
    return redirect('orders:shipping')


@permission_required_codename('order.create')
@require_GET
def shipping(request):
    shipping_data = request.session.get('shipping_data')
    if not shipping_data:
        messages.info(request, 'Start a booking from a product page.')
        return redirect('catalog:browse')

    product = get_object_or_404(
        Product.objects.listed(),
        pk=shipping_data['product_id'],
    )
    initial = {
        'delivery_by': shipping_data.get('delivery_by'),
        'quantity': shipping_data.get('quantity', 1),
        'delivery_address': request.user.address,
        'city': request.user.city,
        'state': request.user.state,
        'post_code': request.user.post_code,
    }
    form = ShippingReviewForm(initial=initial)
    form.fields['delivery_by'].choices = delivery_choices_for_product(product)
    return render(
        request,
        'orders/shipping.html',
        {
            'product': product,
            'shipping': shipping_data,
            'form': form,
        },
    )


@permission_required_codename('order.create')
@require_POST
def checkout_process(request):
    shipping_data = request.session.get('shipping_data')
    if not shipping_data:
        messages.info(request, 'Start a booking from a product page.')
        return redirect('catalog:browse')

    product = get_object_or_404(
        Product.objects.listed(),
        pk=shipping_data['product_id'],
    )
    form = ShippingReviewForm(request.POST)
    form.fields['delivery_by'].choices = delivery_choices_for_product(product)
    if not form.is_valid():
        return render(
            request,
            'orders/shipping.html',
            {'product': product, 'shipping': shipping_data, 'form': form},
        )

    data = form.cleaned_data
    delivery_address = ''
    if data['delivery_by'] != Order.DeliveryBy.RENTER:
        delivery_address = ' '.join(
            [
                data['delivery_address'],
                data['city'],
                data['state'],
                data['post_code'],
            ]
        ).strip()
        user = request.user
        user.address = data['delivery_address']
        user.city = data['city']
        user.state = data['state']
        user.post_code = data['post_code']
        user.save(update_fields=['address', 'city', 'state', 'post_code'])

    try:
        pricing = compute_pricing(
            product,
            plan_type=shipping_data['plan_type'],
            period=shipping_data['period'],
            quantity=data['quantity'],
            delivery_by=data['delivery_by'],
        )
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('orders:shipping')

    request.session['checkout_data'] = {
        'product_id': product.pk,
        'product_slug': product.slug,
        'plan_type': shipping_data['plan_type'],
        'start_date_time': shipping_data['start_date_time'],
        'end_date_time': shipping_data['end_date_time'],
        'period': pricing['period'],
        'quantity': pricing['quantity'],
        'delivery_by': data['delivery_by'],
        'delivery_address': delivery_address,
        'subtotal': str(pricing['subtotal']),
        'shipping_charge': str(pricing['shipping_charge']),
        'amount': str(pricing['amount']),
        'processing_fee': str(pricing['processing_fee']),
        'total': str(pricing['total']),
    }
    return redirect('orders:checkout')


@permission_required_codename('order.create')
@require_GET
def checkout(request):
    checkout_data = request.session.get('checkout_data')
    if not checkout_data:
        messages.info(request, 'Complete shipping details first.')
        return redirect('catalog:browse')

    product = get_object_or_404(
        Product.objects.listed(),
        pk=checkout_data['product_id'],
    )
    return render(
        request,
        'orders/checkout.html',
        {'product': product, 'checkout': checkout_data},
    )


@permission_required_codename('order.create')
@require_POST
def order_create(request):
    checkout_data = request.session.get('checkout_data')
    if not checkout_data:
        messages.info(request, 'Complete checkout first.')
        return redirect('catalog:browse')

    try:
        order = create_order_from_checkout(request.user, checkout_data)
    except (ValueError, Product.DoesNotExist) as exc:
        messages.error(request, str(exc))
        return redirect('orders:checkout')

    request.session.pop('checkout_data', None)
    request.session.pop('shipping_data', None)
    messages.success(request, f'Order {order.id_label} placed successfully.')
    return redirect('orders:success', id_label=order.id_label)


@permission_required_codename('order.create')
@require_GET
def order_success(request, id_label):
    order = get_object_or_404(
        Order.objects.for_renter(request.user).select_related('product'),
        id_label=id_label,
    )
    return render(request, 'orders/success.html', {'order': order})


@permission_required_codename('order.create')
@require_GET
def renter_list(request):
    tab = request.GET.get('tab') or Order.Status.NEW_ORDER
    qs = Order.objects.for_renter(request.user).select_related('product')
    counts = dict(
        Order.objects.for_renter(request.user)
        .values('order_status')
        .annotate(c=Count('id'))
        .values_list('order_status', 'c')
    )
    if tab == 'due-back':
        qs = qs.due_back()
    elif tab in dict(Order.Status.choices):
        qs = qs.filter(order_status=tab)

    page = Paginator(qs, 20).get_page(request.GET.get('page'))
    tabs = [
        {'value': value, 'label': label, 'count': counts.get(value, 0)}
        for value, label in Order.Status.choices
    ]
    return render(
        request,
        'orders/renter/list.html',
        {
            'page_obj': page,
            'orders': page.object_list,
            'tab': tab,
            'tabs': tabs,
        },
    )


@permission_required_codename('order.create')
@require_GET
def renter_detail(request, id_label):
    order = get_object_or_404(
        Order.objects.for_renter(request.user).select_related('product', 'product__owner'),
        id_label=id_label,
    )
    cancel_form = CancelRequestForm()
    return render(
        request,
        'orders/renter/detail.html',
        {'order': order, 'cancel_form': cancel_form},
    )


@permission_required_codename('order.create')
@require_POST
def manage_status(request):
    order = get_object_or_404(
        Order.objects.for_renter(request.user),
        pk=request.POST.get('order_id'),
    )
    action = request.POST.get('action')
    try:
        if action == 'request-cancellation':
            form = CancelRequestForm(request.POST)
            if form.is_valid():
                request_cancellation(
                    order,
                    reason=form.cleaned_data.get('reason') or '',
                    comment=form.cleaned_data.get('comment') or '',
                )
                messages.success(request, 'Cancellation requested.')
            else:
                messages.error(request, 'Invalid cancellation request.')
        elif action == 'revert-cancellation':
            revert_cancellation(order)
            messages.success(request, 'Cancellation request withdrawn.')
        elif action == 'request-return':
            request_return(order)
            messages.success(request, 'Return requested.')
        elif action == 'revert-return':
            revert_return(order)
            messages.success(request, 'Return request withdrawn.')
        else:
            messages.error(request, 'Unknown action.')
    except TransitionError as exc:
        messages.error(request, str(exc))

    return redirect('orders:renter_detail', id_label=order.id_label)


@permission_required_codename('order.manage_own')
@require_GET
def owner_list(request):
    tab = request.GET.get('tab') or Order.Status.NEW_ORDER
    search = (request.GET.get('search') or '').strip()
    qs = Order.objects.for_owner(request.user).select_related('product', 'user')

    if search:
        qs = qs.filter(
            Q(id_label__icontains=search)
            | Q(user_name__icontains=search)
            | Q(order_status__icontains=search)
            | Q(product__name__icontains=search)
        )

    counts = dict(
        Order.objects.for_owner(request.user)
        .values('order_status')
        .annotate(c=Count('id'))
        .values_list('order_status', 'c')
    )
    counts['due-back'] = Order.objects.for_owner(request.user).due_back().count()

    if tab == 'due-back':
        qs = qs.due_back()
    elif tab in dict(Order.Status.choices):
        qs = qs.filter(order_status=tab)

    page = Paginator(qs.order_by('-created_at'), 20).get_page(request.GET.get('page'))
    tabs = [
        {'value': value, 'label': label, 'count': counts.get(value, 0)}
        for value, label in Order.Status.choices
    ]
    tabs.append(
        {'value': 'due-back', 'label': 'Due back', 'count': counts.get('due-back', 0)}
    )
    return render(
        request,
        'orders/owner/list.html',
        {
            'page_obj': page,
            'orders': page.object_list,
            'tab': tab,
            'tabs': tabs,
            'search': search,
        },
    )


@permission_required_codename('order.manage_own')
@require_GET
def owner_detail(request, id_label):
    order = get_object_or_404(
        Order.objects.for_owner(request.user).select_related('product', 'user'),
        id_label=id_label,
    )
    free_variants = ProductVariant.objects.filter(
        product_id=order.product_id,
        is_sold=False,
    )
    deliver_form = DeliverOrderForm(order=order) if order.order_status == Order.Status.NEW_ORDER else None
    cancel_form = (
        OwnerCancelForm()
        if order.order_status == Order.Status.REQUEST_CANCELLATION
        else None
    )
    return render(
        request,
        'orders/owner/detail.html',
        {
            'order': order,
            'deliver_form': deliver_form,
            'cancel_form': cancel_form,
            'free_variants': free_variants,
        },
    )


@permission_required_codename('order.manage_own')
@require_POST
def owner_deliver(request, id_label):
    order = get_object_or_404(
        Order.objects.for_owner(request.user),
        id_label=id_label,
    )
    form = DeliverOrderForm(request.POST, order=order)
    if not form.is_valid():
        messages.error(request, 'Select the required free variants.')
        return redirect('orders:owner_detail', id_label=id_label)
    try:
        mark_delivered(order, form.cleaned_data['variant_skus'])
        messages.success(request, 'Order marked as delivered.')
    except (TransitionError, ValueError) as exc:
        messages.error(request, str(exc))
    return redirect('orders:owner_detail', id_label=id_label)


@permission_required_codename('order.manage_own')
@require_POST
def owner_return(request, id_label):
    order = get_object_or_404(
        Order.objects.for_owner(request.user),
        id_label=id_label,
    )
    try:
        mark_returned(order)
        messages.success(request, 'Order marked as returned.')
    except TransitionError as exc:
        messages.error(request, str(exc))
    return redirect('orders:owner_detail', id_label=id_label)


@permission_required_codename('order.manage_own')
@require_POST
def owner_accept_cancel(request, id_label):
    order = get_object_or_404(
        Order.objects.for_owner(request.user),
        id_label=id_label,
    )
    form = OwnerCancelForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Invalid cancellation form.')
        return redirect('orders:owner_detail', id_label=id_label)
    try:
        accept_cancellation(
            order,
            notes=form.cleaned_data.get('notes') or '',
            refund_amount=form.cleaned_data.get('refund_amount'),
        )
        messages.success(request, 'Order cancelled.')
    except TransitionError as exc:
        messages.error(request, str(exc))
    return redirect('orders:owner_detail', id_label=id_label)
