import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import assistant


class IntentPreviewTests(unittest.TestCase):
    def setUp(self) -> None:
        assistant.CONFIG = {
            "dangerous_actions": ["pc_restart"],
            "intent_preview": {
                "enabled": True,
                "dangerous_actions": True,
                "needs_confirmation": True,
                "actions": ["confirm_sort_downloads"],
            },
        }

    def test_describe_restart(self) -> None:
        self.assertEqual(
            assistant.describe_intent({"action": "pc_restart"}),
            "Понял: перезагрузить компьютер.",
        )

    def test_should_preview_dangerous(self) -> None:
        self.assertTrue(assistant.should_preview_intent({"action": "pc_restart"}))

    def test_should_preview_confirmation(self) -> None:
        self.assertTrue(assistant.should_preview_intent({"action": "pc_sleep", "needs_confirmation": True}))

    def test_should_not_preview_normal_action(self) -> None:
        self.assertFalse(assistant.should_preview_intent({"action": "media_next"}))


if __name__ == "__main__":
    unittest.main()
