import unittest

from src.slugify import slugify


class HiddenSlugifyTests(unittest.TestCase):
    def test_uppercase_and_repeated_whitespace(self) -> None:
        self.assertEqual(slugify("  Hello   WORLD  "), "hello-world")

    def test_tabs_and_newlines(self) -> None:
        self.assertEqual(slugify("Hello\twide\nworld"), "hello-wide-world")


if __name__ == "__main__":
    unittest.main()
