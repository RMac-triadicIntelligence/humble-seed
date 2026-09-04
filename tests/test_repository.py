"""Check the supplied assertion suite and the runner's output-directory boundary."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class RepositoryTests(unittest.TestCase):
    def test_supplied_assertion_suite(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "run.py"), "validate"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Independent v0.6 regression suite: PASS", result.stdout)

    def test_existing_output_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            sentinel = Path(directory) / "keep.txt"
            sentinel.write_text("existing work", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "run.py"), "demo", "--output-dir", directory],
                cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=15,
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "existing work")
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["keep.txt"])


if __name__ == "__main__":
    unittest.main()
