from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from accounts.decorators import permission_required_codename
from core.models import Setting

from .forms import ProductBrowseFilterForm, ProductForm, ProductVariantForm
from .models import Category, Product, ProductVariant


def _apply_browse_filters(queryset, cleaned):
    q = (cleaned.get('q') or '').strip()
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(description__icontains=q)
            | Q(city__icontains=q)
            | Q(sku__icontains=q)
        )

    category_slug = (cleaned.get('category') or '').strip()
    if category_slug:
        category = Category.objects.filter(slug=category_slug, is_active=True).first()
        if category:
            queryset = queryset.filter(category_id__in=category.get_descendant_ids())

    for field in ('city', 'state', 'post_code'):
        value = (cleaned.get(field) or '').strip()
        if value:
            queryset = queryset.filter(**{f'{field}__iexact': value})

    if cleaned.get('delivery'):
        queryset = queryset.filter(owner_delivery_pickup=True)
    if cleaned.get('pickup'):
        queryset = queryset.filter(owner_pickup=True)
    if cleaned.get('postage'):
        queryset = queryset.filter(owner_postage=True)

    return queryset


@require_GET
def browse(request):
    form = ProductBrowseFilterForm(request.GET or None)
    products = Product.objects.listed().select_related('category', 'owner')
    if form.is_valid():
        products = _apply_browse_filters(products, form.cleaned_data)

    paginator = Paginator(products, 15)
    page = paginator.get_page(request.GET.get('page'))
    categories = Category.objects.filter(parent__isnull=True, is_active=True)

    return render(
        request,
        'catalog/browse.html',
        {
            'form': form,
            'page_obj': page,
            'products': page.object_list,
            'categories': categories,
        },
    )


@require_GET
def detail(request, slug):
    from datetime import date

    from orders.availability import occupied_days, occupied_hours
    from orders.forms import delivery_choices_for_product, plan_choices_for_product

    product = get_object_or_404(
        Product.objects.listed().select_related('category', 'owner'),
        slug=slug,
    )
    today = date.today()
    return render(
        request,
        'catalog/detail.html',
        {
            'product': product,
            'plan_choices': plan_choices_for_product(product),
            'delivery_choices': delivery_choices_for_product(product),
            'occupied_hours': occupied_hours(product, today),
            'occupied_days': occupied_days(product, today.year, today.month),
            'hour_choices': list(range(0, 24)),
        },
    )


@require_GET
def terms(request, slug):
    product = get_object_or_404(
        Product.objects.listed().select_related('category', 'owner'),
        slug=slug,
    )
    if product.which_tnc == Product.WhichTnc.OWN and product.tnc:
        terms_html = product.tnc
    else:
        terms_html = Setting.get_html('rental_tnc') or Setting.get_html('tnc')
    return render(
        request,
        'catalog/tnc.html',
        {'product': product, 'terms_html': terms_html},
    )


@require_GET
def subcategories(request):
    parent_slug = (request.GET.get('parent') or '').strip()
    if not parent_slug:
        return JsonResponse({'subcategories': []})
    parent = Category.objects.filter(slug=parent_slug, is_active=True).first()
    if not parent:
        return JsonResponse({'subcategories': []})
    children = parent.children.filter(is_active=True).order_by('sort_order', 'name')
    return JsonResponse(
        {
            'subcategories': [
                {'id': c.id, 'name': c.name, 'slug': c.slug} for c in children
            ]
        }
    )


@permission_required_codename('product.manage_own')
def manage_list(request):
    products = (
        Product.objects.filter(owner=request.user)
        .select_related('category')
        .order_by('-created_at')
    )
    return render(request, 'catalog/manage/list.html', {'products': products})


@permission_required_codename('product.manage_own')
@require_http_methods(['GET', 'POST'])
def manage_create(request):
    form = ProductForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        product = form.save(commit=False)
        product.owner = request.user
        product.created_by = Product.CreatedBy.WEB
        if not request.user.stripe_charges_enabled:
            product.is_active = False
            messages.warning(
                request,
                'Your listing was saved as inactive until Stripe charges are enabled.',
            )
        product.is_admin_approved = False
        product.save(skip_approval_reset=True)
        ProductVariant.create_variants(product, count=product.total_items or 1)
        messages.success(request, 'Product created. It will appear publicly after approval.')
        return redirect('catalog:manage_edit', slug=product.slug)

    return render(
        request,
        'catalog/manage/form.html',
        {'form': form, 'title': 'Create listing', 'product': None},
    )


@permission_required_codename('product.manage_own')
@require_http_methods(['GET', 'POST'])
def manage_edit(request, slug):
    product = get_object_or_404(Product, slug=slug, owner=request.user)
    form = ProductForm(request.POST or None, request.FILES or None, instance=product)
    if request.method == 'POST' and form.is_valid():
        product = form.save(commit=False)
        if not request.user.stripe_charges_enabled:
            product.is_active = False
        # Owner edits reset admin approval (default save behavior).
        product.save()
        messages.success(request, 'Product updated. Re-approval may be required.')
        return redirect('catalog:manage_edit', slug=product.slug)

    return render(
        request,
        'catalog/manage/form.html',
        {'form': form, 'title': 'Edit listing', 'product': product},
    )


@permission_required_codename('product.manage_own')
@require_POST
def manage_delete(request, slug):
    product = get_object_or_404(Product, slug=slug, owner=request.user)
    product.delete()
    messages.success(request, 'Product deactivated.')
    return redirect('catalog:manage_list')


@permission_required_codename('product.manage_own')
def manage_variants(request, slug):
    product = get_object_or_404(Product, slug=slug, owner=request.user)
    variants = product.variants.all()
    form = ProductVariantForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        variant = form.save(commit=False)
        variant.product = product
        variant.save()
        messages.success(request, 'Variant added.')
        return redirect('catalog:manage_variants', slug=product.slug)
    return render(
        request,
        'catalog/manage/variants.html',
        {'product': product, 'variants': variants, 'form': form},
    )


@permission_required_codename('product.manage_own')
@require_POST
def manage_variant_toggle(request, slug, variant_id):
    product = get_object_or_404(Product, slug=slug, owner=request.user)
    variant = get_object_or_404(ProductVariant, pk=variant_id, product=product)
    variant.is_sold = not variant.is_sold
    variant.save(update_fields=['is_sold', 'updated_at'])
    messages.success(request, 'Variant updated.')
    return redirect('catalog:manage_variants', slug=product.slug)
