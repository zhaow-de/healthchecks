from __future__ import annotations

import logging
import time
from datetime import timedelta as td
from secrets import token_urlsafe
from urllib.parse import urlparse
from uuid import UUID

import pyotp
import segno
from django.conf import settings
from django.contrib.auth import authenticate, update_session_auth_hash
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core.signing import BadSignature, SignatureExpired, TimestampSigner
from django.db.models.functions import Lower
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import Resolver404, resolve, reverse
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_POST

from hc.accounts import device, forms
from hc.accounts.decorators import require_sudo_mode
from hc.accounts.http import AuthenticatedHttpRequest
from hc.accounts.models import Credential, Profile, Project
from hc.api.models import TokenBucket
from hc.lib.tz import all_timezones
from hc.lib.webauthn import CreateHelper, GetHelper

logger = logging.getLogger(__name__)

POST_LOGIN_ROUTES = (
    "hc-checks",
    "hc-details",
    "hc-log",
    "hc-channels",
    "hc-add-slack",
    "hc-project-settings",
    "hc-uncloak",
)


def _allow_redirect(redirect_url: str | None) -> bool:
    if not redirect_url:
        return False

    parsed = urlparse(redirect_url)
    if parsed.netloc:
        # Allow redirects only to relative URLs
        return False

    try:
        match = resolve(parsed.path)
    except Resolver404:
        return False

    return match.url_name in POST_LOGIN_ROUTES


def _redirect_after_login(request: HttpRequest) -> HttpResponse:
    """Redirect to the URL indicated in ?next= query parameter."""

    redirect_url = request.GET.get("next")
    if redirect_url and _allow_redirect(redirect_url):
        return redirect(redirect_url)

    assert isinstance(request.user, User)
    if request.user.project_set.count() == 1:
        project = request.user.project_set.get()
        return redirect("hc-checks", project.code)

    return redirect("hc-index")


def _check_2fa(request: HttpRequest, user: User) -> HttpResponse:
    have_keys = user.credentials.exists()
    profile = Profile.objects.for_user(user)
    if have_keys or profile.totp:
        # We have verified user's password or token, and now must
        # verify their security key. We store the following in user's session:
        # - user.id, to look up the user in the login_webauthn view
        # - user.email, to make sure email was not changed between the auth steps
        # - timestamp, to limit the max time between the auth steps
        request.session["2fa_user"] = [user.id, user.email, int(time.time())]

        query = {}
        if _allow_redirect(request.GET.get("next")):
            query["next"] = request.GET["next"]

        route = "hc-login-webauthn" if have_keys else "hc-login-totp"
        path = reverse(route, query=query)
        return redirect(path)

    return _complete_login(request, user)


def _complete_login(request: HttpRequest, user: User, backend: str | None = None) -> HttpResponse:
    """Log the user in once every step the login requires is done."""
    auth_login(request, user, backend)
    response = _redirect_after_login(request)
    device.issue(request, response, user)
    return response


def _set_autologin_cookie(response: HttpResponse) -> None:
    # check_token looks for this cookie to decide if
    # it needs to do the extra POST step.
    response.set_cookie(
        "auto-login",
        "1",
        max_age=300,
        httponly=True,
        samesite="Lax",
        secure=bool(settings.SESSION_COOKIE_SECURE),
    )


@sensitive_post_parameters()
def login(request: HttpRequest) -> HttpResponse:
    form = forms.PasswordLoginForm()
    magic_form = forms.EmailLoginForm()
    if request.method == "POST":
        if request.POST.get("action") == "login":
            form = forms.PasswordLoginForm(request)
            if form.is_valid():
                assert isinstance(form.user, User)
                return _check_2fa(request, form.user)

        else:
            magic_form = forms.EmailLoginForm(request)
            if magic_form.is_valid():
                redirect_url = request.GET.get("next")
                if not _allow_redirect(redirect_url):
                    redirect_url = None

                # Every email gets the same redirect. Without MAILERS the form
                # is hidden, but a crafted POST still arrives and sends nothing.
                if settings.MAILERS and magic_form.user:
                    profile = Profile.objects.for_user(magic_form.user)
                    profile.send_instant_login_link(redirect_url=redirect_url)
                elif settings.MAILERS:
                    # Hash a throwaway token as prepare_token() hashes the
                    # owner's, so the response time does not tell which email
                    # exists.
                    make_password(token_urlsafe(24))

                response = redirect("hc-login-link-sent")
                _set_autologin_cookie(response)
                return response

    if request.user.is_authenticated:
        return _redirect_after_login(request)

    bad_link = request.session.pop("bad_link", None)
    ctx = {
        "page": "login",
        "form": form,
        "magic_form": magic_form,
        "bad_link": bad_link,
        "support_email": settings.SUPPORT_EMAIL,
        "account_closed": "account-closed" in request.GET,
        "use_magic_form": bool(settings.MAILERS),
    }
    return render(request, "accounts/login.html", ctx)


@require_POST
def logout(request: HttpRequest) -> HttpResponse:
    auth_logout(request)
    return redirect("hc-index")


def login_link_sent(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/login_link_sent.html")


def check_token(request: HttpRequest, username: str, token: str, new_email: str | None = None) -> HttpResponse:
    if request.user.is_authenticated:
        auth_logout(request)

    # Some email servers open links in emails to check for malicious content.
    # To work around this, we sign user in if the method is POST
    # *or* if the browser presents a cookie we had set when sending the login link.
    #
    # If the method is GET and the auto-login cookie isn't present, we serve
    # an HTML form with a submit button.
    if request.method != "POST" and "auto-login" not in request.COOKIES:
        return render(request, "accounts/check_token_submit.html")

    user = authenticate(username=username, token=token)
    if user is not None and user.is_active:
        if new_email:
            if User.objects.filter(email=new_email).exists():
                request.session["bad_link"] = True
                return redirect("hc-login")

            user.email = new_email
            user.save()

        user.profile.token = ""
        user.profile.save()
        return _check_2fa(request, user)

    request.session["bad_link"] = True
    return redirect("hc-login")


@login_required
def profile(request: AuthenticatedHttpRequest) -> HttpResponse:
    profile = request.profile

    ctx = {
        "page": "profile",
        "profile": profile,
        "2fa_status": "default",
        "tz_status": "default",
        "added_credential_name": request.session.pop("added_credential_name", ""),
        "removed_credential_name": request.session.pop("removed_credential_name", ""),
        "enabled_totp": request.session.pop("enabled_totp", False),
        "disabled_totp": request.session.pop("disabled_totp", False),
        "credentials": list(request.user.credentials.order_by("id")),
        "use_webauthn": settings.RP_ID,
        "timezones": all_timezones,
    }

    if ctx["added_credential_name"] or ctx["enabled_totp"]:
        ctx["2fa_status"] = "success"

    if ctx["removed_credential_name"] or ctx["disabled_totp"]:
        ctx["2fa_status"] = "info"

    if request.session.pop("changed_password", False):
        ctx["changed_password"] = True
        ctx["email_password_status"] = "success"

    if request.method == "POST" and "tz" in request.POST:
        form = forms.TzForm(request.POST)
        if form.is_valid():
            profile.tz = form.cleaned_data["tz"]
            profile.save()
            ctx["tz_status"] = "info"
            ctx["tz_updated"] = True

    ctx["ownerships"] = request.user.project_set.order_by(Lower("name"))
    return render(request, "accounts/profile.html", ctx)


@login_required
@require_POST
def add_project(request: AuthenticatedHttpRequest) -> HttpResponse:
    form = forms.ProjectNameForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest("The project name is required and can be at most 60 characters long.")

    project = Project(owner=request.user)
    project.name = form.cleaned_data["name"]
    project.save()

    return redirect("hc-checks", project.code)


@login_required
def project(request: AuthenticatedHttpRequest, code: UUID) -> HttpResponse:
    project = get_object_or_404(Project, code=code, owner=request.user)
    ctx = {"page": "project", "project": project}

    if request.method == "POST":
        if "create_key" in request.POST:
            if request.POST["create_key"] == "api_key":
                ctx["new_key"] = project.set_api_key()
            elif request.POST["create_key"] == "api_key_readonly":
                ctx["new_key"] = project.set_api_key_readonly()
            elif request.POST["create_key"] == "ping_key":
                ctx["new_ping_key"] = project.set_ping_key()
            project.save()

            ctx["key_created"] = True
            ctx["api_status"] = "success"
        elif "revoke_key" in request.POST:
            if request.POST["revoke_key"] == "api_key":
                project.api_key = ""
            elif request.POST["revoke_key"] == "api_key_readonly":
                project.api_key_readonly = ""
            elif request.POST["revoke_key"] == "ping_key":
                project.ping_key = None
            project.save()

            ctx["key_revoked"] = True
            ctx["api_status"] = "info"
        elif "set_project_name" in request.POST:
            name_form = forms.ProjectNameForm(request.POST)
            if name_form.is_valid():
                project.name = name_form.cleaned_data["name"]
                project.save()

                ctx["project_name_updated"] = True
                ctx["project_name_status"] = "success"

    return render(request, "accounts/project.html", ctx)


@login_required
def notifications(request: AuthenticatedHttpRequest) -> HttpResponse:
    profile = request.profile

    ctx = {
        "status": "default",
        "page": "profile",
        "profile": profile,
    }

    if request.method == "POST":
        form = forms.ReportSettingsForm(request.POST)
        if form.is_valid():
            profile.reports = form.cleaned_data["reports"]
            profile.next_report_date = profile.choose_next_report_date()

            if profile.nag_period != form.cleaned_data["nag_period"]:
                # Set the new nag period
                profile.nag_period = form.cleaned_data["nag_period"]
                # and update next_nag_date:
                if profile.nag_period:
                    profile.update_next_nag_date()
                else:
                    profile.next_nag_date = None

            profile.save()
            ctx["status"] = "info"

    return render(request, "accounts/notifications.html", ctx)


@login_required
@sensitive_post_parameters()
@require_sudo_mode
def set_password(request: AuthenticatedHttpRequest) -> HttpResponse:
    form = forms.SetPasswordForm(request.user)
    if request.method == "POST":
        form = forms.SetPasswordForm(request.user, request.POST)
        if form.is_valid():
            password = form.cleaned_data["password"]
            request.user.set_password(password)
            request.user.save()

            request.profile.token = ""
            request.profile.save()

            # update the session with the new password hash so that
            # the user doesn't  get logged out
            update_session_auth_hash(request, request.user)

            request.session["changed_password"] = True
            return redirect("hc-profile")

    return render(request, "accounts/set_password.html", {"form": form})


@login_required
@require_sudo_mode
def change_email(request: AuthenticatedHttpRequest) -> HttpResponse:
    if "sent" in request.session:
        ctx = {"email": request.session.pop("sent")}
        return render(request, "accounts/change_email_instructions.html", ctx)

    if request.method == "POST":
        form = forms.ChangeEmailForm(request.POST)
        if form.is_valid():
            # The user has entered a valid-looking new email address.
            # Send a special login link to the new address. When the user
            # clicks the special login link, hc.accounts.views.change_email_verify
            # unpacks the payload, and passes it to hc.accounts.views.check_token,
            # which finally updates user's email address.
            email = form.cleaned_data["email"]
            request.profile.send_change_email_link(email)
            request.session["sent"] = email

            response = redirect(reverse("hc-change-email"))
            # check_token looks for this cookie to decide if
            # it needs to do the extra POST step.
            _set_autologin_cookie(response)
            return response
    else:
        form = forms.ChangeEmailForm()

    return render(request, "accounts/change_email.html", {"form": form})


def change_email_verify(request: HttpRequest, signed_payload: str) -> HttpResponse:
    try:
        payload = TimestampSigner().unsign_object(signed_payload, max_age=900)
    except BadSignature:
        return render(request, "bad_link.html")

    return check_token(request, payload["u"], payload["t"], payload["e"])


@csrf_exempt
def unsubscribe_reports(request: HttpRequest, signed_username: str) -> HttpResponse:
    # Some email servers open links in emails to check for malicious content.
    # To work around this, for GET requests we serve a confirmation form.
    # If the signature is more than 5 minutes old, we also include JS code to
    # auto-submit the form.

    signer = TimestampSigner(salt="reports")
    # First, check the signature without looking at the timestamp:
    try:
        username = signer.unsign(signed_username)
    except BadSignature:
        return render(request, "bad_link.html")

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        # This is likely an old unsubscribe link, and the user account has already
        # been deleted. Show the "Unsubscribed!" page nevertheless.
        return render(request, "accounts/unsubscribed.html")

    if request.method != "POST":
        # Unsign again, now with max_age set,
        # to see if the timestamp is older than 5 minutes
        try:
            autosubmit = False
            username = signer.unsign(signed_username, max_age=300)
        except SignatureExpired:
            autosubmit = True

        ctx = {"autosubmit": autosubmit}
        return render(request, "accounts/unsubscribe_submit.html", ctx)

    profile = Profile.objects.for_user(user)
    profile.reports = "off"
    profile.next_report_date = None
    profile.nag_period = td()
    profile.next_nag_date = None
    profile.save()

    return render(request, "accounts/unsubscribed.html")


@login_required
@require_sudo_mode
def close(request: AuthenticatedHttpRequest) -> HttpResponse:
    user = request.user

    if request.method == "POST" and request.POST.get("confirmation") == request.user.email:
        # Deleting user also deletes its profile, checks, channels etc.
        user.delete()

        request.session.flush()
        path = reverse("hc-login", query={"account-closed": 1})
        return redirect(path)

    ctx = {}
    if "confirmation" in request.POST:
        ctx["wrong_confirmation"] = True

    return render(request, "accounts/close_account.html", ctx)


@require_POST
@login_required
def remove_project(request: AuthenticatedHttpRequest, code: str) -> HttpResponse:
    project = get_object_or_404(Project, code=code, owner=request.user)
    for check in project.check_set.all():
        check.rename_and_delete()
    project.delete()
    return redirect("hc-index")


@login_required
@require_sudo_mode
def add_webauthn(request: AuthenticatedHttpRequest) -> HttpResponse:
    if not settings.RP_ID:
        return HttpResponse(status=404)

    q = request.user.credentials.values_list("data", flat=True)
    # CreateHelper wants list[bytes] so normalize to that
    credentials = [bytes(item) for item in q]
    helper = CreateHelper(settings.RP_ID, credentials)

    if request.method == "POST":
        form = forms.AddWebAuthnForm(request.POST)
        if not form.is_valid():
            return HttpResponseBadRequest()

        state = request.session["state"]
        try:
            credential_bytes = helper.verify(state, form.cleaned_data["response"])
        except ValueError:
            logger.exception("CreateHelper.verify failed, form: %s", form.cleaned_data)
            return HttpResponseBadRequest()

        c = Credential(user=request.user)
        c.name = form.cleaned_data["name"]
        c.data = credential_bytes
        c.save()

        request.session.pop("state")
        request.session["added_credential_name"] = c.name
        return redirect("hc-profile")

    options, request.session["state"] = helper.prepare(request.user.email)
    return render(request, "accounts/add_credential.html", {"options": options})


@login_required
@require_sudo_mode
def add_totp(request: AuthenticatedHttpRequest) -> HttpResponse:
    if request.profile.totp:
        # TOTP is already configured, refuse to continue
        return HttpResponseBadRequest()

    if "totp_secret" not in request.session:
        request.session["totp_secret"] = pyotp.random_base32()

    totp = pyotp.totp.TOTP(request.session["totp_secret"])

    if request.method == "POST":
        form = forms.TotpForm(totp, request.POST)
        if form.is_valid():
            request.profile.totp = request.session["totp_secret"]
            request.profile.totp_created = now()
            request.profile.save()

            request.session["enabled_totp"] = True
            request.session.pop("totp_secret")
            return redirect("hc-profile")
    else:
        form = forms.TotpForm(totp)

    uri = totp.provisioning_uri(name=request.user.email, issuer_name=settings.SITE_NAME)
    qr_data_uri = segno.make(uri).png_data_uri(scale=8)
    ctx = {
        "form": form,
        "qr_data_uri": qr_data_uri,
        "secret": request.session["totp_secret"],
    }
    return render(request, "accounts/add_totp.html", ctx)


@login_required
@require_sudo_mode
def remove_totp(request: AuthenticatedHttpRequest) -> HttpResponse:
    if request.method == "POST" and "disable_totp" in request.POST:
        request.profile.totp = ""
        request.profile.totp_created = None
        request.profile.save()
        request.session["disabled_totp"] = True
        return redirect("hc-profile")

    ctx = {"is_last": not request.user.credentials.exists()}
    return render(request, "accounts/remove_totp.html", ctx)


@login_required
@require_sudo_mode
def remove_credential(request: AuthenticatedHttpRequest, code: str) -> HttpResponse:
    if not settings.RP_ID:
        return HttpResponse(status=404)

    try:
        credential = Credential.objects.get(user=request.user, code=code)
    except Credential.DoesNotExist:
        return HttpResponseBadRequest()

    if request.method == "POST" and "remove_credential" in request.POST:
        request.session["removed_credential_name"] = credential.name
        credential.delete()
        return redirect("hc-profile")

    is_last = not request.profile.totp and request.user.credentials.count() == 1

    ctx = {"credential": credential, "is_last": is_last}
    return render(request, "accounts/remove_credential.html", ctx)


def login_webauthn(request: HttpRequest) -> HttpResponse:
    # We require RP_ID. Fail predicably if it is not set:
    if not settings.RP_ID:
        return HttpResponse(status=404)

    # Expect an unauthenticated user
    if request.user.is_authenticated:
        return HttpResponseBadRequest()

    if "2fa_user" not in request.session:
        return HttpResponseBadRequest()

    user_id, email, timestamp = request.session["2fa_user"]
    if timestamp + 300 < time.time():
        return redirect("hc-login")

    try:
        user = User.objects.get(id=user_id, email=email)
    except User.DoesNotExist:
        return HttpResponseBadRequest()

    q = user.credentials.values_list("data", flat=True)
    # GetHelper wants list[bytes] so normalize to that
    credentials = [bytes(item) for item in q]
    helper = GetHelper(settings.RP_ID, credentials)

    if request.method == "POST":
        form = forms.WebAuthnForm(request.POST)
        if not form.is_valid():
            return HttpResponseBadRequest()

        if not helper.verify(request.session["state"], form.cleaned_data["response"]):
            return HttpResponseBadRequest()

        request.session.pop("state")
        request.session.pop("2fa_user")
        return _complete_login(request, user, "hc.accounts.backends.EmailBackend")

    options, request.session["state"] = helper.prepare()

    totp_url = None
    if user.profile.totp:
        query = {}
        if _allow_redirect(request.GET.get("next")):
            query["next"] = request.GET["next"]
        totp_url = reverse("hc-login-totp", query=query)

    ctx = {
        "options": options,
        "totp_url": totp_url,
    }
    return render(request, "accounts/login_webauthn.html", ctx)


def login_totp(request: HttpRequest) -> HttpResponse:
    # Expect an unauthenticated user
    if request.user.is_authenticated:
        return HttpResponseBadRequest()

    if "2fa_user" not in request.session:
        return HttpResponseBadRequest()

    user_id, email, timestamp = request.session["2fa_user"]
    if timestamp + 300 < time.time():
        return redirect("hc-login")

    try:
        user = User.objects.get(id=user_id, email=email)
    except User.DoesNotExist:
        return HttpResponseBadRequest()

    if not user.profile.totp:
        return HttpResponseBadRequest()

    totp = pyotp.totp.TOTP(user.profile.totp)
    if request.method == "POST":
        # To guard against brute-forcing TOTP codes, we allow
        # 96 attempts per user per 24h.
        if not TokenBucket.authorize_totp_attempt(user):
            return render(request, "try_later.html")

        form = forms.TotpForm(totp, request.POST)
        if form.is_valid():
            # We blacklist a used TOTP code for 90 seconds,
            # so an attacker cannot reuse a stolen code.
            if not TokenBucket.authorize_totp_code(user, form.cleaned_data["code"]):
                return render(request, "try_later.html")

            request.session.pop("2fa_user")
            return _complete_login(request, user, "hc.accounts.backends.EmailBackend")
    else:
        form = forms.TotpForm(totp)

    return render(request, "accounts/login_totp.html", {"form": form})
