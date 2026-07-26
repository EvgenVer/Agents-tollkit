import unittest

from src.csv_normalizer import normalize_csv_table


class CsvNormalizerTests(unittest.TestCase):
    def test_normalizes_header_and_honors_quoted_commas(self) -> None:
        self.assertEqual(
            normalize_csv_table(
                ' User Name , Note \n Ada ," Hello, world "\n\n'
            ),
            [{"user_name": "Ada", "note": "Hello, world"}],
        )

    def test_rejects_a_row_with_the_wrong_width(self) -> None:
        with self.assertRaises(ValueError):
            normalize_csv_table("name,count\nAda\n")


if __name__ == "__main__":
    unittest.main()
