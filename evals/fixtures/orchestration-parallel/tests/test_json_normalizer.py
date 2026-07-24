import unittest

from src.json_normalizer import normalize_json_object


class JsonNormalizerTests(unittest.TestCase):
    def test_normalizes_keys_and_string_values(self) -> None:
        self.assertEqual(
            normalize_json_object({" Name ": " Ada ", "COUNT": 2}),
            {"name": "Ada", "count": 2},
        )


if __name__ == "__main__":
    unittest.main()
