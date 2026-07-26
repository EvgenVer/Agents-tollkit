import math
import unittest

from src.csv_batch import load_typed_csv
from src.jsonl_batch import group_json_events, load_json_events
from src.kv_batch import index_kv_records, load_kv_records


class HiddenIntegrationTests(unittest.TestCase):
    def test_all_loaders_handle_whitespace_only_input(self) -> None:
        self.assertEqual(load_typed_csv(" \n\n", {}), [])
        self.assertEqual(load_json_events(" \n\n"), [])
        self.assertEqual(load_kv_records(" \n\n"), [])

    def test_csv_required_width_and_finite_number_rules(self) -> None:
        with self.assertRaisesRegex(ValueError, "record 2"):
            load_typed_csv("id,value\none\n", {"id": "str", "value": "int"})
        with self.assertRaises(ValueError):
            load_typed_csv("value\nnan\n", {"value": "float"})
        result = load_typed_csv(
            "id,enabled\none,false\ntwo,1\n",
            {"id": "str", "enabled": "bool"},
            required=("enabled",),
        )
        self.assertEqual(result[0]["enabled"], False)
        self.assertEqual(result[1]["enabled"], True)
        self.assertTrue(all(not isinstance(v, float) or math.isfinite(v) for row in result for v in row.values()))

    def test_json_rejects_duplicate_members_and_non_scalar_group(self) -> None:
        with self.assertRaisesRegex(ValueError, "line 1"):
            load_json_events('{"User": 1, " user ": 2}\n')
        with self.assertRaises(ValueError):
            group_json_events('{"kind": [1, 2]}\n', "kind")

    def test_json_required_and_grouping_contract(self) -> None:
        with self.assertRaisesRegex(ValueError, "line 2"):
            load_json_events('{"id":1}\n{"name":"missing"}\n', required=("id",))
        self.assertEqual(
            list(group_json_events('{"kind":true}\n{"kind":false}\n', "kind")),
            ["True", "False"],
        )

    def test_kv_rejects_duplicate_keys_and_missing_required(self) -> None:
        with self.assertRaisesRegex(ValueError, "line 1"):
            load_kv_records("Name=Ada name=Grace\n")
        with self.assertRaisesRegex(ValueError, "line 2"):
            load_kv_records("id=one role=admin\nid=two\n", required=("role",))

    def test_kv_index_requires_unique_nonempty_values(self) -> None:
        with self.assertRaises(ValueError):
            index_kv_records("id=one\nid=one\n", "id")
        with self.assertRaises(ValueError):
            index_kv_records('id="" value=1\n', "id")


if __name__ == "__main__":
    unittest.main()
