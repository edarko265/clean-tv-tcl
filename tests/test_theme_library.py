"""The offline Theme Gallery ships complete, safe packs and stays reachable from Launcher settings."""

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
LIBRARY = ROOT / "theme-library"
SAFE_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,47}\Z")


class ThemeLibraryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads((LIBRARY / "catalog.json").read_text(encoding="utf-8"))
        cls.items = cls.catalog.get("themes", [])

    def test_catalog_is_versioned_and_has_unique_safe_ids(self):
        self.assertEqual(1, self.catalog.get("version"))
        self.assertGreaterEqual(len(self.items), 18)
        ids = [item.get("id") for item in self.items]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertNotIn("personal", ids, "Personal is made privately on the TV, never shipped publicly")
        for item in self.items:
            self.assertRegex(item.get("id", ""), SAFE_ID)
            self.assertTrue(item.get("name", "").strip())
            self.assertTrue(item.get("description", "").strip())

    def test_catalog_and_pack_folders_match_exactly(self):
        folders = {p.name for p in LIBRARY.iterdir() if p.is_dir()}
        self.assertEqual({item["id"] for item in self.items}, folders)

    def test_every_pack_has_a_json_object_and_tv_sized_jpeg(self):
        for item in self.items:
            with self.subTest(theme=item["id"]):
                folder = LIBRARY / item["id"]
                config = json.loads((folder / "config.json").read_text(encoding="utf-8"))
                self.assertIsInstance(config, dict)
                wallpaper = folder / "wallpaper.jpg"
                self.assertTrue(wallpaper.is_file())
                self.assertGreater(wallpaper.stat().st_size, 0)
                self.assertLessEqual(wallpaper.stat().st_size, 300 * 1024)
                self.assertEqual(b"\xff\xd8", wallpaper.read_bytes()[:2])

    def test_launcher_settings_exposes_and_applies_the_gallery(self):
        layout = (ROOT / "launcher/app/src/main/res/layout/activity_launcher_settings.xml").read_text()
        activity = (ROOT / "launcher/app/src/main/java/com/gathin/tvhome/LauncherSettingsActivity.java").read_text()
        provider = (ROOT / "launcher/app/src/main/java/com/gathin/tvhome/ThemeProvider.java").read_text()
        self.assertIn('android:id="@+id/themeChoice"', layout)
        self.assertIn("ThemeLibrary.apply(this, selected.id)", activity)
        self.assertIn("ThemeFiles.libraryPath", provider)

    def test_docs_and_credits_name_the_offline_gallery(self):
        self.assertTrue((LIBRARY / "CREDITS.md").is_file())
        self.assertIn("Theme gallery", (ROOT / "docs/launcher.md").read_text(encoding="utf-8"))
        self.assertIn("tools/theme-library.sh", (ROOT / "README.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
