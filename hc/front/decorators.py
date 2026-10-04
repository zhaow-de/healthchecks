from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden

from hc.lib.typealias import ViewFunc


def require_setting(key: str) -> Callable[[ViewFunc], ViewFunc]:
    def decorator(f: ViewFunc) -> ViewFunc:
        @wraps(f)
        def wrapper(request: HttpRequest, *args: Any, **kwds: Any) -> HttpResponse:
            if not getattr(settings, key):
                return HttpResponse(status=404)

            return f(request, *args, **kwds)

        return wrapper

    return decorator


def deny_anonymous(f: ViewFunc) -> ViewFunc:
    """Answer 403 to a request that is not logged in, where login_required would redirect."""

    @wraps(f)
    def wrapper(request: HttpRequest, *args: Any, **kwds: Any) -> HttpResponse:
        if not request.user.is_authenticated:
            return HttpResponseForbidden()

        return f(request, *args, **kwds)

    return wrapper
