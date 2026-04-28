import unittest

from common import PathPair


class TestPathPair(unittest.TestCase):
    def test_arr_target_ids_dedup_preserves_order(self):
        """Constructor must dedupe arr_target_ids while preserving order so
        ArrNotifier can't emit duplicate scan commands."""
        pair = PathPair(
            name="TV",
            remote_path="/r",
            local_path="/l",
            arr_target_ids=["b", "a", "b", "c", "a"],
        )
        self.assertEqual(["b", "a", "c"], pair.arr_target_ids)

    def test_arr_target_ids_empty_when_none(self):
        pair = PathPair(name="TV", remote_path="/r", local_path="/l", arr_target_ids=None)
        self.assertEqual([], pair.arr_target_ids)

    def test_to_dict_roundtrip_preserves_dedup(self):
        pair = PathPair(
            name="TV",
            remote_path="/r",
            local_path="/l",
            arr_target_ids=["a", "a", "b"],
        )
        rebuilt = PathPair.from_dict(pair.to_dict())
        self.assertEqual(["a", "b"], rebuilt.arr_target_ids)


if __name__ == "__main__":
    unittest.main()
