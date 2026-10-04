from datetime import timedelta as td
from typing import Any

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.http import HttpRequest
from pyotp.totp import TOTP

from hc.accounts import device
from hc.accounts.models import REPORT_CHOICES
from hc.api.models import TokenBucket
from hc.front.forms import TimezoneField


class LowercaseEmailField(forms.EmailField):
    def clean(self, value: str) -> str:
        value = super().clean(value)
        return value.lower()


class EmailLoginForm(forms.Form):
    # Call it "identity" instead of "email"
    # to avoid some of the dumber bots
    identity = LowercaseEmailField()

    def __init__(self, request: HttpRequest | None = None):
        self.request = request
        super().__init__(request.POST if request else None)

    def clean_identity(self) -> str:
        v = self.cleaned_data["identity"]

        assert isinstance(v, str)
        assert self.request
        self.user: User | None = User.objects.filter(email=v).first()
        nonce = device.nonce(self.request, self.user)
        if not TokenBucket.authorize_login_email(v, nonce):
            raise forms.ValidationError("Too many attempts, please try later.")

        if not nonce and not TokenBucket.authorize_auth_ip(self.request):
            raise forms.ValidationError("Too many attempts, please try later.")

        return v


class PasswordLoginForm(forms.Form):
    email = LowercaseEmailField()
    password = forms.CharField()

    def __init__(self, request: HttpRequest | None = None):
        self.request = request
        super().__init__(request.POST if request else None)

    def clean(self) -> dict[str, Any]:
        username = self.cleaned_data.get("email")
        password = self.cleaned_data.get("password")

        if username and password:
            assert self.request
            user = User.objects.filter(email=username).first()
            nonce = device.nonce(self.request, user)
            if not TokenBucket.authorize_login_password(username, nonce):
                raise forms.ValidationError("Too many attempts, please try later.")

            self.user = authenticate(username=username, password=password)
            if self.user is None or not self.user.is_active:
                raise forms.ValidationError("Incorrect email or password.")

        return self.cleaned_data


class ReportSettingsForm(forms.Form):
    reports = forms.ChoiceField(choices=REPORT_CHOICES)
    nag_period = forms.IntegerField(min_value=0, max_value=86400)

    def clean_nag_period(self) -> td:
        seconds = self.cleaned_data["nag_period"]

        if seconds not in (0, 3600, 86400):
            raise forms.ValidationError(f"Bad nag_period: {seconds}")

        return td(seconds=seconds)


class SetPasswordForm(forms.Form):
    error_css_class = "has-error"
    password = forms.CharField()

    def __init__(self, user: User, *args: Any, **kwargs: Any) -> None:
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        assert isinstance(password, str)
        validate_password(password, self.user)
        return password


class ChangeEmailForm(forms.Form):
    error_css_class = "has-error"
    email = LowercaseEmailField()

    def clean_email(self) -> str:
        v = self.cleaned_data["email"]
        assert isinstance(v, str)
        if User.objects.filter(email=v).exists():
            raise forms.ValidationError(f"{v} is already registered")

        return v


class ProjectNameForm(forms.Form):
    name = forms.CharField(max_length=60)


class AddWebAuthnForm(forms.Form):
    name = forms.CharField(max_length=100)
    response = forms.CharField()


class WebAuthnForm(forms.Form):
    response = forms.CharField()


class TotpForm(forms.Form):
    error_css_class = "has-error"
    code = forms.RegexField(regex=r"^\d{6}$")

    def __init__(self, totp: TOTP, post: Any = None):
        self.totp = totp
        super().__init__(post)

    def clean_code(self) -> str:
        assert isinstance(self.cleaned_data["code"], str)
        if not self.totp.verify(self.cleaned_data["code"], valid_window=1):
            raise forms.ValidationError("The code you entered was incorrect.")

        return self.cleaned_data["code"]


class TzForm(forms.Form):
    tz = TimezoneField()
