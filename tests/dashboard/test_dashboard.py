import hashlib
import zipfile
import errno
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from tools import dashboard


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_absent_reports_do_not_claim_passes(self):
        snapshot = dashboard.make_snapshot([("Missing", self.root / "absent.xml")])
        self.assertEqual(snapshot["reports"], [])
        self.assertEqual(snapshot["missingReports"], ["Missing"])
        self.assertTrue(all(r["state"] == "pending" for r in snapshot["requirements"] if r["method"] == "Test"))
        self.assertIsNone(snapshot["demo"])

    def test_real_pass_and_failed_parameter_propagate(self):
        report = self.root / "results.xml"
        report.write_text('<testsuite>' + ''.join(
            '<testcase name="' + name + '"/>' for name in (
                'test_fsw_005_packets_c', 'test_fsw_005_packets_python',
                'test_fsw_005_packets_cross_language', 'test_fsw_006_sequence_wrap_c'))
            + '<testcase name="test_fsw_006_sequence_wrap_python"><failure/></testcase></testsuite>')
        snapshot = dashboard.make_snapshot([("Test environment", report)])
        states = {r["id"]: r["state"] for r in snapshot["requirements"]}
        self.assertEqual(states["FSW-005"], "passed")
        self.assertEqual(states["FSW-006"], "failed")
        self.assertEqual(snapshot["reports"][0]["state"], "incomplete")

    def test_export_contains_assets_and_sources_without_tokens(self):
        dashboard.export(self.root / "site", [])
        for name in ("index.html", "style.css", "app.js", "data.json", "docs/design.md"):
            self.assertTrue((self.root / "site" / name).is_file())
        data = json.loads((self.root / "site/data.json").read_text())
        self.assertNotIn("token", data)
        self.assertNotIn(str(dashboard.ROOT), json.dumps(data))

    def test_release_bundle_hashes_match_downloaded_evidence(self):
        site = self.root / "site"
        dashboard.export(site, [])
        with zipfile.ZipFile(site / "kestrel-verification.zip") as bundle:
            hashes = json.loads(bundle.read("SHA256.json"))
            self.assertIn("docs/verification/m5-demo/mission.csv", hashes)
            for name, expected in hashes.items():
                self.assertEqual(hashlib.sha256(bundle.read(name)).hexdigest(), expected)
            data = json.loads(bundle.read("data.json"))
            self.assertEqual(data["release"]["mission"]["result"], "pass")
            self.assertEqual(len(data["release"]["records"]), 5)

    def test_missing_binary_is_not_a_success(self):
        with self.assertRaises(FileNotFoundError):
            dashboard.run_demo(self.root / "missing")

    def test_invalid_demo_summary_is_rejected(self):
        binary = self.root / "fake"
        binary.touch()
        with patch.object(dashboard.subprocess, "run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = '{"result":"pass","messages":19}'
            with self.assertRaises(ValueError):
                dashboard.run_demo(binary)


class LocalServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.server = dashboard.DashboardServer(0, root, [], root / "missing", {"demo": None})
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()

    def test_local_state_has_token_but_no_run_capability_without_binary(self):
        with urlopen(self.url + "/api/state") as response:
            state = json.load(response)
        self.assertEqual(state["token"], self.server.token)
        self.assertFalse(state["canRun"])

    def test_duplicate_port_preserves_original_error_and_existing_server(self):
        root = Path(self.temp.name)
        with self.assertRaises(OSError) as error:
            dashboard.DashboardServer(self.server.server_port, root, [], root / "missing", {})
        self.assertEqual(error.exception.errno, errno.EADDRINUSE)
        with urlopen(self.url + "/api/state") as response:
            self.assertEqual(json.load(response)["token"], self.server.token)

    def test_cli_duplicate_port_explains_how_to_open_console(self):
        stderr = io.StringIO()
        argv = ["dashboard.py", "serve", "--port", str(self.server.server_port),
                "--output", str(Path(self.temp.name) / "export")]
        with patch.object(dashboard.sys, "argv", argv), patch.object(dashboard.sys, "stderr", stderr):
            with self.assertRaises(SystemExit) as error:
                dashboard.main()
        self.assertEqual(error.exception.code, 1)
        self.assertIn("already in use", stderr.getvalue())
        self.assertIn(self.url + "/#runtime", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())

    def test_cross_origin_cannot_run_even_with_token(self):
        request = Request(self.url + "/api/run-m0", method="POST", headers={
            "Origin": "https://example.com", "X-Kestrel-Token": self.server.token})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 403)

    def test_missing_token_cannot_run(self):
        request = Request(self.url + "/api/run-m0", method="POST", headers={"Origin": self.url})
        with self.assertRaises(HTTPError) as error:
            urlopen(request)
        self.assertEqual(error.exception.code, 403)

    def test_valid_run_returns_actual_record_and_busy_run_is_rejected(self):
        request = Request(self.url + "/api/run-m0", method="POST", headers={
            "Origin": self.url, "X-Kestrel-Token": self.server.token})
        receipt = {"state": "passed", "record": {"messages": 20}}
        with patch.object(dashboard, "run_demo", return_value=receipt):
            with urlopen(request) as response:
                self.assertEqual(json.load(response), receipt)
        self.server.run_lock.acquire()
        try:
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 409)
        finally:
            self.server.run_lock.release()


if __name__ == "__main__":
    unittest.main()
