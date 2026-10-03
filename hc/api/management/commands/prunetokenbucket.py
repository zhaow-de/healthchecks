from __future__ import annotations

from argparse import ArgumentParser
from datetime import timedelta as td
from typing import Any

from django.core.management.base import BaseCommand
from django.utils.timezone import now

from hc.api.models import TokenBucket


class Command(BaseCommand):
    help = "Prune token bucket entries older than a day, or every entry with --all"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--all",
            action="store_true",
            help="Delete every entry, the recent ones too: this lifts a login lockout.",
        )

    def handle(self, **options: Any) -> str:
        q = TokenBucket.objects.all()
        if not options["all"]:
            q = q.filter(updated__lt=now() - td(days=1))
        n_pruned, _ = q.delete()

        return f"Done! Pruned {n_pruned} token bucket entries"
