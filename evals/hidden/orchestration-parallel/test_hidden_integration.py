import unittest

from src.csv_normalizer import normalize_csv_row
from src.json_normalizer import normalize_json_object
from src.text_normalizer import normalize_text


class HiddenIntegrationTests(unittest.TestCase):
    def test_all_normalizers_handle_empty_values(self) -> None:
        self.assertEqual(normalize_csv_row(" , "), [])
        self.assertEqual(normalize_json_object({}), {})
        self.assertEqual(normalize_text(" \n\t "), "")

    def test_json_keeps_non_string_values(self) -> None:
        self.assertEqual(
            normalize_json_object({" Enabled ": True, " Items ": [1, 2]}),
            {"enabled": True, "items": [1, 2]},
        )


if __name__ == "__main__":
    unittest.main()
