from argparse import ArgumentParser
from typing import Any

from django.core.management.base import BaseCommand

from hc.api.management.commands.prune import delete_stale_token_buckets
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
        if options["all"]:
            n_pruned, _ = TokenBucket.objects.all().delete()
        else:
            n_pruned = delete_stale_token_buckets()

        return f"Done! Pruned {n_pruned} token bucket entries"
