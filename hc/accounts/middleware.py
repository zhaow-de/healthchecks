from collections.abc import Callable
from typing import cast

from django.http import HttpRequest, HttpResponse
from django.utils.functional import SimpleLazyObject

from hc.accounts.http import AuthenticatedHttpRequest
from hc.accounts.models import Profile

type MiddlewareFunc = Callable[[HttpRequest], HttpResponse]


class ProfileMiddleware:
    def __init__(self, get_response: MiddlewareFunc) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Loaded on first use, so a request that never reads it (a ping, an API call)
        # does not read the session either, and its response does not vary on Cookie
        request = cast(AuthenticatedHttpRequest, request)
        request.profile = cast(Profile, SimpleLazyObject(lambda: Profile.objects.for_user(request.user)))
        return self.get_response(request)
