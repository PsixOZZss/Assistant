import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import assistant


class ConfirmationTests(unittest.TestCase):
    def setUp(self) -> None:
        assistant.CONFIG = {
            "confirmation": {
                "yes_phrases": ["да", "подтверждаю"],
                "no_phrases": ["нет", "отмена"],
            }
        }

    def test_classify_yes(self) -> None:
        self.assertEqual(assistant.classify_confirmation_answer("да подтверждаю"), "yes")

    def test_classify_no(self) -> None:
        self.assertEqual(assistant.classify_confirmation_answer("отмена"), "no")

    def test_classify_empty(self) -> None:
        self.assertEqual(assistant.classify_confirmation_answer(""), "empty")

    def test_classify_unknown(self) -> None:
        self.assertEqual(assistant.classify_confirmation_answer("может быть"), "unknown")


if __name__ == "__main__":
    unittest.main()
