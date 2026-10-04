from typing import override

from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.contrib.auth.models import User
from django.http import HttpRequest, HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters

from hc.accounts.decorators import require_sudo_mode
from hc.accounts.models import Credential, Profile, Project


@admin.register(Profile)
class ProfileAdmin(ModelAdmin[Profile]):
    list_display = ("id", "user__email", "reports", "last_active_date")
    # No TOTP fields: the second factor changes on the profile page, behind sudo mode
    fields = (
        "tz",
        "reports",
        "next_report_date",
        "nag_period",
        "next_nag_date",
        "token",
        "sort",
        "ping_log_limit",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Profile.objects.for_user creates the one user's profile
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Profile | None = None) -> bool:
        # Profile.objects.for_user recreates a deleted profile without TOTP, so a
        # delete here would turn the second factor off outside sudo mode
        return False


@admin.register(Project)
class ProjectAdmin(ModelAdmin[Project]):
    list_display = ("id", "name", "owner")
    readonly_fields = ("code", "owner")


admin.site.unregister(User)


class OneUserPasswordChangeForm(AdminPasswordChangeForm):
    """The admin's password form without its switch that turns password log-in off."""

    def __init__(self, user: User, *args: object, **kwargs: object) -> None:
        super().__init__(user, *args, **kwargs)
        self.fields.pop("usable_password", None)


@admin.register(User)
class HcUserAdmin(UserAdmin[User]):
    list_display = ("id", "email", "date_joined", "last_login", "is_staff")
    list_display_links = ("id", "email")
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

    @override
    @method_decorator(sensitive_post_parameters())
    @method_decorator(require_sudo_mode)
    def user_change_password(self, request: HttpRequest, id: str, form_url: str = "") -> HttpResponse:
        return super().user_change_password(request, id, form_url)


@admin.register(Credential)
class CredentialAdmin(ModelAdmin[Credential]):
    list_display = ("id", "created", "user", "name")
    readonly_fields = ("user",)

    def has_add_permission(self, request: HttpRequest) -> bool:
        # A security key is registered on the profile page, behind sudo mode
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Credential | None = None) -> bool:
        # A security key is removed on the profile page, behind sudo mode
        return False
