"""Validate the requirements register and gate milestones on real evidence."""
import argparse
import hashlib
from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
MILESTONES = tuple(f"M{i}" for i in range(6))


@dataclass(frozen=True)
class Requirement:
    identifier: str
    statement: str
    method: str
    due: str
    verification: tuple


def read_requirements(path):
    requirements = []
    for line in path.read_text().splitlines():
        if not line.startswith("| FSW-"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 5:
            raise ValueError(f"Expected five columns: {line}")
        identifier, statement, method, due, checks = cells
        if not re.fullmatch(r"FSW-\d{3}", identifier) or not statement:
            raise ValueError(f"Invalid requirement: {identifier}")
        if method not in ("Test", "Inspection", "Demo") or due not in MILESTONES:
            raise ValueError(f"Invalid method/milestone for {identifier}")
        verification = tuple(check.strip() for check in checks.split(","))
        if not all(verification) or len(set(verification)) != len(verification):
            raise ValueError(f"Missing/duplicate verification for {identifier}")
        if method == "Test":
            prefix = "test_" + identifier.lower().replace("-", "_") + "_"
            if any(not re.fullmatch(prefix + r"[a-z0-9_]+", name) for name in verification):
                raise ValueError(f"Test must contain its requirement ID: {identifier}")
        elif len(verification) != 1 or verification[0] != f"docs/verification/{identifier}.json":
            raise ValueError(f"Invalid evidence record for {identifier}")
        requirements.append(Requirement(identifier, statement, method, due, verification))
    expected = {f"FSW-{i:03}" for i in range(1, 21)}
    found = [requirement.identifier for requirement in requirements]
    if len(found) != len(set(found)) or set(found) != expected:
        raise ValueError("Registry must contain FSW-001 through FSW-020 exactly once")
    return requirements


def read_results(paths):
    results = {}
    for path in paths:
        root = ET.parse(path).getroot()
        if root.tag not in ("testsuites", "testsuite"):
            raise ValueError(f"Not a JUnit test report: {path}")
        for case in root.iter("testcase"):
            name = case.get("name", "").split("[", 1)[0]
            passed = not any(case.find(tag) is not None for tag in ("failure", "error", "skipped"))
            passed = passed and case.get("status", "run") not in ("notrun", "disabled")
            results.setdefault(name, []).append(passed)
    return results


def evidence_passes(requirement, results, root):
    if requirement.method == "Test":
        return all(results.get(name) and all(results[name]) for name in requirement.verification)
    path = root / requirement.verification[0]
    if not path.is_file():
        return False
    record = json.loads(path.read_text())
    if not isinstance(record, dict):
        raise ValueError(f"Invalid verification record: {path}")
    if record.get("id") != requirement.identifier or record.get("result") != "pass":
        return False
    for field in ("reviewer", "scope"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            return False
    evidence = record.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        return False
    for filename in evidence:
        if not isinstance(filename, str) or Path(filename).is_absolute():
            return False
        artifact = (root / filename).resolve()
        if not artifact.is_relative_to(root.resolve()) or artifact == path.resolve():
            return False
        if not artifact.is_file() or artifact.stat().st_size == 0:
            return False
    hashes = record.get("sourceHashes")
    if not isinstance(hashes, dict) or not hashes:
        return False
    for filename, expected in hashes.items():
        artifact = (root / filename).resolve()
        if not artifact.is_relative_to(root.resolve()) or not artifact.is_file():
            return False
        if hashlib.sha256(artifact.read_bytes()).hexdigest() != expected:
            return False
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, default=ROOT / "docs/requirements.md")
    parser.add_argument("--milestone", choices=MILESTONES, default="M0")
    parser.add_argument("--junit", type=Path, action="append", default=[])
    parser.add_argument("--provenance", type=Path, help="Require reports bound to current source")
    args = parser.parse_args(argv)
    try:
        if args.provenance:
            from tools.provenance import verify
            verify(args.provenance, args.junit, ROOT)
        requirements = read_requirements(args.requirements)
        results = read_results(args.junit)
        unmet = []
        passed = 0
        for requirement in requirements:
            complete = bool(evidence_passes(requirement, results, ROOT))
            required = MILESTONES.index(requirement.due) <= MILESTONES.index(args.milestone)
            passed += complete
            if required and not complete:
                unmet.append(requirement.identifier)
            state = "PASS" if complete else "PENDING"
            print(f"{requirement.identifier} {state:7} due={requirement.due} {requirement.method}")
        print(f"Evidence: {passed}/20 verified. {args.milestone} gate: "
              + ("FAIL (" + ", ".join(unmet) + ")" if unmet else "PASS"))
        return 1 if unmet else 0
    except (ValueError, OSError, ET.ParseError) as error:
        print(f"Trace error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
