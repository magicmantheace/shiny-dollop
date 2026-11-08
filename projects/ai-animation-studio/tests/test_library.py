import tempfile
import unittest
from pathlib import Path
from studio.library import Library
from studio.cli import load

class LibraryTests(unittest.TestCase):
    def test_registry_and_status_filter(self):
        with tempfile.TemporaryDirectory() as temp:
            lib = Library(Path(temp) / "test.db")
            try:
                lib.init()
                lib.put_asset(load("asset_mug.json"))
                lib.put_character(load("character_traveler.json"))
                lib.put_scene(load("scene_demo.json"))
                self.assertEqual(len(lib.list_assets()), 1)
                self.assertEqual(len(lib.list_assets(approved_only=True)), 0)
                lib.put_asset(load("asset_mug.json"))
                self.assertEqual(len(lib.list_assets()), 1)
            finally:
                lib.close()

if __name__ == "__main__":
    unittest.main()
