"""Build a portable mission-console snapshot or serve it with a local M0 runner."""
import argparse
import zipfile
import hashlib
import errno
from datetime import datetime, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import platform
import secrets
import shutil
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import trace  # noqa: E402
from ground import ccsds  # noqa: E402
from tools.flight_control import FlightController
from tools.scenarios import ScenarioRunner  # noqa: E402

DEFAULT_OUTPUT = ROOT / "output/dashboard/local"
HOST_LABEL = "macOS" if platform.system() == "Darwin" else platform.system()
DEFAULT_REPORTS = [
    (f"{HOST_LABEL} · Debug", ROOT / "build/results.xml"),
    (f"{HOST_LABEL} · Release", ROOT / "build-release/results.xml"),
    ("Ubuntu · Debug", ROOT / "build/verification/ubuntu-m5-debug.xml"),
    ("Ubuntu · Release", ROOT / "build/verification/ubuntu-m5-release.xml"),
    (f"{HOST_LABEL} · Debug scenarios", ROOT / "build/scenario-results.xml"),
    (f"{HOST_LABEL} · Release scenarios", ROOT / "build-release/scenario-results.xml"),
    ("Ubuntu · Debug scenarios", ROOT / "build/verification/ubuntu-m6-debug.xml"),
    ("Ubuntu · Release scenarios", ROOT / "build/verification/ubuntu-m6-release.xml"),
]


def iso_time(timestamp=None):
    return datetime.fromtimestamp(timestamp or time.time(), timezone.utc).isoformat()


def report_summary(label, path):
    root = ET.parse(path).getroot()
    if root.tag not in ("testsuites", "testsuite"):
        raise ValueError(f"Invalid JUnit report: {path}")
    cases = list(root.iter("testcase"))
    tests = []
    for case in cases:
        if any(case.find(tag) is not None for tag in ("failure", "error")):
            state = "failed"
        elif case.find("skipped") is not None or case.get("status") in ("notrun", "disabled"):
            state = "skipped"
        else:
            state = "passed"
        tests.append({"name": case.get("name", "Unnamed check"), "state": state,
                      "seconds": float(case.get("time", "0"))})
    return {"label": label, "recordedAt": iso_time(path.stat().st_mtime),
            "state": "passed" if tests and all(t["state"] == "passed" for t in tests) else "incomplete",
            "tests": tests, "file": path.name}


def run_demo(binary):
    if not binary.is_file():
        raise FileNotFoundError("Build the M0 executable first: cmake --build build")
    started = time.monotonic()
    run = subprocess.run([str(binary)], text=True, capture_output=True, timeout=10)
    if run.returncode != 0:
        raise RuntimeError(f"M0 demo exited with status {run.returncode}.")
    record = json.loads(run.stdout)
    expected = {"milestone": "M0", "messages": 20, "checksum": 2870, "result": "pass"}
    if any(record.get(key) != value for key, value in expected.items()):
        raise ValueError("M0 demo returned an invalid summary.")
    if type(record.get("elapsed_ticks")) is not int or record["elapsed_ticks"] <= 0:
        raise ValueError("M0 demo did not report advancing ticks.")
    return {"recordedAt": iso_time(), "wallMs": round((time.monotonic() - started) * 1000),
            "record": record, "source": "FreeRTOS POSIX executable", "state": "passed"}


def make_snapshot(reports, demo=None, flight_record=None):
    project = json.loads((ROOT / "dashboard/project.json").read_text())
    present = [(label, path) for label, path in reports if path.is_file()]
    results = trace.read_results([path for _, path in present])
    requirements = []
    for item in trace.read_requirements(ROOT / "docs/requirements.md"):
        complete = bool(trace.evidence_passes(item, results, ROOT))
        failed = item.method == "Test" and any(
            name in results and not all(results[name]) for name in item.verification)
        requirements.append({"id": item.identifier, "text": item.statement,
                             "method": item.method, "due": item.due,
                             "evidence": list(item.verification),
                             "state": "passed" if complete else "failed" if failed else "pending"})
    project.update({"schemaVersion": 1, "generatedAt": iso_time(),
                    "requirements": requirements,
                    "reports": [report_summary(label, path) for label, path in present],
                    "missingReports": [label for label, path in reports if not path.is_file()],
                    "demo": demo})
    fixtures = json.loads((ROOT / "tests/vectors/packets.json").read_text())
    vectors = []
    for valid, cases in ((True, fixtures["valid"]), (False, fixtures["invalid"])):
        for fixture in cases:
            expected = "OK" if valid else fixture["error"]
            try:
                packet = ccsds.decode(bytes.fromhex(fixture["hex"]))
                actual = "OK"
                matches = valid and ccsds.encode(packet).hex() == fixture["hex"]
                if valid:
                    matches = matches and packet.fields == fixture["fields"]
            except ccsds.PacketError as error:
                actual, matches = error.status, error.status == expected
            vectors.append({"name": fixture["name"], "hex": fixture["hex"], "valid": valid,
                            "expected": expected, "actual": actual, "matches": matches})
    project["protocol"] = {"vectors": vectors}
    project["flightRecord"] = flight_record
    mission = ROOT / "docs/verification/m5-demo/mission.json"
    project["release"] = {
        "version": "0.1.0",
        "mission": json.loads(mission.read_text()) if mission.is_file() else None,
        "records": {r["id"]: json.loads((ROOT / r["evidence"][0]).read_text())
                    for r in requirements if r["method"] != "Test" and
                    (ROOT / r["evidence"][0]).is_file()},
        "verified": sum(r["state"] == "passed" for r in requirements),
        "hostedCI": project["hostedCI"]["status"],
    }
    return project


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def export(output, reports, demo=None, flight_record=None):
    output.mkdir(parents=True, exist_ok=True)
    for source in (ROOT / "dashboard/web").iterdir():
        if source.is_file():
            shutil.copy2(source, output / source.name)
    snapshot = make_snapshot(reports, demo, flight_record)
    write_json(output / "data.json", snapshot)
    (output / "docs").mkdir(exist_ok=True)
    for doc in snapshot["documents"]:
        shutil.copy2(ROOT / "docs" / doc["file"], output / "docs" / doc["file"])
    bundle = {"data.json": output / "data.json", "README.md": ROOT / "README.md"}
    for source in (ROOT / "docs/verification").rglob("*"):
        if source.is_file():
            bundle[str(source.relative_to(ROOT))] = source
    for index, (_, path) in enumerate(reports):
        if path.is_file():
            bundle[f"reports/{index}-{path.name}"] = path
    manifest = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in bundle.items()}
    with zipfile.ZipFile(output / "kestrel-verification.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for name, path in bundle.items():
            archive.write(path, name)
        archive.writestr("SHA256.json", json.dumps(manifest, indent=2)+"\n")
    return snapshot


class DashboardServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, port, output, reports, binary, snapshot, flight_binary=None):
        self.flight = None
        self.scenario = None
        super().__init__(("127.0.0.1", port), partial(Handler, directory=str(output)))
        self.reports, self.binary, self.snapshot = reports, binary, snapshot
        self.run_lock = threading.Lock()
        self.token = secrets.token_urlsafe(32)
        self.flight = FlightController(flight_binary or ROOT / "build/kestrel_flight")
        self.scenario = ScenarioRunner(self.flight, self.run_lock, ROOT / "output/scenarios")

    def server_close(self):
        try:
            if self.scenario is not None:
                self.scenario.close()
            if self.flight is not None:
                self.flight.stop()
        finally:
            super().server_close()


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, format_string, *args):
        # Do not log session tokens or request bodies.
        super().log_message(format_string, *args)

    def json_response(self, status, value):
        encoded = json.dumps(value).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def valid_host(self):
        port = self.server.server_port
        return self.headers.get("Host") in (f"127.0.0.1:{port}", f"localhost:{port}")

    def do_GET(self):
        if not self.valid_host():
            return self.json_response(403, {"error": "Invalid local host."})
        if self.path == "/api/flight/log.csv":
            try:
                content = self.server.flight.csv_log()
            except (OSError, RuntimeError) as error:
                return self.json_response(409, {"error": str(error)})
            self.send_response(200)
            self.send_header("Content-Type", "text/csv")
            self.send_header("Content-Disposition", 'attachment; filename="kestrel-telemetry.csv"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if self.path == "/api/scenario/report.json":
            try:
                content = self.server.scenario.download()
            except RuntimeError as error:
                return self.json_response(409, {"error": str(error)})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Disposition", 'attachment; filename="kestrel-scenario.json"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        if self.path == "/api/flight":
            state = self.server.flight.snapshot()
            state["scenario"] = self.server.scenario.snapshot()
            return self.json_response(200, state)
        if self.path == "/api/state":
            try:
                state = make_snapshot(self.server.reports, self.server.snapshot.get("demo"), self.server.snapshot.get("flightRecord"))
                self.json_response(200, {"data": state, "token": self.server.token,
                                         "canRun": self.server.binary.is_file()})
            except (ValueError, OSError, ET.ParseError) as error:
                self.json_response(500, {"error": str(error)})
        else:
            super().do_GET()

    def set_hk_rate(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not 1 <= length <= 128:
            raise ValueError("Expected a small JSON object containing periodMs.")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict) or set(value) != {"periodMs"}:
            raise ValueError("Expected periodMs only.")
        return self.server.flight.command("set_hk_rate", value["periodMs"])

    def inject_fault(self):
        length = int(self.headers.get("Content-Length", "0"))
        if not 1 <= length <= 128:
            raise ValueError("Expected faultId JSON.")
        value = json.loads(self.rfile.read(length))
        if not isinstance(value, dict) or set(value) != {"faultId"}:
            raise ValueError("Expected faultId only.")
        return self.server.flight.command("inject_fault", value["faultId"])

    def do_POST(self):
        flight_actions = {"/api/flight/start": self.server.flight.start,
                          "/api/flight/start_test": lambda: self.server.flight.start(test_build=True),
                          "/api/flight/inject_fault": self.inject_fault,
                          "/api/flight/stop": self.server.flight.stop,
                          "/api/flight/noop": lambda: self.server.flight.command("noop"),
                          "/api/flight/request_hk": lambda: self.server.flight.command("request_hk"),
                          "/api/flight/nominal": lambda: self.server.flight.command("set_mode", 2),
                          "/api/flight/safe": lambda: self.server.flight.command("set_mode", 1),
                          "/api/flight/reset_counters": lambda: self.server.flight.command("reset_counters"),
                          "/api/flight/set_hk_rate": self.set_hk_rate}
        if self.path not in ("/api/run-m0", "/api/scenario/start", "/api/scenario/cancel") and self.path not in flight_actions:
            return self.json_response(404, {"error": "Unknown operation."})
        origin = self.headers.get("Origin", "")
        if (not self.valid_host() or origin != "http://" + self.headers.get("Host", "")
                or not secrets.compare_digest(self.headers.get("X-Kestrel-Token", ""), self.server.token)):
            return self.json_response(403, {"error": "Open the local console to control a simulator."})
        if self.path == "/api/scenario/cancel":
            return self.json_response(200, self.server.scenario.cancel())
        if self.path == "/api/scenario/start":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 1 <= length <= 128:
                    raise ValueError("Expected scenario JSON.")
                value = json.loads(self.rfile.read(length))
                if not isinstance(value, dict) or set(value) != {"scenario"}:
                    raise ValueError("Expected scenario only.")
                return self.json_response(202, self.server.scenario.start(value["scenario"]))
            except (ValueError, OSError, RuntimeError) as error:
                return self.json_response(409, {"error": str(error)})
        if self.path in flight_actions:
            if not self.server.run_lock.acquire(blocking=False):
                return self.json_response(409, {"error": "An operation is already running."})
            try:
                return self.json_response(200, flight_actions[self.path]())
            except (ValueError, OSError, RuntimeError) as error:
                return self.json_response(409, {"error": str(error)})
            finally:
                self.server.run_lock.release()
        if not self.server.run_lock.acquire(blocking=False):
            return self.json_response(409, {"error": "A demonstration is already running."})
        try:
            result = run_demo(self.server.binary)
            self.server.snapshot["demo"] = result
            self.json_response(200, result)
        except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            self.json_response(500, {"error": str(error)})
        finally:
            self.server.run_lock.release()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("build", "serve"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--binary", type=Path, default=ROOT / "build/kestrel_m0")
    parser.add_argument("--run-demo", action="store_true")
    parser.add_argument("--flight-binary", type=Path, default=ROOT / "build/kestrel_flight")
    parser.add_argument("--flight-record", type=Path, help="Recorded M2 session JSON for a hosted snapshot")
    parser.add_argument("--report", action="append", help="LABEL=path to a JUnit report")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    reports = DEFAULT_REPORTS
    if args.report:
        reports = []
        for value in args.report:
            label, path = value.split("=", 1)
            reports.append((label, Path(path).resolve()))
    binary = args.binary.resolve()
    demo = run_demo(binary) if args.run_demo else None
    flight_record = json.loads(args.flight_record.read_text()) if args.flight_record else None
    snapshot = export(args.output.resolve(), reports, demo, flight_record)
    print(f"Console exported to {args.output.resolve()}", flush=True)
    if args.action == "serve":
        try:
            server = DashboardServer(args.port, args.output.resolve(), reports, binary, snapshot, args.flight_binary.resolve())
        except OSError as error:
            if error.errno != errno.EADDRINUSE:
                raise
            print(
                f"Port {args.port} is already in use. If Kestrel is already running, "
                f"open http://127.0.0.1:{args.port}/#runtime .\n"
                "To use a different port, add --port 8766 (or another unused port).",
                file=sys.stderr,
            )
            raise SystemExit(1) from None
        print(f"Local console: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


if __name__ == "__main__":
    main()
