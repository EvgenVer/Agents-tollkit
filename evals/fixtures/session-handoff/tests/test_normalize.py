import unittest
from src.formatter import normalize

class NormalizeTests(unittest.TestCase):
    def test_values(self):
        for value, expected in [("", ""), (" A  B ", "a b"), ("Straße", "strasse")]:
            self.assertEqual(normalize(value), expected)
