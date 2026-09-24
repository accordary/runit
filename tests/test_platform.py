"""Smoke tests for the integrated runit-platform entry point."""
import os
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "scripts")
PLATFORM = os.path.join(SCRIPTS, "runit-platform")


def run(*args):
    env = dict(os.environ)
    env["PYTHONPATH"] = SCRIPTS + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([PLATFORM, *args], capture_output=True, text=True, env=env)


class PlatformEntryPointTest(unittest.TestCase):
    def test_help_lists_four_capabilities(self):
        r = run("--help")
        self.assertEqual(r.returncode, 0, r.stderr)
        for cap in ("diag", "logs", "devices", "network"):
            self.assertIn(cap, r.stdout)

    def test_doctor_reports_all_capabilities_present(self):
        r = run("doctor")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn("FAIL", r.stdout)

    def test_version_reports_model(self):
        r = run("version")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("model:", r.stdout)

    def test_no_capability_exits_two(self):
        self.assertEqual(run().returncode, 2)

    def test_unknown_capability_exits_two(self):
        r = run("nope")
        self.assertEqual(r.returncode, 2)
        self.assertIn("unknown capability", r.stderr)

    def test_notices_document_bundled_model(self):
        with open(os.path.join(ROOT, "NOTICES.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("scripts/edge_diag/model.json", text)
        self.assertIn("COPYING.md", text)


if __name__ == "__main__":
    unittest.main()
