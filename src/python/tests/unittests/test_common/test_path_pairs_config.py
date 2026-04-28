import unittest

from common import PathPair, PathPairsConfig
from common.persist import PersistError


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


class TestPathPairsConfig(unittest.TestCase):
    def test_round_trip_persistence(self):
        """to_str/from_str round-trip must preserve all fields."""
        ppc = PathPairsConfig()
        ppc.add_pair(
            PathPair(
                name="TV",
                remote_path="/remote/tv",
                local_path="/local/tv",
                enabled=True,
                auto_queue=False,
                arr_target_ids=["id-1", "id-2"],
            )
        )
        ppc.add_pair(
            PathPair(
                name="Movies",
                remote_path="/remote/movies",
                local_path="/local/movies",
                enabled=False,
                auto_queue=True,
                arr_target_ids=[],
            )
        )

        serialized = ppc.to_str()
        restored = PathPairsConfig.from_str(serialized)

        self.assertEqual(len(ppc.pairs), len(restored.pairs))
        for original, loaded in zip(ppc.pairs, restored.pairs):
            self.assertEqual(original.id, loaded.id)
            self.assertEqual(original.name, loaded.name)
            self.assertEqual(original.remote_path, loaded.remote_path)
            self.assertEqual(original.local_path, loaded.local_path)
            self.assertEqual(original.enabled, loaded.enabled)
            self.assertEqual(original.auto_queue, loaded.auto_queue)
            self.assertEqual(original.arr_target_ids, loaded.arr_target_ids)

    def test_from_str_rejects_malformed(self):
        """Malformed JSON raises PersistError."""
        with self.assertRaises(PersistError):
            PathPairsConfig.from_str("NOT VALID JSON {{{")


if __name__ == "__main__":
    unittest.main()
