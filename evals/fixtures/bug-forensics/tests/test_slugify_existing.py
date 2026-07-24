import unittest

from src.slugify import slugify


class ExistingSlugifyTests(unittest.TestCase):
    def test_single_space_lowercase(self) -> None:
        self.assertEqual(slugify("hello world"), "hello-world")


if __name__ == "__main__":
    unittest.main()
