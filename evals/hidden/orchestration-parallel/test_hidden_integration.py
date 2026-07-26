import unittest

from src.csv_normalizer import normalize_csv_table
from src.json_normalizer import normalize_json_lines
from src.text_normalizer import normalize_key_value_lines


class HiddenIntegrationTests(unittest.TestCase):
    def test_all_normalizers_handle_empty_input(self) -> None:
        self.assertEqual(normalize_csv_table(" \n\n"), [])
        self.assertEqual(normalize_json_lines(" \n\n"), [])
        self.assertEqual(normalize_key_value_lines(" \n\n"), [])

    def test_csv_rejects_duplicate_normalized_headers(self) -> None:
        with self.assertRaises(ValueError):
            normalize_csv_table(" User Name ,user   name\nAda,Lovelace\n")

    def test_json_keeps_non_string_values_and_rejects_key_collisions(self) -> None:
        self.assertEqual(
            normalize_json_lines('{" Enabled ": true, " Items ": [1, 2]}\n'),
            [{"enabled": True, "items": [1, 2]}],
        )
        with self.assertRaisesRegex(ValueError, "line 1"):
            normalize_json_lines('{" User ": 1, "user": 2}\n')

    def test_key_value_parser_rejects_duplicate_keys(self) -> None:
        with self.assertRaisesRegex(ValueError, "line 2"):
            normalize_key_value_lines("ok=1\nName=Ada name=Grace\n")


if __name__ == "__main__":
    unittest.main()
