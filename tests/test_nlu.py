import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from nlu import fallback_intent_parse, parse_json_from_text


class NluFallbackTests(unittest.TestCase):
    def test_create_project_note(self) -> None:
        intent = fallback_intent_parse("создай заметку проекта голосовой ассистент")
        self.assertEqual(intent["action"], "create_note")
        self.assertEqual(intent["query"], "голосовой ассистент")
        self.assertEqual(intent["app"], "project")

    def test_obsidian_review(self) -> None:
        intent = fallback_intent_parse("что надо проверить")
        self.assertEqual(intent["action"], "obsidian_review")

    def test_set_project_alias(self) -> None:
        intent = fallback_intent_parse("запомни проект голосовой ассистент как ассистент")
        self.assertEqual(intent["action"], "set_project_alias")
        self.assertEqual(intent["query"], "голосовой ассистент как ассистент")

    def test_parse_json_from_fenced_text(self) -> None:
        parsed = parse_json_from_text('```json\n{"action":"cancel"}\n```')
        self.assertEqual(parsed, {"action": "cancel"})

    def test_volume_down_with_amount(self) -> None:
        intent = fallback_intent_parse("тише на 25")
        self.assertEqual(intent["action"], "volume_down")
        self.assertEqual(intent["query"], "25")

    def test_media_next(self) -> None:
        intent = fallback_intent_parse("следующий трек")
        self.assertEqual(intent["action"], "media_next")

    def test_pc_restart_requires_confirmation(self) -> None:
        intent = fallback_intent_parse("перезагрузи компьютер")
        self.assertEqual(intent["action"], "pc_restart")
        self.assertTrue(intent["needs_confirmation"])


if __name__ == "__main__":
    unittest.main()
