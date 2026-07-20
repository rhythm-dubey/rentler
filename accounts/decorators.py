from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*role_slugs):
    """Require the user to have at least one of the given role slugs."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user
            if user.is_superuser or any(user.has_role(slug) for slug in role_slugs):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped

    return decorator


def permission_required_codename(codename):
    """Require a custom accounts.Permission codename (or superuser)."""

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.has_permission(codename):
                return view_func(request, *args, **kwargs)
            raise PermissionDenied
        return _wrapped

    return decorator
