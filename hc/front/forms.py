from datetime import UTC, datetime
from datetime import timedelta as td
from typing import Any

from django import forms

from hc.front.validators import (
    CronValidator,
    OnCalendarValidator,
    TimezoneValidator,
    WebhookValidator,
)


def _choices(csv: str) -> list[tuple[str, str]]:
    return [(v, v) for v in csv.split(",")]


class LaxURLField(forms.URLField):
    """Subclass of URLField which additionally accepts URLs without a tld.

    For example, unlike URLField, it accepts "http://home_server"

    """

    default_validators = [WebhookValidator()]


class SecondsDurationField(forms.IntegerField):
    """A number of seconds, from a minute to a year, cleaned to a timedelta."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(min_value=60, max_value=31536000, **kwargs)

    def clean(self, value: Any) -> td:
        return td(seconds=super().clean(value))


class TimezoneField(forms.CharField):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(max_length=36, validators=[TimezoneValidator()], **kwargs)


class NameTagsForm(forms.Form):
    name = forms.CharField(max_length=100, required=False)
    # The characters a slug ping URL accepts (ping_by_slug refuses uppercase)
    slug = forms.RegexField(
        regex=r"^[a-z0-9_-]+$",
        max_length=100,
        required=False,
        error_messages={"invalid": "Use lowercase letters, digits, dashes and underscores only."},
    )
    tags = forms.CharField(max_length=500, required=False)
    desc = forms.CharField(required=False)

    def clean_tags(self) -> str:
        result = []

        for part in self.cleaned_data["tags"].split(" "):
            part = part.strip()
            if part != "":
                result.append(part)

        return " ".join(result)


class AddCheckForm(NameTagsForm):
    kind = forms.ChoiceField(choices=_choices("simple,cron,oncalendar"))
    timeout = SecondsDurationField()
    schedule = forms.CharField(required=False, max_length=100)
    tz = TimezoneField()
    grace = SecondsDurationField()

    def clean_schedule(self) -> str:
        kind = self.cleaned_data.get("kind")
        if kind == "cron":
            cron_validator = CronValidator()
            cron_validator(self.cleaned_data["schedule"])
        elif kind == "oncalendar":
            oncalendar_validator = OnCalendarValidator()
            oncalendar_validator(self.cleaned_data["schedule"])
        else:
            # If kind is not cron or oncalendar, ignore the passed in value
            # and use "* * * * *" instead.
            return "* * * * *"

        assert isinstance(self.cleaned_data["schedule"], str)
        return self.cleaned_data["schedule"]


class FilteringRulesForm(forms.Form):
    filter_http_body = forms.BooleanField(required=False)
    filter_default_fail = forms.BooleanField(required=False)
    start_kw = forms.CharField(required=False, max_length=200)
    success_kw = forms.CharField(required=False, max_length=200)
    failure_kw = forms.CharField(required=False, max_length=200)
    methods = forms.ChoiceField(required=False, choices=(("", "Any"), ("POST", "POST")))
    manual_resume = forms.BooleanField(required=False)


class TimeoutForm(forms.Form):
    timeout = SecondsDurationField()
    grace = SecondsDurationField()


class CronPreviewForm(forms.Form):
    schedule = forms.CharField(max_length=100, validators=[CronValidator()])
    tz = TimezoneField()


class CronForm(CronPreviewForm):
    grace = SecondsDurationField()


class OnCalendarForm(forms.Form):
    schedule = forms.CharField(max_length=100, validators=[OnCalendarValidator()])
    tz = TimezoneField()
    grace = SecondsDurationField()


class AddUrlForm(forms.Form):
    error_css_class = "has-error"
    value = LaxURLField(max_length=1000, assume_scheme="https")


class ChannelNameForm(forms.Form):
    name = forms.CharField(max_length=100, required=False)


class SearchForm(forms.Form):
    q = forms.RegexField(regex=r"^[0-9a-zA-Z\s]{3,100}$")


class LogFiltersForm(forms.Form):
    # min_value is 2009-12-31T22:00Z, max_value is 2100-01-01T00:00Z
    u = forms.FloatField(min_value=1262296800, max_value=4102444800, required=False)
    end = forms.FloatField(min_value=1262296800, max_value=4102444800, required=False)
    success = forms.BooleanField(required=False)
    fail = forms.BooleanField(required=False)
    start = forms.BooleanField(required=False)
    log = forms.BooleanField(required=False)
    ign = forms.BooleanField(required=False)
    notification = forms.BooleanField(required=False)
    flip = forms.BooleanField(required=False)

    def clean_u(self) -> datetime | None:
        if self.cleaned_data["u"]:
            return datetime.fromtimestamp(self.cleaned_data["u"], tz=UTC)
        return None

    def clean_end(self) -> datetime | None:
        if self.cleaned_data["end"]:
            return datetime.fromtimestamp(self.cleaned_data["end"], tz=UTC)
        return None

    def kinds(self) -> tuple[str, ...]:
        kind_keys = ("success", "fail", "start", "log", "ign", "notification", "flip")
        return tuple(key for key in kind_keys if self.cleaned_data[key])


class TransferForm(forms.Form):
    project = forms.UUIDField()
