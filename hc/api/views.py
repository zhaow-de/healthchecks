import email.policy
import hmac
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from datetime import timedelta as td
from email import message_from_bytes
from functools import wraps
from typing import Any, Literal
from uuid import UUID

from cronsim import CronSim, CronSimError
from django.conf import settings
from django.core.signing import BadSignature
from django.db import connection, transaction
from django.db.models import Q
from django.db.models.functions import Length
from django.http import (
    Http404,
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    JsonResponse,
)
from django.shortcuts import get_object_or_404
from django.utils.timezone import now
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from oncalendar import OnCalendar, OnCalendarError
from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from pydantic_core import PydanticCustomError

from hc.accounts.models import Profile, Project
from hc.api.decorators import ApiRequest, authorize, authorize_read, cors
from hc.api.forms import FlipsFiltersForm
from hc.api.models import Channel, Check, Flip, Notification, Ping, find_by_unique_key, prepare_durations
from hc.lib.ip import client_ip
from hc.lib.signing import unsign_bounce_id
from hc.lib.string import is_valid_uuid_string
from hc.lib.typealias import ViewFunc
from hc.lib.tz import all_timezones, legacy_timezones


class BadChannelError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def guess_kind(schedule: str) -> str:
    # If it is a single line with 5 components, it is probably a cron expression:
    if "\n" not in schedule.strip() and len(schedule.split()) == 5:
        return "cron"

    return "oncalendar"


class Spec(BaseModel):
    channels: str | None = None
    desc: str | None = Field(None, max_length=10_000)
    failure_kw: str | None = Field(None, max_length=200)
    filter_subject: bool | None = None
    filter_body: bool | None = None
    filter_http_body: bool | None = None
    filter_default_fail: bool | None = None
    grace: td | None = Field(None, ge=60, le=31536000)
    manual_resume: bool | None = None
    methods: Literal["", "POST"] | None = None
    name: str | None = Field(None, max_length=100)
    schedule: str | None = Field(None, max_length=100)
    slug: str | None = Field(None, max_length=100, pattern="^[a-z0-9-_]*$")
    start_kw: str | None = Field(None, max_length=200)
    subject: str | None = Field(None, max_length=200)
    subject_fail: str | None = Field(None, max_length=200)
    success_kw: str | None = Field(None, max_length=200)
    tags: str | None = Field(None, max_length=500)
    timeout: td | None = Field(None, ge=60, le=31536000)
    tz: str | None = None
    unique: list[Literal["name", "slug", "tags", "timeout", "grace"]] | None = None

    @model_validator(mode="before")
    @classmethod
    def check_nulls(cls, data: dict[str, Any]) -> dict[str, Any]:
        # Look for any null values in the incoming data. Replace them with a
        # float. None of the fields have a float type, and we are using
        # strict validation, so this will cause type validation to fail.
        for k, v in data.items():
            if v is None:
                data[k] = 0.0
        return data

    @field_validator("timeout", "grace", mode="before")
    @classmethod
    def convert_to_timedelta(cls, v: Any) -> Any:
        if isinstance(v, int):
            return td(seconds=v)
        return v

    @field_validator("tz")
    @classmethod
    def check_tz(cls, v: str) -> str:
        if v in legacy_timezones:
            # Replace legacy timezone with the current canonical time zone
            # (for example, Europe/Kiev -> Europe/Kyiv)
            v = legacy_timezones[v]

        if v not in all_timezones:
            raise PydanticCustomError("tz_syntax", "not a valid timezone")
        return v

    @field_validator("schedule")
    @classmethod
    def check_schedule(cls, v: str) -> str:
        if guess_kind(v) == "cron":
            try:
                # Test if cronsim accepts it and can calculate the next datetime
                it = CronSim(v, datetime(2000, 1, 1, tzinfo=UTC))
                next(it)
            except CronSimError, StopIteration:
                raise PydanticCustomError("cron_syntax", "not a valid cron expression") from None
        else:
            try:
                # Test if oncalendar accepts it, and can calculate the next datetime
                oncalendar_it = OnCalendar(v, datetime(2000, 1, 1, tzinfo=UTC))
                next(oncalendar_it)
            except OnCalendarError, StopIteration:
                raise PydanticCustomError("cron_syntax", "not a valid expression") from None

        return v

    def kind(self) -> str | None:
        if self.schedule:
            return guess_kind(self.schedule)

        if self.timeout:
            return "simple"

        return None


CUSTOM_ERRORS = {
    "too_long": "%s is too long",
    "string_too_long": "%s is too long",
    "string_type": "%s is not a string",
    "string_pattern_mismatch": "%s does not match pattern",
    "less_than_equal": "%s is too large",
    "greater_than_equal": "%s is too small",
    "int_type": "%s is not a number",
    "bool_type": "%s is not a boolean",
    "literal_error": "%s has unexpected value",
    "list_type": "%s is not an array",
    "cron_syntax": "%s is not a valid cron or OnCalendar expression",
    "tz_syntax": "%s is not a valid timezone",
    "time_delta_type": "%s is not a number",
}


def format_first_error(exc: ValidationError) -> str:
    first_error = exc.errors()[0]
    subject = first_error["loc"][0]
    if len(first_error["loc"]) == 2:
        subject = f"an item in '{subject}'"

    tmpl = CUSTOM_ERRORS[first_error["type"]]
    return "json validation error: " + tmpl % subject


def _ping_preflight(view: ViewFunc) -> ViewFunc:
    """Answer a browser's CORS preflight (OPTIONS) to a ping URL, recording no ping."""

    @wraps(view)
    def wrapper(request: HttpRequest, *args: Any, **kwds: Any) -> HttpResponse:
        if request.method != "OPTIONS":
            return view(request, *args, **kwds)

        response = HttpResponse(status=204)
        response["Access-Control-Allow-Origin"] = "*"
        response["Access-Control-Allow-Methods"] = "GET, HEAD, POST, OPTIONS"
        response["Access-Control-Allow-Headers"] = request.headers.get("Access-Control-Request-Headers", "Content-Type")
        response["Access-Control-Max-Age"] = "600"
        return response

    return wrapper


def _ping(request: HttpRequest, lookup: Q, action: str, exitstatus: int | None) -> HttpResponse:
    if exitstatus is not None and exitstatus > 255:
        return HttpResponseBadRequest("invalid url format")

    rid, rid_str = None, request.GET.get("rid")
    if rid_str is not None:
        if not is_valid_uuid_string(rid_str):
            return HttpResponseBadRequest("invalid uuid format")
        rid = UUID(rid_str)

    if exitstatus is not None and exitstatus > 0:
        action = "fail"

    # Read before Check.ping takes the lock: the body may still be arriving
    body = request.body[: settings.PING_BODY_LIMIT]
    try:
        Check.ping(
            lookup,
            remote_addr=client_ip(request),
            scheme="https" if request.is_secure() else "http",
            method=request.META["REQUEST_METHOD"],
            ua=request.headers.get("User-Agent", ""),
            body=body,
            action=action,
            rid=rid,
            exitstatus=exitstatus,
        )
    except Check.DoesNotExist:
        return HttpResponseNotFound("not found")
    except Check.MultipleObjectsReturned:
        return HttpResponse("ambiguous slug", status=409)

    response = HttpResponse("OK")
    if settings.PING_BODY_LIMIT is not None:
        response["Ping-Body-Limit"] = str(settings.PING_BODY_LIMIT)
    response["Access-Control-Allow-Origin"] = "*"
    response["Access-Control-Expose-Headers"] = "Ping-Body-Limit"
    return response


@csrf_exempt
@never_cache
@_ping_preflight
def ping(request: HttpRequest, code: UUID, action: str = "success", exitstatus: int | None = None) -> HttpResponse:
    return _ping(request, Q(code=code), action, exitstatus)


@csrf_exempt
@never_cache
@_ping_preflight
def ping_by_slug(
    request: HttpRequest,
    ping_key: str,
    slug: str,
    action: str = "success",
    exitstatus: int | None = None,
) -> HttpResponse:
    if slug != slug.lower():
        return HttpResponseBadRequest("invalid url format")

    return _ping(request, Q(slug=slug, project__ping_key=ping_key), action, exitstatus)


def _with_check(view: Callable[..., HttpResponse]) -> ViewFunc:
    """Pass the view the check `code` names: 404 if there is none, 403 if another project owns it.

    The 403 is returned, not raised, so it keeps its empty body and the cors headers.
    """

    @wraps(view)
    def wrapper(request: ApiRequest, code: UUID, **kwds: Any) -> HttpResponse:
        check = get_object_or_404(Check, code=code)
        if check.project_id != request.project.id:
            return HttpResponseForbidden()

        check.project = request.project
        try:
            return view(request, check, **kwds)
        except Check.DoesNotExist:
            # Deleted between this read and the Check.lock() of a write
            return HttpResponseNotFound()

    return wrapper


def _lookup(project: Project, spec: Spec) -> Check | None:
    if not spec.unique:
        return None

    for field_name in spec.unique:
        # If any field referenced in 'unique' is absent then return None
        # (meaning, did not find a matching Check)
        if getattr(spec, field_name) is None:
            return None

    existing_checks = Check.objects.filter(project=project)
    if "name" in spec.unique:
        existing_checks = existing_checks.filter(name=spec.name)
    if "slug" in spec.unique:
        existing_checks = existing_checks.filter(slug=spec.slug)
    if "tags" in spec.unique:
        existing_checks = existing_checks.filter(tags=spec.tags)
    if "timeout" in spec.unique:
        existing_checks = existing_checks.filter(timeout=spec.timeout)
    if "grace" in spec.unique:
        existing_checks = existing_checks.filter(grace=spec.grace)

    return existing_checks.first()


def _update(check: Check, spec: Spec) -> None:
    new_channels: Iterable[Channel] | None
    # First, validate the supplied channel codes/names
    match spec.channels:
        case None:
            # If the channels key is not present, don't update check's channels
            new_channels = None
        case "*":
            # "*" means "all project's channels"
            new_channels = Channel.objects.filter(project=check.project)
        case "":
            # "" means "empty list"
            new_channels = []
        case _:
            # expect a comma-separated list of channel codes or names
            new_channels = set()
            available = list(Channel.objects.filter(project=check.project))

            for s in spec.channels.split(","):
                if s == "":
                    raise BadChannelError("empty channel identifier")

                matches = [c for c in available if str(c.code) == s or c.name == s]
                if len(matches) == 0:
                    raise BadChannelError(f"invalid channel identifier: {s}")
                if len(matches) > 1:
                    raise BadChannelError(f"non-unique channel identifier: {s}")

                new_channels.add(matches[0])

    with transaction.atomic():
        if not check._state.adding:
            check.lock()
        _apply(check, spec, new_channels)


def _apply(check: Check, spec: Spec, new_channels: Iterable[Channel] | None) -> None:
    """Set the spec's fields and alert_after on the check, save it, then set its channels."""
    update_fields = set()

    if spec.name is not None:
        check.name = spec.name
        update_fields.add("name")

    kind = spec.kind()
    if kind == "simple":
        check.kind = "simple"
        check.timeout = spec.timeout
        update_fields.update(("kind", "timeout"))

    if kind in ("cron", "oncalendar"):
        check.kind = kind
        assert spec.schedule is not None
        check.schedule = spec.schedule
        update_fields.update(("kind", "schedule"))

    # subject and subject_fail are deprecated, kept for compatibility with the original
    # Healthchecks API v3: map them to success_kw, failure_kw and filter_subject.
    if spec.subject is not None:
        check.success_kw = spec.subject
        check.filter_subject = bool(check.success_kw or check.failure_kw)
        update_fields.update(("success_kw", "filter_subject"))
    if spec.subject_fail is not None:
        check.failure_kw = spec.subject_fail
        check.filter_subject = bool(check.success_kw or check.failure_kw)
        update_fields.update(("failure_kw", "filter_subject"))

    for key in (
        "slug",
        "tags",
        "desc",
        "manual_resume",
        "methods",
        "tz",
        "start_kw",
        "success_kw",
        "failure_kw",
        "filter_subject",
        "filter_body",
        "filter_http_body",
        "filter_default_fail",
        "grace",
    ):
        v = getattr(spec, key)
        if v is not None:
            setattr(check, key, v)
            update_fields.add(key)

    check.alert_after = check.going_down_after()
    update_fields.add("alert_after")
    if check._state.adding:
        check.save()
    else:
        check.save(update_fields=update_fields)

    # This needs to be done after saving the check, because of
    # the M2M relation between checks and channels:
    if new_channels is not None:
        check.channel_set.set(new_channels)


@authorize_read
def get_checks(request: ApiRequest) -> JsonResponse:
    q = Check.objects.filter(project=request.project).order_by("created", "id")

    tags = set(request.GET.getlist("tag"))
    for tag in tags:
        # approximate filtering by tags
        q = q.filter(tags__contains=tag)

    if slug := request.GET.get("slug"):
        q = q.filter(slug=slug)

    # precise, final filtering
    checks = [check for check in q if not tags or check.matches_tag_set(tags)]
    if request.readonly:
        return JsonResponse({"checks": [check.to_dict(readonly=True) for check in checks]})

    # Codes from the link table, not channel_set: building Channel instances for them costs more
    codes: dict[int, list[UUID]] = {}
    links = Channel.checks.through.objects.filter(check__project=request.project)
    for check_id, code in links.values_list("check_id", "channel__code"):
        codes.setdefault(check_id, []).append(code)

    return JsonResponse({"checks": [check.to_dict(channel_codes=codes.get(check.id, [])) for check in checks]})


@authorize
def create_check(request: ApiRequest) -> HttpResponse:
    try:
        spec = Spec.model_validate(request.json, strict=True)
    except ValidationError as e:
        return JsonResponse({"error": format_first_error(e)}, status=400)

    created = False
    check = _lookup(request.project, spec)
    if check is None:
        check = Check(project=request.project)
        created = True

    try:
        _update(check, spec)
    except BadChannelError as e:
        return JsonResponse({"error": e.message}, status=400)

    return JsonResponse(check.to_dict(), status=201 if created else 200)


@csrf_exempt
@cors("GET", "POST")
def checks(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        return create_check(request)

    return get_checks(request)


@cors("GET")
@csrf_exempt
@authorize
def channels(request: ApiRequest) -> JsonResponse:
    q = Channel.objects.filter(project=request.project)
    channels = [ch.to_dict() for ch in q]
    return JsonResponse({"channels": channels})


@authorize_read
@_with_check
def get_check(request: ApiRequest, check: Check) -> HttpResponse:
    return JsonResponse(check.to_dict(readonly=request.readonly))


@cors("GET")
@csrf_exempt
@authorize_read
def get_check_by_unique_key(request: ApiRequest, unique_key: str) -> HttpResponse:
    check = find_by_unique_key(request.project.check_set.all(), unique_key)
    if check is None:
        return HttpResponseNotFound()

    return JsonResponse(check.to_dict(readonly=request.readonly))


@authorize
@_with_check
def update_check(request: ApiRequest, check: Check) -> HttpResponse:
    try:
        spec = Spec.model_validate(request.json, strict=True)
    except ValidationError as e:
        return JsonResponse({"error": format_first_error(e)}, status=400)

    try:
        _update(check, spec)
    except BadChannelError as e:
        return JsonResponse({"error": e.message}, status=400)

    return JsonResponse(check.to_dict())


@authorize
@_with_check
def delete_check(request: ApiRequest, check: Check) -> HttpResponse:
    check.rename_and_delete()
    return JsonResponse(check.to_dict())


@csrf_exempt
@cors("GET", "POST", "DELETE")
def single(request: HttpRequest, code: UUID) -> HttpResponse:
    if request.method == "POST":
        return update_check(request, code)

    if request.method == "DELETE":
        return delete_check(request, code)

    return get_check(request, code)


@cors("POST")
@csrf_exempt
@authorize
@_with_check
def pause(request: ApiRequest, check: Check) -> HttpResponse:
    check.pause()
    return JsonResponse(check.to_dict())


@cors("POST")
@csrf_exempt
@authorize
@_with_check
def resume(request: ApiRequest, check: Check) -> HttpResponse:
    if not check.resume():
        return HttpResponse("check is not paused", status=409)

    return JsonResponse(check.to_dict())


@cors("GET")
@csrf_exempt
@authorize
@_with_check
def pings(request: ApiRequest, check: Check) -> HttpResponse:
    # Look up ping log limit from account's profile.
    # There might be more pings in the database (depends on how pruning is handled)
    # but we will not return more than the limit allows.
    # Cap the number of returned pings to 1000.
    limit = min(request.project.owner_profile.ping_log_limit, 1000)

    # Query in descending order so we're sure to get the most recent
    # pings, regardless of the limit restriction. By "n", not "id": see Ping.Meta
    q = Ping.objects.filter(owner=check).order_by("-n")
    # Optimization: query just the length of body_raw instead of body_raw itself.
    q = q.defer("body_raw").annotate(body_raw_length=Length("body_raw"))
    pings = list(q[:limit])

    prepare_durations(pings)

    # Pass check's code to Ping.to_dict(), so it does not need to look it up
    # (which would result in a database query)
    ping_dicts = [p.to_dict(owner_code=check.code) for p in pings]
    return JsonResponse({"pings": ping_dicts})


@cors("GET")
@csrf_exempt
@authorize
@_with_check
def ping_body(request: ApiRequest, check: Check, n: int) -> HttpResponse:
    threshold = check.n_pings - request.project.owner_profile.ping_log_limit
    if n <= threshold:
        raise Http404()

    ping = get_object_or_404(Ping, owner=check, n=n)
    body = ping.get_body_bytes()
    if not body:
        raise Http404()

    return HttpResponse(body, content_type="text/plain")


def flips(request: ApiRequest, check: Check) -> HttpResponse:
    form = FlipsFiltersForm(request.GET)
    if not form.is_valid():
        return HttpResponseBadRequest()

    # api_flip_owner_created serves this order; sendalerts back-dates a down flip, so by id it would differ
    flips = Flip.objects.filter(owner=check).order_by("-created")

    if form.cleaned_data["start"]:
        flips = flips.filter(created__gte=form.cleaned_data["start"])

    if form.cleaned_data["end"]:
        flips = flips.filter(created__lt=form.cleaned_data["end"])

    if form.cleaned_data["seconds"]:
        threshold = now() - td(seconds=form.cleaned_data["seconds"])
        flips = flips.filter(created__gte=threshold)

    return JsonResponse({"flips": [flip.to_dict() for flip in flips]})


@cors("GET")
@csrf_exempt
@authorize_read
@_with_check
def flips_by_uuid(request: ApiRequest, check: Check) -> HttpResponse:
    return flips(request, check)


@cors("GET")
@csrf_exempt
@authorize_read
def flips_by_unique_key(request: ApiRequest, unique_key: str) -> HttpResponse:
    check = find_by_unique_key(request.project.check_set.all(), unique_key)
    if check is None:
        return HttpResponseNotFound()

    return flips(request, check)


@never_cache
def metrics(request: HttpRequest) -> HttpResponse:
    if not settings.METRICS_KEY:
        return HttpResponseForbidden()

    key = request.headers.get("X-Metrics-Key", "")
    if not hmac.compare_digest(key.encode(), settings.METRICS_KEY.encode()):
        return HttpResponseForbidden()

    doc = {
        "ts": int(time.time()),
        "max_ping_id": Ping.objects.values_list("id", flat=True).last(),
        "max_notification_id": Notification.objects.values_list("id", flat=True).last(),
        "num_unprocessed_flips": Flip.objects.filter(processed__isnull=True).count(),
    }

    return JsonResponse(doc)


@never_cache
def status(request: HttpRequest) -> HttpResponse:
    with connection.cursor() as c:
        c.execute("SELECT 1")
        c.fetchone()

    return HttpResponse("OK")


@csrf_exempt
@never_cache
def bounces(request: HttpRequest) -> HttpResponse:
    msg = message_from_bytes(request.body, policy=email.policy.SMTP)
    to_local = msg.get("To", "").split("@")[0]

    try:
        unsigned = unsign_bounce_id(to_local, max_age=3600 * 48)
    except BadSignature:
        # If the signature is invalid or expired return HTTP 200 so the other party
        # doesn't retry over and over again-
        return HttpResponse("OK (bad signature)")

    status, diagnostic = "", ""
    for part in msg.walk():
        if "Status" in part and "Action" in part:
            status = part["Status"]
            diagnostic = part.get("Diagnostic-Code", "")
            if diagnostic.lower().startswith("smtp; "):
                diagnostic = diagnostic[6:]
            break

    permanent = status.startswith("5.")
    transient = status.startswith("4.")
    # Special case 5.4.4 (unable to route, probably due to DNS issues) as transient
    if status == "5.4.4":
        permanent = False
        transient = True

    if not permanent and not transient:
        return HttpResponse("OK (ignored)")

    if unsigned.startswith("n."):
        notification_code = unsigned[2:]
        try:
            cutoff = now() - td(hours=48)
            n = Notification.objects.get(code=notification_code, created__gt=cutoff)
        except Notification.DoesNotExist:
            return HttpResponse("OK (notification not found)")

        reason = diagnostic or f"SMTP status code: {status}"
        error = f"Delivery failed ({reason})"[:200]

        n.error = error
        n.save(update_fields=["error"])

        channel_q = Channel.objects.filter(id=n.channel_id)
        channel_q.update(last_error=error)

        if permanent:
            channel_q.update(disabled=True)

    if unsigned.startswith("r.") and permanent:
        username = unsigned[2:]

        try:
            profile = Profile.objects.get(user__username=username)
        except Profile.DoesNotExist:
            return HttpResponse("OK (user not found)")

        profile.disable_reports()

    return HttpResponse("OK")
