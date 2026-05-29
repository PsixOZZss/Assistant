"""
Локальный бесплатный офлайн-ассистент для Windows.

Стек:
- openWakeWord или Vosk: wake word / wake phrase офлайн
- Vosk: распознавание команды офлайн
- Ollama + qwen3:8b: понимание команды и перевод в JSON
- Python router: безопасное выполнение только разрешённых действий
- pyttsx3: локальная озвучка ответов
- Everything ES: поиск файлов
- VS Code CLI: открытие проектов
- PowerShell: отчёты по диску

Что умеет:
- "hey jarvis" через openWakeWord или Vosk wake phrases → проснуться
- "открой проект ..." → найти проект и открыть через VS Code
- "открой загрузки / игры / архив / проекты" → открыть папку
- "запусти Steam / браузер / VS Code / Obsidian" → открыть программу
- "найди ..." → поиск через Everything ES
- "покажи что занимает место" → отчёт по большим файлам
- "разбери загрузки" → подготовить план сортировки без перемещения
- "подтверждаю сортировку" → после голосового подтверждения переместить файлы

Безопасность:
- ИИ не выполняет произвольные команды.
- ИИ только выбирает action из белого списка.
- Удаление файлов не реализовано.
- Массовое перемещение требует подтверждения.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from actions import AssistantActions
from config_store import load_config, save_config
from default_config import DEFAULT_CONFIG
from doctor import print_doctor_report, run_doctor
from nlu import call_ollama_for_intent
from paths import (
    CONFIG_PATH,
    LOGS_DIR,
    PENDING_ACTION_PATH,
    SAMPLE_RATE,
    TEMP_DIR,
)
from project_index import scan_projects
from speech import Speech


# ============================================================
# ГЛОБАЛЬНОЕ СОСТОЯНИЕ
# ============================================================

CONFIG: Dict[str, Any] = {}
VOSK_MODEL: Optional[Any] = None
DRY_RUN: bool = False
SPEECH: Optional[Speech] = None
ACTIONS: Optional[AssistantActions] = None


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def log_event(event_type: str, payload: Dict[str, Any]) -> None:
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_path = LOGS_DIR / f"assistant_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        item = {
            "time": now_iso(),
            "type": event_type,
            "payload": payload
        }
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    except Exception as exc:
        print("[LOG ERROR]", exc)


def normalize_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def speak(text: str) -> None:
    if SPEECH is None:
        print(f"[ASSISTANT]: {text}")
        return
    SPEECH.speak(text)


# ============================================================
# VOSK: РАСПОЗНАВАНИЕ РЕЧИ
# ============================================================

def load_vosk_model() -> Any:
    from vosk import Model

    model_path = Path(normalize_path(CONFIG["vosk_model_path"]))

    if not model_path.exists():
        raise FileNotFoundError(
            f"Vosk model не найден: {model_path}\n"
            f"Скачай русскую модель Vosk и распакуй её в C:\\Assistant\\models\\vosk-ru"
        )

    print(f"[VOSK] Загружаю модель: {model_path}")
    return Model(str(model_path))


def listen_text_vosk(seconds: int = 7) -> str:
    """Слушает речь N секунд и возвращает распознанный текст."""
    import sounddevice as sd
    from vosk import KaldiRecognizer

    if VOSK_MODEL is None:
        raise RuntimeError("VOSK_MODEL не загружена")

    audio_queue: queue.Queue[bytes] = queue.Queue()
    recognizer = KaldiRecognizer(VOSK_MODEL, SAMPLE_RATE)

    def callback(indata: bytes, frames: int, time_info: Any, status: Any) -> None:
        if status:
            print("[AUDIO STATUS]", status)
        audio_queue.put(bytes(indata))

    final_parts: List[str] = []

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=callback
    ):
        start = time.time()
        while time.time() - start < seconds:
            try:
                data = audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    final_parts.append(text)

        final = json.loads(recognizer.FinalResult())
        text = final.get("text", "").strip()
        if text:
            final_parts.append(text)

    recognized = " ".join(final_parts).strip()
    print(f"[RECOGNIZED]: {recognized}")
    log_event("recognized_command", {"text": recognized})
    return recognized


def text_has_wake_phrase(text: str) -> bool:
    normalized = text.lower().strip()
    wake_phrases = [p.lower().strip() for p in CONFIG.get("wake_phrases", [])]
    return any(phrase in normalized for phrase in wake_phrases if phrase)


def wait_for_wake_phrase() -> None:
    wake_engine = str(CONFIG.get("wake_engine", "openwakeword")).lower().strip()
    if wake_engine == "openwakeword":
        wait_for_wake_word_openwakeword()
        return

    wait_for_wake_phrase_vosk()


def wait_for_wake_phrase_vosk() -> None:
    """Постоянно слушает микрофон через Vosk и возвращается, когда услышит wake phrase."""
    import sounddevice as sd
    from vosk import KaldiRecognizer

    if VOSK_MODEL is None:
        raise RuntimeError("VOSK_MODEL не загружена")

    audio_queue: queue.Queue[bytes] = queue.Queue()
    recognizer = KaldiRecognizer(VOSK_MODEL, SAMPLE_RATE)

    def callback(indata: bytes, frames: int, time_info: Any, status: Any) -> None:
        if status:
            print("[AUDIO STATUS]", status)
        audio_queue.put(bytes(indata))

    wake_phrases = CONFIG.get("wake_phrases", [])
    print(f"[WAKE] Жду фразу: {', '.join(wake_phrases)}")

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=8000,
        dtype="int16",
        channels=1,
        callback=callback
    ):
        while True:
            data = audio_queue.get()

            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                text = result.get("text", "").strip()
                if text:
                    print(f"[WAKE FINAL]: {text}")
                    if text_has_wake_phrase(text):
                        log_event("wake_detected", {"text": text})
                        return
            else:
                partial = json.loads(recognizer.PartialResult()).get("partial", "").strip()
                if partial and text_has_wake_phrase(partial):
                    print(f"[WAKE PARTIAL]: {partial}")
                    log_event("wake_detected", {"text": partial})
                    return


def wait_for_wake_word_openwakeword() -> None:
    """Постоянно слушает микрофон через openWakeWord и возвращается при wake word."""
    try:
        import numpy as np
        import sounddevice as sd
        from openwakeword.model import Model as WakeWordModel
    except Exception as exc:
        raise RuntimeError(
            "openWakeWord недоступен. Установи зависимость: pip install openwakeword "
            "или переключи config wake_engine на 'vosk'."
        ) from exc

    openwakeword_config = CONFIG.get("openwakeword", {})
    models = openwakeword_config.get("models", ["hey jarvis"])
    threshold = float(openwakeword_config.get("threshold", 0.5))
    frame_ms = int(openwakeword_config.get("frame_ms", 80))
    vad_threshold = openwakeword_config.get("vad_threshold")
    blocksize = max(1, int(SAMPLE_RATE * frame_ms / 1000))

    model_kwargs: Dict[str, Any] = {"wakeword_models": models}
    if vad_threshold is not None:
        model_kwargs["vad_threshold"] = float(vad_threshold)

    print(f"[WAKE] openWakeWord models: {', '.join(models)} | threshold={threshold}")
    wake_model = WakeWordModel(**model_kwargs)

    audio_queue: queue.Queue[bytes] = queue.Queue()

    def callback(indata: bytes, frames: int, time_info: Any, status: Any) -> None:
        if status:
            print("[AUDIO STATUS]", status)
        audio_queue.put(bytes(indata))

    with sd.RawInputStream(
        samplerate=SAMPLE_RATE,
        blocksize=blocksize,
        dtype="int16",
        channels=1,
        callback=callback
    ):
        while True:
            data = audio_queue.get()
            frame = np.frombuffer(data, dtype=np.int16)
            predictions = wake_model.predict(frame)

            for name, score in predictions.items():
                score_float = float(score)
                if score_float >= threshold:
                    print(f"[WAKE OPENWAKEWORD]: {name} score={score_float:.3f}")
                    log_event("wake_detected", {"engine": "openwakeword", "model": name, "score": score_float})
                    return


# ============================================================
# CONFIRMATION / PENDING ACTIONS
# ============================================================

def is_confirmation_yes(text: str) -> bool:
    text = text.lower().strip()
    phrases = CONFIG.get("confirmation", {}).get("yes_phrases", [])
    return any(phrase in text for phrase in phrases)


def is_confirmation_no(text: str) -> bool:
    text = text.lower().strip()
    phrases = CONFIG.get("confirmation", {}).get("no_phrases", [])
    return any(phrase in text for phrase in phrases)


def ask_voice_confirmation(message: str) -> bool:
    seconds = int(CONFIG.get("confirmation_listen_seconds", 5))

    speak(message)
    speak("Скажи: подтверждаю, или скажи: отмена.")

    answer = listen_text_vosk(seconds=seconds)
    print("[CONFIRMATION ANSWER]", answer)
    log_event("confirmation_answer", {"answer": answer})

    if is_confirmation_yes(answer):
        speak("Подтверждение получено.")
        return True

    if is_confirmation_no(answer):
        speak("Действие отменено.")
        return False

    speak("Я не понял подтверждение. Действие отменено.")
    return False


def set_pending_action(action: Dict[str, Any]) -> None:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    if DRY_RUN:
        action = dict(action)
        action["dry_run"] = True
    PENDING_ACTION_PATH.write_text(
        json.dumps(action, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log_event("pending_action_set", action)


def get_pending_action() -> Optional[Dict[str, Any]]:
    if not PENDING_ACTION_PATH.exists():
        return None

    try:
        pending = json.loads(PENDING_ACTION_PATH.read_text(encoding="utf-8"))
        created_at = pending.get("created_at")
        ttl = int(CONFIG.get("pending_action_ttl_seconds", 900))
        if created_at:
            try:
                created = datetime.fromisoformat(str(created_at))
                if (datetime.now() - created).total_seconds() > ttl:
                    clear_pending_action()
                    speak("Ожидающее действие устарело. Я его отменил.")
                    return None
            except Exception:
                clear_pending_action()
                return None
        return pending
    except Exception as exc:
        print("[PENDING READ ERROR]", exc)
        return None


def clear_pending_action() -> None:
    try:
        if PENDING_ACTION_PATH.exists():
            PENDING_ACTION_PATH.unlink()
        log_event("pending_action_cleared", {})
    except Exception as exc:
        print("[PENDING CLEAR ERROR]", exc)


# ============================================================
# ROUTER
# ============================================================

def action_is_dangerous(action: str) -> bool:
    return action in CONFIG.get("dangerous_actions", [])


def route_intent(intent: Dict[str, Any]) -> None:
    if ACTIONS is None:
        speak("Действия ещё не инициализированы.")
        return

    action = intent.get("action", "cancel")
    query = intent.get("query", "")
    app = intent.get("app", "")

    safe_actions = CONFIG.get("safe_actions", [])

    if action not in safe_actions:
        speak("Команда не разрешена.")
        log_event("blocked_action", intent)
        return

    if action_is_dangerous(action):
        log_event("dangerous_action_requested", intent)

    if action == "open_project":
        ACTIONS.open_project(query=query, app=app or "vscode")

    elif action == "open_folder":
        ACTIONS.open_folder(query=query)

    elif action == "open_app":
        ACTIONS.open_app(query=query)

    elif action == "volume_up":
        ACTIONS.change_volume(direction="up", amount_text=query)

    elif action == "volume_down":
        ACTIONS.change_volume(direction="down", amount_text=query)

    elif action == "volume_set":
        ACTIONS.set_volume(amount_text=query)

    elif action == "volume_mute":
        ACTIONS.set_mute(True)

    elif action == "volume_unmute":
        ACTIONS.set_mute(False)

    elif action == "media_pause":
        ACTIONS.send_media_key("pause")

    elif action == "media_play":
        ACTIONS.send_media_key("play")

    elif action == "media_next":
        ACTIONS.send_media_key("next")

    elif action == "media_previous":
        ACTIONS.send_media_key("previous")

    elif action == "pc_sleep":
        ACTIONS.pc_sleep()

    elif action == "pc_restart":
        ACTIONS.pc_restart()

    elif action == "pc_lock":
        ACTIONS.pc_lock()

    elif action == "minimize_windows":
        ACTIONS.minimize_windows()

    elif action == "assistant_status":
        ACTIONS.assistant_status()

    elif action == "search_files":
        ACTIONS.search_files(query=query)

    elif action == "disk_report":
        ACTIONS.disk_report()

    elif action == "storage_audit":
        ACTIONS.storage_audit()

    elif action == "open_note":
        ACTIONS.open_note(query=query)

    elif action == "append_inbox":
        ACTIONS.append_inbox(text=query)

    elif action == "refresh_obsidian_inventory":
        ACTIONS.refresh_obsidian_inventory()

    elif action == "create_note":
        ACTIONS.create_note(title=query, note_type=app or "note")

    elif action == "obsidian_review":
        ACTIONS.obsidian_review()

    elif action == "set_project_alias":
        ACTIONS.set_project_alias(query=query)

    elif action == "prepare_sort_downloads":
        ACTIONS.prepare_sort_downloads()

    elif action == "confirm_sort_downloads":
        ACTIONS.confirm_sort_downloads()

    elif action == "cancel":
        clear_pending_action()
        speak("Отменяю.")

    else:
        speak("Я пока не умею выполнять такую команду.")


# ============================================================
# ДИАГНОСТИКА
# ============================================================

def print_startup_info() -> None:
    print("\n" + "=" * 70)
    print("LOCAL PC VOICE ASSISTANT")
    print("=" * 70)
    print(f"Config: {CONFIG_PATH}")
    print(f"Vosk model: {CONFIG.get('vosk_model_path')}")
    print(f"Ollama: {CONFIG.get('ollama_base_url')} | model: {CONFIG.get('ollama_model')}")
    print(f"Wake engine: {CONFIG.get('wake_engine', 'openwakeword')}")
    print(f"Wake phrases: {', '.join(CONFIG.get('wake_phrases', []))}")
    print("Project roots:")
    for root in CONFIG.get("project_roots", []):
        print(f"  - {root}")
    print("=" * 70 + "\n")


def check_ollama_available() -> bool:
    import requests

    base_url = CONFIG.get("ollama_base_url", "http://localhost:11434").rstrip("/")
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        response.raise_for_status()
        return True
    except Exception:
        return False


def check_external_tools() -> None:
    # VS Code CLI
    try:
        subprocess.run(["code", "--version"], capture_output=True, text=True, timeout=5)
    except Exception:
        print("[CHECK] Команда 'code' может быть недоступна. Проверь VS Code CLI.")

    # Everything ES
    try:
        subprocess.run(["es.exe", "-n", "1", "*.txt"], capture_output=True, text=True, timeout=5)
    except Exception:
        print("[CHECK] es.exe может быть недоступен. Поиск файлов через Everything не заработает.")

    # Ollama
    if not check_ollama_available():
        print("[CHECK] Ollama API недоступен. Ассистент будет использовать fallback-правила.")
        print("[CHECK] Запусти Ollama и скачай модель: ollama pull qwen3:8b")


def download_openwakeword_models() -> None:
    try:
        from openwakeword import utils as openwakeword_utils
    except Exception as exc:
        raise RuntimeError("openWakeWord не установлен. Установи зависимости из requirements.txt.") from exc

    print("[OPENWAKEWORD] Скачиваю/проверяю предобученные модели.")
    openwakeword_utils.download_models()
    speak("Модели openWakeWord подготовлены.")


# ============================================================
# MAIN LOOP
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Локальный голосовой ассистент для Windows-ПК.")
    parser.add_argument("--text", help="Выполнить одну текстовую команду без микрофона.")
    parser.add_argument("--dry-run", action="store_true", help="Показать намерение и планы без запуска программ и переноса файлов.")
    parser.add_argument("--refresh-project-index", action="store_true", help="Пересканировать проекты и обновить кэш.")
    parser.add_argument("--download-wake-models", action="store_true", help="Скачать предобученные модели openWakeWord для офлайн-работы.")
    parser.add_argument("--doctor", action="store_true", help="Проверить окружение без запуска голосового цикла.")
    return parser.parse_args()


def load_config_for_doctor() -> Dict[str, Any]:
    local_config = Path(__file__).resolve().parents[1] / "config" / "config.json"
    if local_config.exists():
        try:
            with local_config.open("r", encoding="utf-8") as f:
                user_config = json.load(f)
            merged = dict(DEFAULT_CONFIG)
            for key, value in user_config.items():
                merged[key] = value
            return merged
        except Exception as exc:
            print("[DOCTOR CONFIG ERROR]", exc)
    return dict(DEFAULT_CONFIG)


def run_text_command(text: str) -> None:
    intent = call_ollama_for_intent(CONFIG, text, log_event)
    route_intent(intent)


def main() -> None:
    global CONFIG, VOSK_MODEL, DRY_RUN, SPEECH, ACTIONS

    args = parse_args()
    DRY_RUN = bool(args.dry_run)

    if args.doctor and not args.text and not args.refresh_project_index and not args.download_wake_models:
        CONFIG = load_config_for_doctor()
        print_doctor_report(run_doctor(CONFIG))
        return

    CONFIG = load_config()
    SPEECH = Speech(CONFIG, log_event, dry_run=DRY_RUN)
    ACTIONS = AssistantActions(
        CONFIG,
        speak=speak,
        log_event=log_event,
        dry_run=DRY_RUN,
        get_pending_action=get_pending_action,
        set_pending_action=set_pending_action,
        clear_pending_action=clear_pending_action,
        ask_voice_confirmation=ask_voice_confirmation,
        save_config=save_config,
    )
    print_startup_info()

    if args.doctor:
        print_doctor_report(run_doctor(CONFIG))
        if not args.text and not args.refresh_project_index and not args.download_wake_models:
            return

    if args.download_wake_models:
        download_openwakeword_models()
        if not args.text and not args.refresh_project_index:
            return

    if args.refresh_project_index:
        projects = scan_projects(CONFIG, force_refresh=True)
        speak(f"Индекс проектов обновлён. Найдено проектов: {len(projects)}.")
        if not args.text:
            return

    if args.text:
        run_text_command(args.text)
        return

    check_external_tools()

    VOSK_MODEL = load_vosk_model()

    speak("Ассистент запущен.")

    while True:
        try:
            wait_for_wake_phrase()
            speak("Слушаю.")

            seconds = int(CONFIG.get("command_listen_seconds", 7))
            command_text = listen_text_vosk(seconds=seconds)

            if not command_text:
                speak("Я не расслышал команду.")
                continue

            intent = call_ollama_for_intent(CONFIG, command_text, log_event)
            route_intent(intent)

        except KeyboardInterrupt:
            print("\n[EXIT] Остановка ассистента.")
            speak("Ассистент остановлен.")
            break
        except Exception as exc:
            print("[MAIN LOOP ERROR]", exc)
            log_event("main_loop_error", {"error": str(exc)})
            speak("Произошла ошибка. Я продолжаю работу.")
            time.sleep(1)


if __name__ == "__main__":
    main()

