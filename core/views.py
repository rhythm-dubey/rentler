from django.shortcuts import render

from .models import Setting


def home(request):
    return render(request, 'core/home.html')


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
