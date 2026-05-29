import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from wake_config import check_openwakeword_config, normalize_openwakeword_config, wake_threshold_hint


class WakeConfigTests(unittest.TestCase):
    def test_normalize_defaults(self) -> None:
        config = normalize_openwakeword_config({})
        self.assertEqual(config["models"], ["hey jarvis"])
        self.assertEqual(config["threshold"], 0.5)
        self.assertEqual(config["frame_ms"], 80)

    def test_threshold_is_clamped(self) -> None:
        low = normalize_openwakeword_config({"openwakeword": {"threshold": -10}})
        high = normalize_openwakeword_config({"openwakeword": {"threshold": 2}})
        self.assertEqual(low["threshold"], 0.05)
        self.assertEqual(high["threshold"], 0.95)

    def test_threshold_hint(self) -> None:
        self.assertIn("sensitive", wake_threshold_hint(0.2))
        self.assertIn("strict", wake_threshold_hint(0.8))
        self.assertEqual(wake_threshold_hint(0.5), "balanced")

    def test_doctor_check(self) -> None:
        item = check_openwakeword_config({"wake_engine": "openwakeword", "openwakeword": {"models": ["hey jarvis"]}})
        self.assertEqual(item["status"], "OK")


if __name__ == "__main__":
    unittest.main()
