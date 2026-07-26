import unittest

from src.csv_batch import load_typed_csv


class CsvBatchTests(unittest.TestCase):
    def test_loads_and_coerces_a_typed_batch(self) -> None:
        self.assertEqual(
            load_typed_csv(
                ' User Name , Active , Score \n Ada ,YES, 3.5\nBob,0,\n',
                {"user_name": "str", "active": "bool", "score": "float"},
                required=("user_name", "active"),
            ),
            [
                {"user_name": "Ada", "active": True, "score": 3.5},
                {"user_name": "Bob", "active": False, "score": None},
            ],
        )

    def test_rejects_duplicate_headers(self) -> None:
        with self.assertRaises(ValueError):
            load_typed_csv(
                "User Name,user   name\nAda,Grace\n",
                {"user_name": "str"},
            )

    def test_conversion_error_identifies_record(self) -> None:
        with self.assertRaisesRegex(ValueError, "record 2"):
            load_typed_csv("count\nnot-an-int\n", {"count": "int"})


if __name__ == "__main__":
    unittest.main()
