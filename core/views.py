from django.shortcuts import render

from catalog.models import Category, Product

from .models import Setting


def home(request):
    featured_categories = Category.objects.filter(
        parent__isnull=True,
        is_active=True,
    )[:8]
    featured_products = (
        Product.objects.listed()
        .filter(is_featured=True)
        .select_related('category', 'owner')[:10]
    )
    return render(
        request,
        'core/home.html',
        {
            'featured_categories': featured_categories,
            'featured_products': featured_products,
        },
    )


def about(request):
    return render(request, 'core/about.html')


def privacy(request):
    return render(request, 'core/privacy.html')


def terms(request):
    return render(
        request,
        'core/terms.html',
        {'terms_html': Setting.get_html('tnc')},
    )


def account_deletion(request):
    return render(request, 'core/account_deletion.html')
