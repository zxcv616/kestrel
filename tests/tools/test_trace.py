"""Prevent missing, skipped, or merely named checks from certifying requirements."""
import hashlib
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import trace


class TraceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.requirements = trace.read_requirements(trace.ROOT / "docs/requirements.md")
        (self.root / "docs").mkdir()
        (self.root / "docs/requirements.md").write_text(
            (trace.ROOT / "docs/requirements.md").read_text())
        root_patch = patch.object(trace, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def report(self, cases):
        path = self.root / "results.xml"
        path.write_text("<testsuite>" + cases + "</testsuite>")
        return trace.read_results([path])

    def test_registry_requires_every_unique_id(self):
        original = (trace.ROOT / "docs/requirements.md").read_text()
        for altered in (original.replace("| FSW-020", "| FSW-019"),
                        original.replace("| FSW-020", "| MISSING")):
            path = self.root / "requirements.md"
            path.write_text(altered)
            with self.assertRaises(ValueError):
                trace.read_requirements(path)

    def test_m0_does_not_claim_future_evidence(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = trace.main(["--milestone", "M0"])
        self.assertEqual(result, 0)
        self.assertIn("0/20 verified", output.getvalue())

    def test_release_gate_fails_without_evidence(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(trace.main(["--milestone", "M5"]), 1)

    def test_test_name_alone_is_not_evidence(self):
        self.assertFalse(trace.evidence_passes(self.requirements[0], {}, self.root))

    def test_junit_success_counts(self):
        results = self.report('<testcase name="test_fsw_001_boot_safe"/>')
        self.assertTrue(trace.evidence_passes(self.requirements[0], results, self.root))

    def test_failure_error_skip_and_notrun_never_pass(self):
        for child in ("failure", "error", "skipped"):
            results = self.report(f'<testcase name="test_fsw_001_boot_safe"><{child}/></testcase>')
            self.assertFalse(trace.evidence_passes(self.requirements[0], results, self.root))
        results = self.report('<testcase name="test_fsw_001_boot_safe" status="notrun"/>')
        self.assertFalse(trace.evidence_passes(self.requirements[0], results, self.root))

    def test_failed_parameter_cannot_be_hidden_by_a_pass(self):
        results = self.report('<testcase name="test_fsw_001_boot_safe[a]"><failure/></testcase>'
                              '<testcase name="test_fsw_001_boot_safe[b]"/>')
        self.assertFalse(trace.evidence_passes(self.requirements[0], results, self.root))

    def test_all_named_checks_are_required(self):
        requirement = trace.Requirement("FSW-001", "Boot", "Test", "M2", ("first", "second"))
        self.assertFalse(trace.evidence_passes(requirement, {"first": [True]}, self.root))
        self.assertTrue(trace.evidence_passes(requirement, {"first": [True], "second": [True]}, self.root))

    def test_inspection_requires_review_and_real_evidence(self):
        requirement = self.requirements[15]
        path = self.root / requirement.verification[0]
        path.parent.mkdir(parents=True)
        record = {"id": "FSW-016", "result": "pass", "reviewer": "Reviewer",
                  "scope": "reviewed-build", "evidence": ["inspection.txt"]}
        path.write_text(json.dumps(record))
        self.assertFalse(trace.evidence_passes(requirement, {}, self.root))
        (self.root / "inspection.txt").write_text("Actual inspection findings")
        self.assertFalse(trace.evidence_passes(requirement, {}, self.root))
        record["sourceHashes"] = {"inspection.txt": hashlib.sha256((self.root / "inspection.txt").read_bytes()).hexdigest()}
        path.write_text(json.dumps(record))
        self.assertTrue(trace.evidence_passes(requirement, {}, self.root))
        record["scope"] = ""
        path.write_text(json.dumps(record))
        self.assertFalse(trace.evidence_passes(requirement, {}, self.root))

    def test_changed_source_invalidates_inspection(self):
        requirement = self.requirements[15]
        path = self.root / requirement.verification[0]
        path.parent.mkdir(parents=True)
        source = self.root / "flight.c"
        source.write_text("reviewed implementation")
        record = {"id": "FSW-016", "result": "pass", "reviewer": "Reviewer",
                  "scope": "source digest", "evidence": ["flight.c"],
                  "sourceHashes": {"flight.c": hashlib.sha256(source.read_bytes()).hexdigest()}}
        path.write_text(json.dumps(record))
        self.assertTrue(trace.evidence_passes(requirement, {}, self.root))
        source.write_text("changed implementation")
        self.assertFalse(trace.evidence_passes(requirement, {}, self.root))

    def test_invalid_report_is_an_error(self):
        with self.assertRaises(ValueError):
            path = self.root / "not-junit.xml"
            path.write_text("<html/>")
            trace.read_results([path])


if __name__ == "__main__":
    unittest.main()
