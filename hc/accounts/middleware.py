from collections.abc import Callable
from typing import cast

from django.http import HttpRequest, HttpResponse

from hc.accounts.http import AuthenticatedHttpRequest
from hc.accounts.models import Profile

type MiddlewareFunc = Callable[[HttpRequest], HttpResponse]


class ProfileMiddleware:
    def __init__(self, get_response: MiddlewareFunc) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.get_response(request)

        request = cast(AuthenticatedHttpRequest, request)
        request.profile = Profile.objects.for_user(request.user)
        return self.get_response(request)
