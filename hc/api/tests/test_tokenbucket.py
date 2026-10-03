from __future__ import annotations

from datetime import datetime
from datetime import timedelta as td
from unittest import skipUnless
from unittest.mock import patch

from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from django.utils.timezone import now

from hc.api.models import TokenBucket
from hc.test import BaseTestCase

# This is sha1("alice@example.org" + "test-secred")
ALICE_HASH = "d60db3b2343e713a4de3e92d4eb417e4f05f06ab"


@override_settings(SECRET_KEY="test-secret")
class TokenBucketTestCase(BaseTestCase):
    def test_it_works(self) -> None:
        r = TokenBucket.authorize_login_email("alice@example.org")
        self.assertTrue(r)

        obj = TokenBucket.objects.get()
        self.assertEqual(obj.tokens, 0.9)
        self.assertEqual(obj.value, "em-" + ALICE_HASH)

    def test_it_handles_insufficient_tokens(self) -> None:
        TokenBucket.objects.create(value="em-" + ALICE_HASH, tokens=0.04)

        r = TokenBucket.authorize_login_email("alice@example.org")
        self.assertFalse(r)

    def test_it_tops_up(self) -> None:
        obj = TokenBucket(value="em-" + ALICE_HASH)
        obj.tokens = 0
        obj.updated = now() - td(minutes=30)
        obj.save()

        r = TokenBucket.authorize_login_email("alice@example.org")
        self.assertTrue(r)

        obj.refresh_from_db()
        self.assertAlmostEqual(obj.tokens, 0.4, places=4)

    @skipUnless(connection.features.has_select_for_update, "no row locks")
    def test_it_locks_the_row(self) -> None:
        with CaptureQueriesContext(connection) as ctx:
            TokenBucket.authorize_login_email("alice@example.org")

        sqls = [q["sql"] for q in ctx.captured_queries]
        self.assertTrue(any(sql.endswith(" FOR UPDATE") for sql in sqls))

    def test_it_reads_and_writes_in_one_atomic_block(self) -> None:
        # TestCase wraps each test in a transaction, so the block shows as a savepoint.
        # Without it select_for_update raises TransactionManagementError on PostgreSQL.
        TokenBucket.objects.create(value="em-" + ALICE_HASH)
        with CaptureQueriesContext(connection) as ctx:
            TokenBucket.authorize_login_email("alice@example.org")

        verbs = [q["sql"].split()[0] for q in ctx.captured_queries]
        self.assertEqual(verbs, ["SAVEPOINT", "SELECT", "UPDATE", "RELEASE"])

    def test_it_reads_the_clock_after_the_bucket(self) -> None:
        TokenBucket.objects.create(value="em-" + ALICE_HASH)
        reads: list[int] = []

        def clock() -> datetime:
            reads.append(len(ctx.captured_queries))
            return now()

        with CaptureQueriesContext(connection) as ctx, patch("hc.api.models.now", clock):
            TokenBucket.authorize_login_email("alice@example.org")

        # Once, after SAVEPOINT and SELECT
        self.assertEqual(reads, [2])

    def test_it_normalizes_email(self) -> None:
        emails = ("alice+alias@example.org", "a.li.ce@example.org")

        for email in emails:
            TokenBucket.authorize_login_email(email)

        self.assertEqual(TokenBucket.objects.count(), 1)

    def test_it_keys_a_trusted_device_apart(self) -> None:
        nonce = "a" * 32
        TokenBucket.authorize_login_password("alice@example.org", nonce)
        TokenBucket.authorize_login_email("alice@example.org", nonce)

        values = sorted(TokenBucket.objects.values_list("value", flat=True))
        self.assertEqual(values, [f"em-{ALICE_HASH}-{nonce}", f"pw-{ALICE_HASH}-{nonce}"])
        self.assertTrue(all(len(v) <= 80 for v in values))

    def test_it_caps_untrusted_password_attempts(self) -> None:
        for i in range(100):
            self.assertTrue(TokenBucket.authorize_login_password(f"user{i}@example.org"))

        self.assertFalse(TokenBucket.authorize_login_password("alice@example.org"))
        self.assertFalse(TokenBucket.objects.filter(value=f"pw-{ALICE_HASH}").exists())
        self.assertEqual(TokenBucket.objects.count(), 101)

    def test_untrusted_cap_refills_over_a_day(self) -> None:
        # 100 attempts per 24 hours: one attempt's worth refills in 864 seconds
        obj = TokenBucket.objects.create(value="pw-untrusted", tokens=0, updated=now() - td(seconds=800))
        self.assertFalse(TokenBucket.authorize_login_password("alice@example.org"))

        obj.updated = now() - td(seconds=900)
        obj.save()
        self.assertTrue(TokenBucket.authorize_login_password("alice@example.org"))

    def test_trusted_device_skips_the_untrusted_cap(self) -> None:
        TokenBucket.objects.create(value="pw-untrusted", tokens=0)

        self.assertTrue(TokenBucket.authorize_login_password("alice@example.org", "a" * 32))
        obj = TokenBucket.objects.get(value="pw-untrusted")
        self.assertEqual(obj.tokens, 0)
