from unittest import TestCase

from hc.lib.string import is_valid_uuid_string, replace


class StringTestCase(TestCase):
    def test_it_works(self) -> None:
        result = replace("$A is $B", {"$A": "aaa", "$B": "bbb"})
        self.assertEqual(result, "aaa is bbb")

    def test_it_ignores_placeholders_in_values(self) -> None:
        result = replace("$A is $B", {"$A": "$B", "$B": "$A"})
        self.assertEqual(result, "$B is $A")

    def test_it_ignores_overlapping_placeholders(self) -> None:
        result = replace("$$AB", {"$A": "", "$B": "text"})
        self.assertEqual(result, "$B")

    def test_it_preserves_non_placeholder_dollar_signs(self) -> None:
        result = replace("$3.50", {"$A": "text"})
        self.assertEqual(result, "$3.50")

    def test_it_validates_uuid_strings(self) -> None:
        self.assertTrue(is_valid_uuid_string("684E2E73-017e-465f-8149-d70b7c5aaa49"))
        self.assertFalse(is_valid_uuid_string("684e2e73-017e-465f-8149-d70b7c5aaa49\n"))
        self.assertFalse(is_valid_uuid_string("684e2e73-017e-465f-8149-d70b7c5aaa490"))
