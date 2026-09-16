import unittest
from src.formatter import normalize, render, summarize

class Behavior(unittest.TestCase):
    def test_composition(self):
        self.assertEqual(normalize(" Straße "), "strasse")
        self.assertEqual(render("x"), "[x]")
        self.assertEqual(summarize(" A  B "), "[a b]")
        self.assertEqual(summarize(""), "[]")
