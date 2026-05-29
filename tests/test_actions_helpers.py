import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from actions import make_unique_target_path, path_is_inside, safe_note_filename
from system_control import first_int


class ActionHelperTests(unittest.TestCase):
    def test_safe_note_filename_removes_forbidden_chars(self) -> None:
        self.assertEqual(safe_note_filename('Bad:Name*?'), "BadName")

    def test_path_is_inside(self) -> None:
        parent = Path(tempfile.gettempdir())
        child = parent / "assistant-test-child"
        self.assertTrue(path_is_inside(child, parent))

    def test_make_unique_target_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "note.md"
            target.write_text("x", encoding="utf-8")
            unique = make_unique_target_path(target)
            self.assertNotEqual(unique, target)
            self.assertEqual(unique.suffix, ".md")

    def test_first_int(self) -> None:
        self.assertEqual(first_int("тише на 25"), 25)
        self.assertEqual(first_int("без числа", default=10), 10)
        self.assertEqual(first_int("на 500"), 100)


if __name__ == "__main__":
    unittest.main()
