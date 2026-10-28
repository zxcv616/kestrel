import json
from pathlib import Path
import tempfile
import unittest
from tools.provenance import digest, source_hashes, verify
class ProvenanceTests(unittest.TestCase):
    def test_source_and_report_changes_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'fsw').mkdir();source=root/'fsw/main.c';source.write_text('int main(void) {return 0;}')
            report=root/'results.xml';report.write_text('<testsuite/>');record=root/'provenance.json'
            record.write_text(json.dumps({'sourceHashes':source_hashes(root),'reports':{report.name:digest(report)}}))
            verify(record,[report],root)
            source.write_text('changed')
            with self.assertRaises(ValueError):verify(record,[report],root)
            source.write_text('int main(void) {return 0;}');report.write_text('changed')
            with self.assertRaises(ValueError):verify(record,[report],root)
            with self.assertRaises(ValueError):verify(record,[],root)
