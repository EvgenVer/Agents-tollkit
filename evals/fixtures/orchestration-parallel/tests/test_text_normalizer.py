import unittest

from src.text_normalizer import normalize_key_value_lines


class KeyValueNormalizerTests(unittest.TestCase):
    def test_parses_quoted_values_and_ignores_blank_lines(self) -> None:
        self.assertEqual(
            normalize_key_value_lines(
                'User=" Ada Lovelace " COUNT=2\n\nEnabled=true\n'
            ),
            [
                {"user": "Ada Lovelace", "count": "2"},
                {"enabled": "true"},
            ],
        )

    def test_rejects_a_token_without_equals_with_line_number(self) -> None:
        with self.assertRaisesRegex(ValueError, "line 1"):
            normalize_key_value_lines("valid=1 broken\n")


if __name__ == "__main__":
    unittest.main()
