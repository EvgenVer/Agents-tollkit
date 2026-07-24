import unittest

from src.text_normalizer import normalize_text


class TextNormalizerTests(unittest.TestCase):
    def test_collapses_whitespace_and_lowercases(self) -> None:
        self.assertEqual(normalize_text(" Hello   WIDE\nWorld "), "hello wide world")


if __name__ == "__main__":
    unittest.main()
