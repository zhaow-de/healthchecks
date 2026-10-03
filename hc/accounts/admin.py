from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import ClassVar, TypedDict

from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.db.models import Count, F, Func, OuterRef, QuerySet, Subquery
from django.http import HttpRequest, HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.utils.html import format_html
from django.views.decorators.debug import sensitive_post_parameters
from django_stubs_ext import WithAnnotations

from hc.accounts.decorators import require_sudo_mode
from hc.accounts.models import Credential, Profile, Project
from hc.api.models import Check

Lookups = Iterable[tuple[str, str]]


def _format_usage(num_checks: int, num_channels: int) -> str:
    tmpl = ""

    if num_checks == 0:
        tmpl += "{} checks, "
    elif num_checks == 1:
        tmpl += "{} check, "
    else:
        tmpl += "<strong>{} checks</strong>, "

    if num_channels == 0:
        tmpl += "{} channels"
    elif num_channels == 1:
        tmpl += "{} channel"
    else:
        tmpl += "<strong>{} channels</strong>"

    return format_html(tmpl, num_checks, num_channels)


class NumChecksFilter(admin.SimpleListFilter):
    title = "check count"

    parameter_name = "num_checks"

    def lookups(self, r: HttpRequest, model_admin: ModelAdmin[Profile]) -> Lookups:
        return (
            ("10", "More than 10"),
            ("20", "More than 20"),
            ("50", "More than 50"),
            ("100", "More than 100"),
            ("500", "More than 500"),
            ("1000", "More than 1000"),
        )

    def queryset(
        self, r: HttpRequest, qs: QuerySet[WithAnnotations[Profile, ProfileAnnotations]]
    ) -> QuerySet[WithAnnotations[Profile, ProfileAnnotations]]:
        value = self.value()
        if value:
            qs = qs.filter(num_checks__gt=int(value))

        return qs


class ProfileAnnotations(TypedDict):
    num_checks: int


@admin.register(Profile)
class ProfileAdmin(ModelAdmin[Profile]):
    class Media:
        css: ClassVar = {"all": ("css/admin/profiles.css",)}

    readonly_fields = ("email",)
    search_fields = ("id", "user__email")
    list_per_page = 30
    list_select_related = ("user",)
    list_display = (
        "id",
        "email",
        "checks",
        "projects",
        "date_joined",
        "last_active",
        "reports",
    )
    list_filter = (
        NumChecksFilter,
        "last_active_date",
        "reports",
    )
    # No action that removes TOTP: that goes through the profile page, behind sudo mode
    actions = (
        "send_report",
        "send_nag",
    )

    _profile_fields = (
        "tz",
        "reports",
        "next_report_date",
        "nag_period",
        "next_nag_date",
        "token",
        "sort",
    )

    _limits_fields = ("ping_log_limit",)

    fieldsets = (
        ("User Profile", {"fields": _profile_fields}),
        ("Limits", {"fields": _limits_fields}),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Profile]:
        qs = super().get_queryset(request)
        qs = qs.prefetch_related("user__project_set")

        # Look up check count in a subquery.
        # Doing it using a join (`annotate(num_checks=Count(...))`)
        # would result in expensive joins when looking up the total number of
        # profile objects.
        #
        # Use Func() instead of Count() here because Count() would
        # also add a GROUP BY clause.
        subquery = (
            Check.objects.filter(project__owner=OuterRef("user_id")).annotate(count=Func("id", function="COUNT")).values("count")
        )
        qs = qs.annotate(num_checks=Subquery(subquery))

        return qs

    def email(self, obj: WithAnnotations[Profile, ProfileAnnotations]) -> str:
        return obj.user.email

    @admin.display(ordering="user__date_joined")
    def date_joined(self, obj: Profile) -> datetime:
        return obj.user.date_joined

    @admin.display(ordering="last_active_date")
    def last_active(self, obj: Profile) -> date | None:
        if obj.last_active_date:
            return obj.last_active_date.date()
        return None

    def projects(self, obj: Profile) -> str:
        return render_to_string("admin/profile_list_projects.html", {"profile": obj})

    def checks(self, obj: WithAnnotations[Profile, ProfileAnnotations]) -> str:
        tmpl = "{}"
        if obj.num_checks > 1:
            tmpl = "<b>{}</b>"
        return format_html(tmpl, obj.num_checks)

    def send_report(self, request: HttpRequest, qs: QuerySet[Profile]) -> None:
        for profile in qs:
            profile.send_report()

        self.message_user(request, f"{len(qs)} email(s) sent")

    def send_nag(self, request: HttpRequest, qs: QuerySet[Profile]) -> None:
        for profile in qs:
            profile.send_report(nag=True)

        self.message_user(request, f"{len(qs)} email(s) sent")


class ProjectAnnotations(TypedDict):
    num_checks: int
    num_channels: int


@admin.register(Project)
class ProjectAdmin(ModelAdmin[Project]):
    readonly_fields = ("code", "owner")
    list_select_related = ("owner",)
    list_display = ("id", "name_", "users", "usage", "switch")
    search_fields = ("id", "name", "owner__email", "code")

    def get_queryset(self, request: HttpRequest) -> QuerySet[Project]:
        qs = super().get_queryset(request)
        qs = qs.annotate(num_channels=Count("channel", distinct=True))
        qs = qs.annotate(num_checks=Count("check", distinct=True))
        return qs

    def name_(self, obj: Project) -> str:
        if obj.name:
            return obj.name

        return f"Default Project for {obj.owner.email}"

    def users(self, obj: Project) -> str:
        return obj.owner.email

    def usage(self, obj: WithAnnotations[Project, ProjectAnnotations]) -> str:
        return _format_usage(obj.num_checks, obj.num_channels)

    def switch(self, obj: Project) -> str:
        url = reverse("hc-checks", args=[obj.code])
        return format_html("<a href='{}'>Show Checks</a>", url)


class UserAnnotations(TypedDict):
    num_checks: int
    num_channels: int
    last_active_date: datetime | None


admin.site.unregister(User)


class OneUserPasswordChangeForm(AdminPasswordChangeForm):
    """The admin's password form without its switch that turns password log-in off."""

    def __init__(self, user: User, *args: object, **kwargs: object) -> None:
        super().__init__(user, *args, **kwargs)
        self.fields.pop("usable_password", None)


@admin.register(User)
class HcUserAdmin(UserAdmin[User]):
    list_display = (
        "id",
        "email",
        "usage",
        "date_joined",
        "last_login",
        "last_active",
        "is_staff",
    )

    list_display_links = ("id", "email")
    list_filter = ("last_login", "date_joined", "is_staff", "is_active")
    # Unticking a flag, blanking the email, which log-in goes by, or, without mail,
    # turning password log-in off would shut the one user out, and createsuperuser
    # refuses to make another user while it exists. The profile page changes the
    # email, by a mailed link.
    readonly_fields = ("email", "is_active", "is_staff", "is_superuser")
    change_password_form = OneUserPasswordChangeForm
    ordering = ("-id",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        # The instance has one user, created by the createsuperuser command
        return False

    @method_decorator(sensitive_post_parameters())
    @method_decorator(require_sudo_mode)
    def user_change_password(self, request: HttpRequest, id: str, form_url: str = "") -> HttpResponse:
        return super().user_change_password(request, id, form_url)

    def get_queryset(self, request: HttpRequest) -> QuerySet[User]:
        qs = super().get_queryset(request)
        qs = qs.annotate(num_checks=Count("project__check", distinct=True))
        qs = qs.annotate(num_channels=Count("project__channel", distinct=True))
        qs = qs.annotate(last_active_date=F("profile__last_active_date"))

        return qs

    def last_active(self, user: WithAnnotations[User, UserAnnotations]) -> datetime | None:
        return user.last_active_date

    def usage(self, user: WithAnnotations[User, UserAnnotations]) -> str:
        return _format_usage(user.num_checks, user.num_channels)


@admin.register(Credential)
class CredentialAdmin(ModelAdmin[Credential]):
    list_display = ("id", "created", "email", "name")
    search_fields = ("id", "code", "name", "user__email")
    list_filter = ("created",)
    readonly_fields = ("user",)

    def has_delete_permission(self, request: HttpRequest, obj: Credential | None = None) -> bool:
        # A security key is removed on the profile page, behind sudo mode
        return False

    def email(self, obj: Credential) -> str:
        return obj.user.email
