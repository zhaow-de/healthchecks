import hmac
import random
import uuid
from datetime import datetime
from datetime import timedelta as td
from secrets import token_urlsafe
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.core.signing import BadSignature, TimestampSigner
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import QuerySet
from django.db.models.functions import Lower
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import now

from hc.lib import emails
from hc.lib.date import day_boundaries, month_boundaries, week_boundaries
from hc.lib.signing import sign_bounce_id
from hc.lib.urls import absolute_reverse

if TYPE_CHECKING:
    # Importing Check at runtime would cause a circular import, so only import it
    # during type checking
    from hc.api.models import Check


NO_NAG = td()
NAG_PERIODS = (
    (NO_NAG, "Disabled"),
    (td(hours=1), "Hourly"),
    (td(days=1), "Daily"),
)

REPORT_CHOICES = (
    ("off", "Off"),
    ("daily", "Daily"),
    ("weekly", "Weekly"),
    ("monthly", "Monthly"),
)


class ProfileManager(models.Manager["Profile"]):
    def for_user(self, user: User) -> Profile:
        try:
            return user.profile
        except Profile.DoesNotExist:
            profile = Profile(user=user)
            profile.save()
            return profile


class Profile(models.Model):
    user = models.OneToOneField(User, models.CASCADE)
    next_report_date = models.DateTimeField(null=True, blank=True)
    reports = models.CharField(max_length=10, default="monthly", choices=REPORT_CHOICES)
    nag_period = models.DurationField(default=NO_NAG, choices=NAG_PERIODS)
    next_nag_date = models.DateTimeField(null=True, blank=True)
    # At 0, Check.prune keeps no ping and then never prunes the check's flips
    # and notifications. The cap bounds a check's pings (the limit + 99).
    ping_log_limit = models.IntegerField(default=100, validators=[MinValueValidator(1), MaxValueValidator(1000)])
    token = models.CharField(max_length=128, blank=True)

    sort = models.CharField(max_length=20, default="created")
    last_active_date = models.DateTimeField(null=True, blank=True)
    tz = models.CharField(max_length=36, default="UTC")

    totp = models.CharField(max_length=32, blank=True, default="")
    totp_created = models.DateTimeField(null=True, blank=True)

    objects = ProfileManager()

    def __str__(self) -> str:
        return f"Profile for {self.user.email}"

    def notifications_url(self) -> str:
        return absolute_reverse("hc-notifications")

    def reports_unsub_url(self) -> str:
        signer = TimestampSigner(salt="reports")
        signed_username = signer.sign(self.user.username)
        return absolute_reverse("hc-unsubscribe-reports", args=[signed_username])

    def prepare_token(self) -> str:
        token = token_urlsafe(24)
        # Store a hashed transformation of the login token
        self.token = make_password(token)
        self.save(update_fields=["token"])
        # Sign the token so we can check its age later
        return TimestampSigner().sign(token)

    def check_token(self, token: str) -> bool:
        try:
            token = TimestampSigner().unsign(token, max_age=3600)
        except BadSignature:
            return False

        return check_password(token, self.token)

    def send_instant_login_link(self, redirect_url: str | None = None) -> None:
        token = self.prepare_token()
        query = {"next": redirect_url} if redirect_url else None
        url = absolute_reverse("hc-check-token", args=[self.user.username, token], query=query)

        ctx = {
            "button_text": "Log In",
            "button_url": url,
        }
        emails.login(self.user.email, ctx)

    def send_change_email_link(self, new_email: str) -> None:
        payload = {
            "u": self.user.username,
            "t": self.prepare_token(),
            "e": new_email,
        }
        signed_payload = TimestampSigner().sign_object(payload)
        url = absolute_reverse("hc-change-email-verify", args=[signed_payload])

        ctx = {
            "button_text": "Log In",
            "button_url": url,
        }
        emails.login(new_email, ctx)

    def projects(self) -> QuerySet[Project]:
        return Project.objects.filter(owner_id=self.user_id).order_by(Lower("name"))

    def checks_from_all_projects(self) -> QuerySet[Check]:
        from hc.api.models import Check

        return Check.objects.filter(project__owner_id=self.user_id)

    def send_report(self, nag: bool = False) -> bool:
        if not settings.MAILERS:
            return False

        q = self.checks_from_all_projects()

        # Has there been a ping in last 6 months?
        result = q.aggregate(models.Max("last_ping"))
        last_ping = result["last_ping__max"]

        six_months_ago = now() - td(days=180)
        if last_ping is None or last_ping < six_months_ago:
            return False

        # Sort checks by project. Need this because will group by project in template.
        # Sort primarily by project name, but projects can have duplicate names
        # so sort by project id also.
        # Checks in each project will be sorted by check name in the template,
        # after grouping.
        q = q.select_related("project").order_by("project__name", "project_id")
        # list() executes the query, to avoid DB access while rendering the template.
        checks = list(q)

        unsub_url = self.reports_unsub_url()
        headers = {
            "X-Bounce-ID": sign_bounce_id(f"r.{self.user.username}"),
            "List-Unsubscribe": f"<{unsub_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
        ctx: dict[str, Any] = {
            "unsub_link": unsub_url,
            "notifications_url": self.notifications_url(),
            "tz": self.tz,
        }

        if not nag:
            # For monthly/weekly/daily reports, calculate the downtimes,
            # throw away the current period, keep two previous periods
            if self.reports == "monthly":
                boundaries = month_boundaries(3, self.tz)
            elif self.reports == "weekly":
                boundaries = week_boundaries(3, self.tz)
            elif self.reports == "daily":
                boundaries = day_boundaries(3, self.tz)
            else:
                assert 0, f"Unexpected Profile.reports value: {self.reports}"

            ctx["summary_nchecks"] = 0
            ctx["summary_ntimes"] = 0
            for check in checks:
                downtimes = check.downtimes_by_boundary(boundaries, self.tz)
                # downtimes_by_boundary returns records in descending order,
                # but the template will need them in ascending order:
                downtimes.reverse()
                check.past_downtimes = downtimes[:-1]
                if count := check.past_downtimes[-1].count:
                    ctx["summary_nchecks"] += 1
                    ctx["summary_ntimes"] += count

            # boundaries are in descending order, but the template
            # will need them in ascending order:
            boundaries.reverse()
            ctx["checks"] = checks
            ctx["boundaries"] = boundaries[:-1]
            ctx["report_period"] = self.reports

            # Prepare the "In January" / "Last week (...)" / "Yesterday (...)" bit:
            when_ctx = {
                "boundary": ctx["boundaries"][-1],
                "report_period": self.reports,
                "tz": self.tz,
            }
            ctx["when"] = render_to_string("emails/report-when.html", when_ctx).strip()

            emails.report(self.user.email, ctx, headers)

        if nag:
            # For nags, only show checks that are currently down
            checks = [c for c in checks if c.get_status() == "down"]
            if not checks:
                return False
            ctx["checks"] = checks
            ctx["num_down"] = len(checks)
            ctx["nag_period"] = self.nag_period.total_seconds()
            emails.nag(self.user.email, ctx, headers)

        return True

    def num_checks_used(self) -> int:
        from hc.api.models import Check

        return Check.objects.filter(project__owner_id=self.user_id).count()

    def disable_reports(self) -> None:
        """Turn reports and nags off, as an unsubscribe link or a bounced report asks."""
        self.reports = "off"
        self.next_report_date = None
        self.nag_period = NO_NAG
        self.next_nag_date = None
        self.save(update_fields=["reports", "next_report_date", "nag_period", "next_nag_date"])

    def update_next_nag_date(self) -> None:
        any_down = self.checks_from_all_projects().filter(status="down").exists()
        if any_down and self.next_nag_date is None and self.nag_period:
            self.next_nag_date = now() + self.nag_period
            self.save(update_fields=["next_nag_date"])
        elif not any_down and self.next_nag_date:
            self.next_nag_date = None
            self.save(update_fields=["next_nag_date"])

    def choose_next_report_date(self) -> datetime | None:
        """Calculate the target date for the next monthly/weekly report.

        Monthly reports should get sent on 1st of each month, between
        9AM and 11AM in user's timezone.

        Weekly reports should get sent on Mondays, between
        9AM and 11AM in user's timezone.

        """

        if self.reports == "off":
            return None

        dt = now().astimezone(ZoneInfo(self.tz))
        dt = dt.replace(hour=9, minute=0) + td(minutes=random.randrange(0, 120))

        while True:
            dt += td(days=1)
            if self.reports == "daily":
                return dt
            if self.reports == "monthly" and dt.day == 1:
                return dt
            if self.reports == "weekly" and dt.weekday() == 0:
                return dt


class ProjectManager(models.Manager["Project"]):
    def for_api_key(self, api_key: str, accept_rw: bool, accept_ro: bool) -> Project | None:
        """Look up project by API key.

        It looks up projects by the first 8 characters of the random part of the key,
        then calls Project.compare_api_key().
        """

        # The owner and the profile come along, so owner_profile costs no query
        q = Project.objects.select_related("owner__profile")
        if accept_rw and api_key.startswith("hcw_"):
            q = q.filter(api_key__startswith=api_key[4:12])
        elif accept_ro and api_key.startswith("hcr_"):
            q = q.filter(api_key_readonly__startswith=api_key[4:12])
        else:
            return None

        return next((project for project in q if project.compare_api_key(api_key)), None)


class Project(models.Model):
    code = models.UUIDField(default=uuid.uuid4, unique=True)
    name = models.CharField(max_length=200, blank=True)
    owner = models.ForeignKey(User, models.CASCADE)
    api_key = models.CharField(max_length=128, blank=True, db_index=True)
    api_key_readonly = models.CharField(max_length=128, blank=True, db_index=True)
    ping_key = models.CharField(max_length=128, blank=True, null=True, unique=True)
    show_slugs = models.BooleanField(default=False)

    objects = ProjectManager()
    # used in hc.front.views to cache the aggregate status of all checks in the project
    overall_status: str
    any_started: bool

    def __str__(self) -> str:
        return self.name or self.owner.email

    def get_absolute_url(self) -> str:
        return reverse("hc-checks", args=[self.code])

    @property
    def owner_profile(self) -> Profile:
        return Profile.objects.for_user(self.owner)

    def update_next_nag_dates(self) -> None:
        """Update next_nag_date on the owner's profile."""

        q = Profile.objects.filter(user_id=self.owner_id).exclude(nag_period=NO_NAG)
        for profile in q:
            profile.update_next_nag_date()

    def get_n_down(self) -> int:
        result = 0
        for check in self.check_set.all():
            if check.get_status() == "down":
                result += 1

        return result

    def have_channel_issues(self) -> bool:
        errors = list(self.channel_set.values_list("last_error", flat=True))

        # It's a problem if a project has no integrations at all
        if len(errors) == 0:
            return True

        # It's a problem if any integration has a logged error
        return any(errors)

    def checks_url(self) -> str:
        return absolute_reverse("hc-checks", args=[self.code])

    def auth_metrics_url(self) -> str:
        return absolute_reverse("hc-auth-metrics", args=[self.code])

    def _make_api_key(self, prefix: str) -> tuple[str, str]:
        """Generate an API key with specified prefix, return (key, key_hash) tuple.

        * `key` is what will be presented to the user,
        * `key_hash` will be stored in the database.

        `key_hash` consists of two parts:
        * first 8 characters: the first 8 characters of plain text key
          (for efficiently looking up project in the database by its API key)
        * next 64 characters: HMAC(SECRET_KEY, key)
        """
        while True:
            secret = token_urlsafe(21)
            if "-" not in secret and "_" not in secret:
                break

        key = f"{prefix}{secret}"
        digest = hmac.digest(settings.SECRET_KEY.encode(), key.encode(), "sha256")
        return key, secret[:8] + "." + digest.hex()

    def set_api_key(self) -> str:
        key, key_hash = self._make_api_key("hcw_")
        self.api_key = key_hash
        return key

    def set_api_key_readonly(self) -> str:
        key, key_hash = self._make_api_key("hcr_")
        self.api_key_readonly = key_hash
        return key

    def set_ping_key(self) -> str:
        # The ping key will be:
        # - 22 characters long, consisting of [a-z0-9]
        # - no "_" or "-" characters for aesthetic reasons
        # - no uppercase characters to avoid case-sensitivity issues
        # The ping key will have ~113 bits of entropy.
        while True:
            self.ping_key = token_urlsafe(16).lower()
            if "_" not in self.ping_key and "-" not in self.ping_key:
                break
        return self.ping_key

    def compare_api_key(self, key: str) -> bool:
        expected = self.api_key_readonly if key.startswith("hcr_") else self.api_key

        # Only calculate and compare digest if db key length is 8 + 64 = 72
        if "." not in expected:
            return False
        _, key_hash = expected.split(".", maxsplit=1)

        digest = hmac.digest(settings.SECRET_KEY.encode(), key.encode(), "sha256")
        return hmac.compare_digest(digest.hex(), key_hash)


class Credential(models.Model):
    code = models.UUIDField(default=uuid.uuid4, unique=True)
    name = models.CharField(max_length=100)
    user = models.ForeignKey(User, models.CASCADE, related_name="credentials")
    created = models.DateTimeField(auto_now_add=True)
    data = models.BinaryField()

    def __str__(self) -> str:
        return self.name
