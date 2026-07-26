import unittest

from src.kv_batch import index_kv_records, load_kv_records


class KeyValueBatchTests(unittest.TestCase):
    def test_loads_quoted_records(self) -> None:
        self.assertEqual(
            load_kv_records(
                'User=" Ada Lovelace " Role=admin\nUser=Grace Role=" engineer "\n',
                required=("user", "role"),
            ),
            [
                {"user": "Ada Lovelace", "role": "admin"},
                {"user": "Grace", "role": "engineer"},
            ],
        )

    def test_indexes_records(self) -> None:
        self.assertEqual(
            index_kv_records("id=one value=1\nid=two value=2\n", " ID "),
            {
                "one": {"id": "one", "value": "1"},
                "two": {"id": "two", "value": "2"},
            },
        )

    def test_rejects_missing_equals_with_line_number(self) -> None:
        with self.assertRaisesRegex(ValueError, "line 2"):
            load_kv_records("ok=1\nbroken\n")


if __name__ == "__main__":
    unittest.main()
