import json
from collections.abc import Callable
from functools import wraps
from typing import Any

from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotAllowed, HttpResponseNotFound, JsonResponse
from django.utils.cache import add_never_cache_headers

from hc.accounts.models import Project
from hc.lib.typealias import ViewFunc

# Separate from DATA_UPLOAD_MAX_MEMORY_SIZE, which bounds ping bodies too
API_BODY_LIMIT = 64 * 1024


class ApiRequest(HttpRequest):
    json: dict[Any, Any]
    project: Project
    readonly: bool


def error(msg: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": msg}, status=status)


def _project(api_key: str, accept_ro: bool) -> Project | JsonResponse:
    if len(api_key) != 32:
        return error("missing api key", 401)

    project = Project.objects.for_api_key(api_key, accept_rw=True, accept_ro=accept_ro)
    if project is None:
        return error("wrong api key", 401)

    return project


def _parse_body(request: ApiRequest) -> JsonResponse | None:
    """Put the JSON object of a POST body in request.json; return the 400 if it is not one."""
    request.json = {}
    if request.method == "POST" and request.body:
        try:
            request.json = json.loads(request.body.decode())
        except ValueError, RecursionError:
            return error("could not parse request body")
        if not isinstance(request.json, dict):
            return error("json validation error: value is not an object")

    return None


def authorize(f: ViewFunc) -> ViewFunc:
    @wraps(f)
    def wrapper(request: ApiRequest, *args: Any, **kwds: Any) -> HttpResponse:
        # WSGI reads no more of the body than CONTENT_LENGTH says
        try:
            content_length = int(request.META.get("CONTENT_LENGTH") or 0)
        except ValueError:
            content_length = 0
        if request.method == "POST" and content_length > API_BODY_LIMIT:
            return error("request body too large", 413)

        if "X-Api-Key" in request.headers:
            # Checked before the body is read, so a client without a valid key
            # cannot make the server parse one
            project = _project(request.headers["X-Api-Key"], accept_ro=False)
            if isinstance(project, JsonResponse):
                return project
            if (response := _parse_body(request)) is not None:
                return response
        else:
            if (response := _parse_body(request)) is not None:
                return response
            project = _project(str(request.json.get("api_key", "")), accept_ro=False)
            if isinstance(project, JsonResponse):
                return project

        request.project = project
        request.readonly = False
        return f(request, *args, **kwds)

    return wrapper


def authorize_read(f: ViewFunc) -> ViewFunc:
    @wraps(f)
    def wrapper(request: ApiRequest, *args: Any, **kwds: Any) -> HttpResponse:
        api_key = request.headers.get("X-Api-Key", "")
        project = _project(api_key, accept_ro=True)
        if isinstance(project, JsonResponse):
            return project

        request.project = project
        request.readonly = api_key.startswith("hcr_")
        return f(request, *args, **kwds)

    return wrapper


def cors(*methods: str) -> Callable[[ViewFunc], ViewFunc]:
    allowed = list(dict.fromkeys((*methods, "OPTIONS")))
    methods_str = ", ".join(allowed)

    def decorator(f: ViewFunc) -> ViewFunc:
        @wraps(f)
        def wrapper(request: HttpRequest, *args: Any, **kwds: Any) -> HttpResponse:
            if request.method == "OPTIONS":
                response = HttpResponse(status=204)
            elif request.method in methods:
                try:
                    response = f(request, *args, **kwds)
                except Http404:
                    # Answered here, not by Django's 404 page, so it carries the headers below
                    response = HttpResponseNotFound()
            else:
                response = HttpResponseNotAllowed(allowed)

            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Headers"] = "X-Api-Key, Content-Type"
            response["Access-Control-Allow-Methods"] = methods_str
            response["Access-Control-Max-Age"] = "600"
            # Check objects carry ping URLs: no shared cache may store them
            add_never_cache_headers(response)
            return response

        return wrapper

    return decorator
