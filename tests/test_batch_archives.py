from contextlib import redirect_stdout
import csv
from io import StringIO
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import zlib

from qff_grader import batch
from qff_grader.contracts import CONTRACT, VERSION


class BatchArchiveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "received"
        self.source.mkdir()
        self.bad = self.source / "01-bad.zip"
        self.bundle = {"schema_version": 1, "notebook_version": VERSION,
                       "contract": CONTRACT, "exercises": {}}

    def write_archive(self, compression=zipfile.ZIP_DEFLATED):
        with zipfile.ZipFile(self.bad, "w", compression=compression) as archive:
            archive.writestr("submission.json", json.dumps(self.bundle))
            archive.writestr("manifest.json", "{}")

    def member_data_offset(self, name):
        with zipfile.ZipFile(self.bad) as archive:
            offset = archive.getinfo(name).header_offset
        raw = self.bad.read_bytes()
        name_length, extra_length = struct.unpack_from("<HH", raw, offset + 26)
        return offset + 30 + name_length + extra_length

    def assert_batch_continues(self):
        good = self.source / "02-good.json"
        good.write_text(json.dumps(self.bundle), encoding="utf-8")
        original = {path.name: path.read_bytes() for path in self.source.iterdir()}
        with redirect_stdout(StringIO()):
            exit_code = batch.main([str(self.source), "--output", str(self.root / "reports")])
        self.assertEqual(exit_code, 2)
        summary_path, = (self.root / "reports").glob("*/summary.json")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        self.assertEqual(summary["received_count"], 2)
        self.assertEqual(summary["counts_by_status"], {"invalid": 1, "incomplete": 1})
        self.assertEqual([row["source"] for row in summary["rows"]], [self.bad.name, good.name])
        self.assertIsNone(summary["rows"][0]["total_score"])
        self.assertEqual(summary["rows"][1]["total_score"], 0)
        result = json.loads((summary_path.parent / "0001/result.json").read_text(encoding="utf-8"))
        self.assertEqual(result["feedback_code"], "RECEIVED_FILE_INVALID")
        self.assertIsNone(result["score"])
        saved = summary_path.parent / "0002/submission.json"
        self.assertEqual(saved.read_bytes(), original[good.name])
        with (summary_path.parent / "scores.csv").open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["total_score"], "")
        self.assertEqual(float(rows[1]["total_score"]), 0)
        self.assertEqual({path.name: path.read_bytes() for path in self.source.iterdir()}, original)

    def corrupt_deflate(self, member):
        self.write_archive()
        offset = self.member_data_offset(member)
        raw = bytearray(self.bad.read_bytes())
        raw[offset] = (raw[offset] & 0xf8) | 7
        self.bad.write_bytes(raw)
        with zipfile.ZipFile(self.bad) as archive, self.assertRaises(zlib.error):
            archive.read(member)

    def test_corrupt_submission_deflate_does_not_stop_next_submission(self):
        self.corrupt_deflate("submission.json")
        self.assert_batch_continues()

    def test_corrupt_manifest_deflate_does_not_stop_next_submission(self):
        self.corrupt_deflate("manifest.json")
        self.assert_batch_continues()

    def test_crc_mismatch_does_not_stop_next_submission(self):
        self.write_archive(zipfile.ZIP_STORED)
        offset = self.member_data_offset("submission.json")
        raw = bytearray(self.bad.read_bytes())
        raw[offset] ^= 1
        self.bad.write_bytes(raw)
        with zipfile.ZipFile(self.bad) as archive, self.assertRaises(zipfile.BadZipFile):
            archive.read("submission.json")
        self.assert_batch_continues()

    def test_truncated_zip_does_not_stop_next_submission(self):
        self.write_archive()
        self.bad.write_bytes(self.bad.read_bytes()[:-22])
        with self.assertRaises(zipfile.BadZipFile):
            zipfile.ZipFile(self.bad)
        self.assert_batch_continues()

    def test_member_read_eof_does_not_stop_next_submission(self):
        self.write_archive()
        with patch.object(zipfile.ZipExtFile, "read", side_effect=EOFError("archive ended early")):
            self.assert_batch_continues()


if __name__ == "__main__":
    unittest.main()
