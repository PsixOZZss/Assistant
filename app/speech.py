from typing import Any, Callable, Dict

try:
    import pyttsx3
except Exception:
    pyttsx3 = None


LogEvent = Callable[[str, Dict[str, Any]], None]


class Speech:
    def __init__(self, config: Dict[str, Any], log_event: LogEvent, dry_run: bool = False) -> None:
        self.config = config
        self.log_event = log_event
        self.dry_run = dry_run
        self._engine: Any = None

    def init_tts(self) -> Any:
        if self._engine is not None:
            return self._engine

        if pyttsx3 is None:
            print("[TTS] pyttsx3 не установлен или не загрузился.")
            return None

        try:
            engine = pyttsx3.init()
            voice_config = self.config.get("voice", {})
            engine.setProperty("rate", voice_config.get("rate", 185))
            engine.setProperty("volume", voice_config.get("volume", 1.0))
            self._engine = engine
            return engine
        except Exception as exc:
            print("[TTS INIT ERROR]", exc)
            return None

    def speak(self, text: str) -> None:
        print(f"[ASSISTANT]: {text}")
        self.log_event("assistant_speak", {"text": text})

        if self.dry_run or not self.config.get("voice", {}).get("enabled", True):
            return

        engine = self.init_tts()
        if engine is None:
            return

        try:
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            print("[TTS SPEAK ERROR]", exc)
