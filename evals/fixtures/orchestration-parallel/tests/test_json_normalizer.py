import unittest

from src.json_normalizer import normalize_json_lines


class JsonNormalizerTests(unittest.TestCase):
    def test_normalizes_each_object_and_ignores_blank_lines(self) -> None:
        self.assertEqual(
            normalize_json_lines(
                '{" User Name ": " Ada ", "COUNT": 2}\n\n{"Enabled": true}\n'
            ),
            [
                {"user_name": "Ada", "count": 2},
                {"enabled": True},
            ],
        )

    def test_rejects_a_non_object_with_line_number(self) -> None:
        with self.assertRaisesRegex(ValueError, "line 1"):
            normalize_json_lines("[1, 2]\n")


if __name__ == "__main__":
    unittest.main()
