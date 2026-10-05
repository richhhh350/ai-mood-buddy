from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from zipfile import ZipFile

from scripts.build_release import build


class DeliveryTests(unittest.TestCase):
    def test_archive_contains_only_source_and_blank_configuration(self):
        with TemporaryDirectory() as directory:
            output = Path(directory) / "release.zip"
            count, digest = build(output)
            with ZipFile(output) as archive:
                names = archive.namelist()
                self.assertEqual(count, len(names))
                self.assertIn("ai-mood-buddy/.env.example", names)
                self.assertIn("ai-mood-buddy/start.cmd", names)
                self.assertIn("ai-mood-buddy/requirements.lock", names)
                self.assertNotIn("ai-mood-buddy/.env", names)
                self.assertFalse(any("/data/" in name or "/.venv/" in name or "__pycache__" in name for name in names))
                self.assertIsNone(archive.testzip())
            self.assertEqual(64, len(digest))
            self.assertTrue(output.with_suffix(".sha256").exists())
