"""Synthetic CLI/path checks; no source PDF or extracted source text is used."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "recover.py"
spec = importlib.util.spec_from_file_location("recovery", SCRIPT)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)
SYNTHETIC_SOURCE = b"Synthetic source placeholder, not a PDF.\n"
SYNTHETIC_ROWS = [["Synthetic label", "1.23", None, ""]]


class FakePage:
    def extract_table(self, settings=None):
        return SYNTHETIC_ROWS


class FakePDF:
    pages = {number - 1: FakePage() for number, _, _ in recovery.PAGES}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class RecoveryCLITests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / "synthetic.pdf"
        self.source.write_bytes(SYNTHETIC_SOURCE)
        self.output = self.root / "output"

    def command(self, *args):
        return subprocess.run([sys.executable, "-B", str(SCRIPT), *map(str, args)],
                              capture_output=True, text=True)

    def assert_usage_error(self, result):
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_missing_arguments(self):
        self.assert_usage_error(self.command())

    def test_missing_source(self):
        self.assert_usage_error(self.command(self.root / "missing.pdf", "--output", self.output))
        self.assertFalse(self.output.exists())

    def test_directory_source(self):
        self.assert_usage_error(self.command(self.root, "--output", self.output))
        self.assertFalse(self.output.exists())

    def test_wrong_source_hash(self):
        result = self.command(self.source, "--output", self.output)
        self.assert_usage_error(result)
        self.assertIn("Source hash differs", result.stderr)
        self.assertFalse(self.output.exists())

    def invoke_synthetic(self, source=None, output=None):
        """Exercise main's path/write behavior; this does not validate PDF parsing."""
        source = source if source is not None else self.source
        output = output if output is not None else self.output
        stdout, stderr = io.StringIO(), io.StringIO()
        code = 0
        with patch.object(recovery, "SOURCE_SHA256", hashlib.sha256(SYNTHETIC_SOURCE).hexdigest()), \
             patch.dict(sys.modules, {"pdfplumber": SimpleNamespace(open=lambda _: FakePDF())}), \
             patch.object(sys, "argv", [str(SCRIPT), str(source), "--output", str(output)]), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                recovery.main()
            except SystemExit as error:
                code = error.code
        return SimpleNamespace(returncode=code, stdout=stdout.getvalue(), stderr=stderr.getvalue())

    def test_unicode_paths_and_existing_output_overwrite(self):
        source = self.root / "échantillon 試験.pdf"
        self.source.rename(source)
        output = self.root / "résumé 出力"
        output.mkdir()
        existing = output / "page117-before.json"
        existing.write_text("synthetic old output\n")
        unrelated = output / "unrelated.txt"
        unrelated.write_text("keep me\n")
        result = self.invoke_synthetic(source, output)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(json.loads(result.stdout)), 3)
        self.assertEqual(source.read_bytes(), SYNTHETIC_SOURCE)
        self.assertEqual(unrelated.read_text(), "keep me\n")
        for number, _, _ in recovery.PAGES:
            for label in ("before", "after"):
                self.assertEqual(json.loads((output / f"page{number}-{label}.json").read_text()), SYNTHETIC_ROWS)

    def assert_source_collision_rejected(self, source, output, actual_source):
        sentinel = output / "page117-before.json"
        sentinel.write_text("existing synthetic output\n")
        result = self.invoke_synthetic(source, output)
        self.assert_usage_error(result)
        self.assertIn("overwrite the source", result.stderr)
        self.assertEqual(actual_source.read_bytes(), SYNTHETIC_SOURCE)
        self.assertEqual(sentinel.read_text(), "existing synthetic output\n",
                         "No output may be written before all target paths are checked")
        self.assertFalse((output / "page117-after.json").exists())

    def test_source_named_like_last_output(self):
        self.output.mkdir()
        source = self.output / "page317-after.json"
        self.source.rename(source)
        self.assert_source_collision_rejected(source, self.output, source)

    def test_output_symlink_to_source(self):
        self.output.mkdir()
        (self.output / "page317-after.json").symlink_to(self.source)
        self.assert_source_collision_rejected(self.source, self.output, self.source)

    def test_source_symlink_to_output(self):
        self.output.mkdir()
        actual = self.output / "page317-after.json"
        self.source.rename(actual)
        self.source.symlink_to(actual)
        self.assert_source_collision_rejected(self.source, self.output, actual)

    def test_output_directory_symlink_alias(self):
        actual = self.root / "actual"
        actual.mkdir()
        source = actual / "page317-after.json"
        self.source.rename(source)
        self.output.symlink_to(actual, target_is_directory=True)
        self.assert_source_collision_rejected(source, self.output, source)

    def test_output_hardlink_to_source(self):
        self.output.mkdir()
        (self.output / "page317-after.json").hardlink_to(self.source)
        self.assert_source_collision_rejected(self.source, self.output, self.source)

    def test_last_output_is_symlink_loop(self):
        self.output.mkdir()
        sentinel = self.output / "page117-before.json"
        sentinel.write_text("existing synthetic output\n")
        last = self.output / "page317-after.json"
        last.symlink_to(last.name)
        result = self.invoke_synthetic()
        self.assert_usage_error(result)
        self.assertEqual(self.source.read_bytes(), SYNTHETIC_SOURCE)
        self.assertEqual(sentinel.read_text(), "existing synthetic output\n")
        self.assertFalse((self.output / "page117-after.json").exists())
        self.assertTrue(last.is_symlink())

    def test_output_directory_is_symlink_loop(self):
        self.output.symlink_to(self.output.name, target_is_directory=True)
        result = self.invoke_synthetic()
        self.assert_usage_error(result)
        self.assertEqual(self.source.read_bytes(), SYNTHETIC_SOURCE)
        self.assertTrue(self.output.is_symlink())

    def test_output_path_is_existing_file(self):
        self.output.write_text("synthetic existing file\n")
        result = self.invoke_synthetic()
        self.assert_usage_error(result)
        self.assertEqual(self.output.read_text(), "synthetic existing file\n")
        self.assertEqual(self.source.read_bytes(), SYNTHETIC_SOURCE)


if __name__ == "__main__":
    unittest.main()
