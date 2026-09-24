import json
import os
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))

from scripts.edge_diag import diagnose_service, load_model
from scripts.edge_diag.edge_model import LOAD_STAGES, ModelLoadError
from scripts.edge_diag.cli import main


class TestLoader(unittest.TestCase):
    def test_serial_stage_order(self):
        model = load_model(use_cache=False)
        self.assertEqual(model.load_stages, LOAD_STAGES)

    def test_no_network_imports(self):
        for mod in ("socket", "http.client", "urllib.request"):
            self.assertNotIn(mod, repr(sys.modules.get("scripts.edge_diag.edge_model")))

    def test_missing_artefact_reports_stage(self):
        with self.assertRaises(ModelLoadError) as ctx:
            load_model("/nonexistent/model.json", use_cache=False)
        self.assertEqual(ctx.exception.stage, "locate")

    def test_corrupt_artefact_reports_parse_stage(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            fh.write("{not json")
            path = fh.name
        try:
            with self.assertRaises(ModelLoadError) as ctx:
                load_model(path, use_cache=False)
            self.assertEqual(ctx.exception.stage, "parse")
        finally:
            os.unlink(path)

    def test_invalid_schema_reports_validate_stage(self):
        with open(os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "edge_diag", "model.json")) as spec_fh:
            spec = json.load(spec_fh)
        spec["weights"]["healthy"] = [0.0]
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(spec, fh)
            path = fh.name
        try:
            with self.assertRaises(ModelLoadError) as ctx:
                load_model(path, use_cache=False)
            self.assertEqual(ctx.exception.stage, "validate")
        finally:
            os.unlink(path)

    def test_concurrent_loads_are_serialised_and_consistent(self):
        results = []
        def worker():
            results.append(load_model())
        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(results), 8)
        self.assertEqual(len({id(r) for r in results}), 1)


class TestDiagnosis(unittest.TestCase):
    def test_healthy(self):
        d = diagnose_service(0, 0, 86400, ["starting", "ready"])
        self.assertEqual(d.label, "healthy")

    def test_respawn_loop(self):
        d = diagnose_service(1, 30, 1.0, ["exited", "restarting"] * 5)
        self.assertEqual(d.label, "respawn_loop")

    def test_permission_fault(self):
        logs = ["open /var/lib/svc: permission denied"] * 4 + ["fatal: cannot start"]
        d = diagnose_service(1, 1, 2.0, logs)
        self.assertEqual(d.label, "permission_fault")
        self.assertTrue(d.evidence["permission"])

    def test_disk_pressure(self):
        logs = ["write log: no space left on device"] * 4 + ["error flushing"]
        d = diagnose_service(1, 1, 120.0, logs)
        self.assertEqual(d.label, "disk_pressure")

    def test_dependency_stall(self):
        logs = ["connect 127.0.0.1:5432: connection refused"] * 4 + ["waiting for database"]
        d = diagnose_service(1, 1, 300.0, logs)
        self.assertEqual(d.label, "dependency_stall")

    def test_interpretable_fields(self):
        d = diagnose_service(1, 30, 1.0, ["exited"])
        self.assertEqual(len(d.contributions), 7)
        self.assertTrue(d.remedy)
        self.assertAlmostEqual(sum(d.probabilities.values()), 1.0, places=6)


class TestCli(unittest.TestCase):
    def test_cli_json_exit_codes(self):
        with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False) as fh:
            fh.write("permission denied\n" * 4 + "fatal\n")
            path = fh.name
        try:
            self.assertEqual(main(["--exit-code", "1", "--restarts", "1", "--uptime", "2", "--log", path, "--json"]), 1)
            self.assertEqual(main(["--exit-code", "0", "--uptime", "9999", "--log", ""]), 0)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
