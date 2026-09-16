import unittest
from src.formatter import normalize, summarize

class Behavior(unittest.TestCase):
    def test_both_phases(self):
        self.assertEqual(normalize(" Straße\t A "), "strasse a")
        self.assertEqual(normalize(""), "")
        self.assertEqual(summarize(" A a\tB Straße STRASSE "), {"a": 2, "b": 1, "strasse": 2})
        self.assertEqual(summarize(""), {})
