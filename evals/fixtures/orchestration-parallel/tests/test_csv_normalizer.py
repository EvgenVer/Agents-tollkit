import unittest

from src.csv_normalizer import normalize_csv_row


class CsvNormalizerTests(unittest.TestCase):
    def test_trims_and_omits_empty_cells(self) -> None:
        self.assertEqual(normalize_csv_row(" a, ,b "), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
