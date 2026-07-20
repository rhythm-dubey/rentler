from core.models import Setting


def site_settings(request):
    """Expose common website settings to all templates."""
    return {
        'company_name': Setting.get_str('company_name', default='Rentler'),
        'support_email': Setting.get_str('support_email', default=''),
        'support_phone': Setting.get_str('support_phone', default=''),
    }
