import unittest

from src.jsonl_batch import group_json_events, load_json_events


class JsonLinesBatchTests(unittest.TestCase):
    def test_loads_objects_and_preserves_non_strings(self) -> None:
        self.assertEqual(
            load_json_events(
                '{" User Name ": " Ada ", "COUNT": 2}\n\n'
                '{"User Name": "Grace", "Enabled": true}\n',
                required=("user_name",),
            ),
            [
                {"user_name": "Ada", "count": 2},
                {"user_name": "Grace", "enabled": True},
            ],
        )

    def test_groups_events_in_input_order(self) -> None:
        grouped = group_json_events(
            '{"Type":"a","id":1}\n{"Type":"b","id":2}\n{"Type":"a","id":3}\n',
            " type ",
        )
        self.assertEqual([item["id"] for item in grouped["a"]], [1, 3])
        self.assertEqual([item["id"] for item in grouped["b"]], [2])

    def test_rejects_non_object_with_line_number(self) -> None:
        with self.assertRaisesRegex(ValueError, "line 2"):
            load_json_events('{"ok": 1}\n[1, 2]\n')


if __name__ == "__main__":
    unittest.main()
