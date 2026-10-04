from __future__ import annotations

from django.contrib import admin
from django.contrib.admin import ModelAdmin

from hc.api.models import Channel, Check, Flip, Notification, Ping


@admin.register(Check)
class ChecksAdmin(ModelAdmin[Check]):
    list_display = ("id", "name", "project", "created", "status", "last_ping")
    readonly_fields = ("code",)


@admin.register(Ping)
class PingsAdmin(ModelAdmin[Ping]):
    list_display = ("id", "created", "owner", "kind", "scheme", "method")


@admin.register(Channel)
class ChannelsAdmin(ModelAdmin[Channel]):
    list_display = ("id", "name", "kind", "project", "last_notify", "last_error", "disabled")
    readonly_fields = ("code",)


@admin.register(Notification)
class NotificationsAdmin(ModelAdmin[Notification]):
    list_display = ("id", "created", "channel", "check_status", "error")
    readonly_fields = ("code",)


@admin.register(Flip)
class FlipsAdmin(ModelAdmin[Flip]):
    list_display = ("id", "created", "processed", "owner", "old_status", "new_status")
