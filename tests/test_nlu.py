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


if __name__ == "__main__":
    unittest.main()
