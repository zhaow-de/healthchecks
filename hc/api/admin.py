from django.contrib import admin
from django.contrib.admin import ModelAdmin
from django.db.models import QuerySet
from django.http import HttpRequest

from hc.api.models import Channel, Check, Flip, Notification, Ping


@admin.register(Check)
class ChecksAdmin(ModelAdmin[Check]):
    list_display = ("id", "name", "project", "created", "status", "last_ping")
    readonly_fields = ("code",)
    raw_id_fields = ("project",)


@admin.register(Ping)
class PingsAdmin(ModelAdmin[Ping]):
    list_display = ("id", "created", "owner", "kind", "scheme", "method")
    readonly_fields = ("owner",)
    show_full_result_count = False

    def get_queryset(self, request: HttpRequest) -> QuerySet[Ping]:
        return super().get_queryset(request).defer("body_raw")


@admin.register(Channel)
class ChannelsAdmin(ModelAdmin[Channel]):
    list_display = ("id", "name", "kind", "project", "last_notify", "last_error", "disabled")
    readonly_fields = ("code",)
    raw_id_fields = ("project", "checks")


@admin.register(Notification)
class NotificationsAdmin(ModelAdmin[Notification]):
    list_display = ("id", "created", "channel", "check_status", "error")
    readonly_fields = ("owner", "code")
    raw_id_fields = ("channel",)
    show_full_result_count = False


@admin.register(Flip)
class FlipsAdmin(ModelAdmin[Flip]):
    list_display = ("id", "created", "processed", "owner", "old_status", "new_status")
    raw_id_fields = ("owner",)
    show_full_result_count = False
