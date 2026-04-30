import json
import unittest

from common import ArrInstance, IntegrationsConfig
from common.persist import PersistError


class TestArrInstance(unittest.TestCase):
    def test_kind_must_be_known(self):
        with self.assertRaises(ValueError):
            ArrInstance(name="X", kind="lidarr")

    def test_round_trip_dict(self):
        inst = ArrInstance(name="TV", kind="sonarr", url="http://s", api_key="k", enabled=False)
        d = inst.to_dict()
        rebuilt = ArrInstance.from_dict(d)
        self.assertEqual(inst, rebuilt)

    def test_from_dict_rejects_bad_types(self):
        base = {"id": "x", "name": "TV", "kind": "sonarr", "url": "http://s", "api_key": "k", "enabled": True}
        for field, bad in (
            ("name", 5),
            ("kind", None),
            ("url", 7),
            ("api_key", []),
            ("enabled", "true"),
        ):
            payload = dict(base)
            payload[field] = bad
            with self.assertRaises(TypeError, msg=field):
                ArrInstance.from_dict(payload)

    def test_repr_redacts_api_key(self):
        inst = ArrInstance(name="X", kind="sonarr", url="http://x", api_key="leak")
        self.assertNotIn("leak", repr(inst))


class TestIntegrationsConfig(unittest.TestCase):
    def test_add_get_remove(self):
        cfg = IntegrationsConfig()
        a = ArrInstance(name="A", kind="sonarr", url="http://a", api_key="1")
        cfg.add_instance(a)
        self.assertEqual(1, len(cfg.instances))
        self.assertEqual("A", cfg.get_instance(a.id).name)
        cfg.remove_instance(a.id)
        self.assertEqual([], cfg.instances)

    def test_add_rejects_duplicate_id(self):
        cfg = IntegrationsConfig()
        a = ArrInstance(instance_id="same", name="A", kind="sonarr")
        b = ArrInstance(instance_id="same", name="B", kind="radarr")
        cfg.add_instance(a)
        with self.assertRaises(ValueError):
            cfg.add_instance(b)

    def test_add_rejects_duplicate_name(self):
        cfg = IntegrationsConfig()
        cfg.add_instance(ArrInstance(name="Sonarr — TV", kind="sonarr"))
        with self.assertRaises(ValueError):
            cfg.add_instance(ArrInstance(name="Sonarr — TV", kind="radarr"))

    def test_update_changes_fields(self):
        cfg = IntegrationsConfig()
        a = ArrInstance(name="A", kind="sonarr", url="http://a", api_key="1")
        cfg.add_instance(a)
        updated = ArrInstance(instance_id=a.id, name="A", kind="sonarr", url="http://b", api_key="2", enabled=False)
        cfg.update_instance(updated)
        got = cfg.get_instance(a.id)
        self.assertEqual("http://b", got.url)
        self.assertFalse(got.enabled)

    def test_update_unknown_id_raises(self):
        cfg = IntegrationsConfig()
        with self.assertRaises(ValueError):
            cfg.update_instance(ArrInstance(instance_id="ghost", name="X", kind="sonarr"))

    def test_remove_unknown_id_raises(self):
        cfg = IntegrationsConfig()
        with self.assertRaises(ValueError):
            cfg.remove_instance("ghost")

    def test_persistence_round_trip(self):
        cfg = IntegrationsConfig()
        cfg.add_instance(ArrInstance(name="A", kind="sonarr", url="http://a", api_key="1"))
        cfg.add_instance(ArrInstance(name="B", kind="radarr", url="http://b", api_key="2", enabled=False))
        rebuilt = IntegrationsConfig.from_str(cfg.to_str())
        self.assertEqual(cfg.instances, rebuilt.instances)

    def test_from_str_rejects_malformed_payloads(self):
        with self.assertRaises(PersistError):
            IntegrationsConfig.from_str("not json")
        with self.assertRaises(PersistError):
            IntegrationsConfig.from_str(json.dumps([1, 2]))
        with self.assertRaises(PersistError):
            IntegrationsConfig.from_str(json.dumps({"instances": "wrong"}))
        with self.assertRaises(PersistError):
            IntegrationsConfig.from_str(json.dumps({"instances": [{"id": "x"}]}))

    def test_migrate_from_legacy_creates_one_per_service_with_url(self):
        ic = IntegrationsConfig.migrate_from_legacy(
            sonarr_url="http://s",
            sonarr_api_key="sk",
            sonarr_enabled=True,
            radarr_url="http://r",
            radarr_api_key="rk",
            radarr_enabled=False,
        )
        kinds = sorted(i.kind for i in ic.instances)
        self.assertEqual(["radarr", "sonarr"], kinds)
        sonarr = next(i for i in ic.instances if i.kind == "sonarr")
        radarr = next(i for i in ic.instances if i.kind == "radarr")
        self.assertTrue(sonarr.enabled)
        self.assertFalse(radarr.enabled)

    def test_migrate_from_legacy_skips_services_without_url(self):
        ic = IntegrationsConfig.migrate_from_legacy(
            sonarr_url="",
            sonarr_api_key="",
            sonarr_enabled=False,
            radarr_url="http://r",
            radarr_api_key="rk",
            radarr_enabled=True,
        )
        self.assertEqual(1, len(ic.instances))
        self.assertEqual("radarr", ic.instances[0].kind)


if __name__ == "__main__":
    unittest.main()
