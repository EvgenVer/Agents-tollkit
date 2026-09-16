import unittest
from src.formatter import normalize, summarize

class Behavior(unittest.TestCase):
    def test_checkpoint(self):
        self.assertEqual(normalize(" Straße\t A "), "strasse a")
        self.assertEqual(normalize(""), "")
        with self.assertRaises(NotImplementedError):
            summarize("A")
