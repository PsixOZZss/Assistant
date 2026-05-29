import json
import re
from typing import Any, Callable, Dict, List, Optional

import requests

from default_config import DEFAULT_CONFIG

LogEvent = Callable[[str, Dict[str, Any]], None]


def parse_json_from_text(text: str) -> Optional[Dict[str, Any]]:
    """На случай если модель вернула JSON внутри текста."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

    return None


def ollama_chat_json(
    config: Dict[str, Any],
    messages: List[Dict[str, str]],
    schema: Dict[str, Any],
    timeout: int = 60,
    log_event: Optional[LogEvent] = None,
) -> Optional[Dict[str, Any]]:
    base_url = config.get("ollama_base_url", "http://localhost:11434").rstrip("/")
    model = config.get("ollama_model", "qwen3:8b")

    payload = {
        "model": model,
        "messages": messages,
        "format": schema,
        "stream": False,
        "options": {"temperature": 0},
    }

    try:
        response = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
        content = data.get("message", {}).get("content", "")
        return parse_json_from_text(content)
    except Exception as exc:
        print("[OLLAMA ERROR]", exc)
        if log_event is not None:
            log_event("ollama_error", {"error": str(exc)})
        return None


def fallback_intent_parse(text: str) -> Dict[str, Any]:
    """Локальные правила на случай, если Ollama недоступна."""
    t = text.lower().strip()
    amount_match = re.search(r"\d+", t)
    amount = amount_match.group(0) if amount_match else "10"

    if any(word in t for word in ["отмена", "отмени", "не надо"]):
        return {"action": "cancel", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback cancel"}

    if any(phrase in t for phrase in ["громче", "увеличь громкость", "прибавь громкость", "сделай громче"]):
        return {"action": "volume_up", "query": amount, "app": "", "needs_confirmation": False, "reason": "fallback volume up"}

    if any(phrase in t for phrase in ["тише", "уменьши громкость", "убавь громкость", "сделай тише"]):
        return {"action": "volume_down", "query": amount, "app": "", "needs_confirmation": False, "reason": "fallback volume down"}

    if any(phrase in t for phrase in ["пауза", "поставь на паузу", "останови воспроизведение", "стоп"]):
        return {"action": "media_pause", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback media pause"}

    if any(phrase in t for phrase in ["продолжай", "продолжить", "возобнови", "воспроизведение"]):
        return {"action": "media_play", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback media play"}

    if any(phrase in t for phrase in ["дальше", "следующий", "следующий клип", "следующий видос", "следующий трек"]):
        return {"action": "media_next", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback media next"}

    if any(phrase in t for phrase in ["назад", "предыдущий", "прошлый трек", "предыдущий трек"]):
        return {"action": "media_previous", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback media previous"}

    if any(phrase in t for phrase in ["сон", "спящий режим", "усыпи компьютер", "переведи в сон"]):
        return {"action": "pc_sleep", "query": "", "app": "", "needs_confirmation": True, "reason": "fallback pc sleep"}

    if any(phrase in t for phrase in ["перезагрузка", "перезагрузи", "перезагрузи компьютер"]):
        return {"action": "pc_restart", "query": "", "app": "", "needs_confirmation": True, "reason": "fallback pc restart"}

    if any(phrase in t for phrase in ["блокировка", "заблокируй", "заблокируй компьютер", "win l", "win+l"]):
        return {"action": "pc_lock", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback pc lock"}

    if any(phrase in t for phrase in ["сверни все окна", "свернуть все окна", "покажи рабочий стол", "рабочий стол"]):
        return {"action": "minimize_windows", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback minimize windows"}

    if "подтверж" in t and "сорт" in t:
        return {"action": "confirm_sort_downloads", "query": "загрузки", "app": "", "needs_confirmation": True, "reason": "fallback confirm sort"}

    if any(phrase in t for phrase in ["разбери загруз", "разложи загруз", "сортируй загруз", "подготовь сорт"]):
        return {"action": "prepare_sort_downloads", "query": "загрузки", "app": "", "needs_confirmation": True, "reason": "fallback prepare sort"}

    if any(phrase in t for phrase in ["что занимает", "большие файлы", "отчёт по диску", "отчет по диску", "место на диске"]):
        return {"action": "disk_report", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback disk report"}

    if any(phrase in t for phrase in ["проверь структуру", "аудит структуры", "проверь диски", "структура дисков", "политика хранения"]):
        return {"action": "storage_audit", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback storage audit"}

    if any(phrase in t for phrase in ["обнови кандидаты", "обнови obsidian", "обнови обсидиан", "обнови карту obsidian", "обнови карту обсидиан"]):
        return {"action": "refresh_obsidian_inventory", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback refresh obsidian inventory"}

    if any(phrase in t for phrase in ["обзор obsidian", "обзор обсидиан", "что надо проверить", "покажи задачи", "собери обзор"]):
        return {"action": "obsidian_review", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback obsidian review"}

    if t.startswith("запомни проект ") and " как " in t:
        q = t.replace("запомни проект", "", 1).strip()
        return {"action": "set_project_alias", "query": q, "app": "", "needs_confirmation": False, "reason": "fallback set project alias"}

    if t.startswith("создай заметку"):
        q = t.replace("создай заметку", "", 1).strip()
        note_type = "note"
        for prefix, detected in [
            ("проекта", "project"),
            ("проект", "project"),
            ("программы", "software"),
            ("программа", "software"),
            ("софта", "software"),
            ("папки", "folder"),
            ("папка", "folder"),
        ]:
            if q.startswith(prefix):
                note_type = detected
                q = q.replace(prefix, "", 1).strip()
                break
        return {"action": "create_note", "query": q, "app": note_type, "needs_confirmation": False, "reason": "fallback create obsidian note"}

    if any(t.startswith(prefix) for prefix in ["запиши в inbox", "запиши в инбокс", "добавь в inbox", "добавь в инбокс", "добавь мысль", "запомни"]):
        q = t
        for prefix in ["запиши в inbox", "запиши в инбокс", "добавь в inbox", "добавь в инбокс", "добавь мысль", "запомни"]:
            q = q.replace(prefix, "", 1).strip(" :")
        return {"action": "append_inbox", "query": q, "app": "", "needs_confirmation": False, "reason": "fallback append inbox"}

    if "заметк" in t and any(word in t for word in ["открой", "покажи", "найди"]):
        q = t
        for token in ["открой", "покажи", "найди", "заметку", "заметка", "заметки", "в obsidian", "в обсидиан"]:
            q = q.replace(token, " ")
        q = re.sub(r"\s+", " ", q).strip()
        return {"action": "open_note", "query": q, "app": "", "needs_confirmation": False, "reason": "fallback open obsidian note"}

    if t.startswith("найди ") or " найти " in f" {t} ":
        q = t.replace("найди", "", 1).strip()
        return {"action": "search_files", "query": q, "app": "", "needs_confirmation": False, "reason": "fallback search"}

    if "проект" in t and any(word in t for word in ["открой", "запусти", "открыть"]):
        q = t
        for token in ["открой", "запусти", "открыть", "проект", "через", "в vscode", "в коде", "код"]:
            q = q.replace(token, " ")
        q = re.sub(r"\s+", " ", q).strip()
        return {"action": "open_project", "query": q, "app": "vscode", "needs_confirmation": False, "reason": "fallback open project"}

    if any(word in t for word in ["открой папку", "открой загруз", "открой архив", "открой игры", "открой проекты", "открой работу"]):
        q = t.replace("открой папку", "").replace("открой", "").strip()
        return {"action": "open_folder", "query": q, "app": "", "needs_confirmation": False, "reason": "fallback open folder"}

    if any(word in t for word in ["запусти", "открой"]):
        q = t.replace("запусти", "").replace("открой", "").strip()
        return {"action": "open_app", "query": q, "app": "", "needs_confirmation": False, "reason": "fallback open app"}

    return {"action": "cancel", "query": "", "app": "", "needs_confirmation": False, "reason": "fallback unknown"}


def call_ollama_for_intent(config: Dict[str, Any], text: str, log_event: LogEvent) -> Dict[str, Any]:
    safe_actions = config.get("safe_actions", DEFAULT_CONFIG["safe_actions"])

    schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": safe_actions},
            "query": {"type": "string"},
            "app": {"type": "string"},
            "needs_confirmation": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["action", "query", "app", "needs_confirmation", "reason"],
    }

    system_prompt = """
Ты локальный голосовой ассистент для Windows-ПК.
Твоя задача — перевести фразу пользователя в JSON-команду.

Разрешённые actions:
- open_project: открыть проект через VS Code. query = название проекта.
- open_folder: открыть папку. query = название папки, например загрузки, архив, игры, проекты.
- open_app: открыть программу. query = название программы, например steam, браузер, obsidian, vscode.
- volume_up: увеличить громкость. query = число процентов, по умолчанию 10.
- volume_down: уменьшить громкость. query = число процентов, по умолчанию 10.
- media_pause: пауза или стоп воспроизведения.
- media_play: продолжить воспроизведение.
- media_next: следующий клип, видос или трек.
- media_previous: предыдущий клип, видос или трек.
- pc_sleep: отправить ПК в сон. needs_confirmation=true.
- pc_restart: перезагрузить ПК. needs_confirmation=true.
- pc_lock: заблокировать ПК.
- minimize_windows: свернуть все окна.
- search_files: найти файлы. query = что искать.
- disk_report: показать, что занимает место на диске.
- storage_audit: проверить структуру хранения, роли дисков, алиасы папок и обязательные папки.
- open_note: открыть markdown-заметку в Obsidian vault. query = название заметки.
- append_inbox: дописать короткую мысль в Obsidian Inbox. query = текст записи.
- refresh_obsidian_inventory: обновить заметку и CSV с кандидатами для Obsidian.
- create_note: создать markdown-заметку в Obsidian. query = название, app = note/project/software/folder.
- obsidian_review: собрать обзор незакрытых задач из Obsidian.
- set_project_alias: запомнить alias для проекта. query = "проект как алиас".
- prepare_sort_downloads: подготовить план сортировки загрузок, ничего не перемещая.
- confirm_sort_downloads: подтвердить ранее подготовленную сортировку загрузок.
- cancel: отменить действие.

Правила безопасности:
- Никогда не возвращай действие для удаления файлов.
- Никогда не возвращай действие для форматирования дисков.
- Никогда не возвращай действие для изменения реестра или системных файлов.
- Если пользователь просит опасное действие, верни action=cancel.
- Сон и перезагрузка разрешены, но только с needs_confirmation=true.
- Для сортировки загрузок сначала prepare_sort_downloads, потом confirm_sort_downloads.

Примеры:
Фраза: "открой проект голосовой ассистент"
JSON: {"action":"open_project","query":"голосовой ассистент","app":"vscode","needs_confirmation":false,"reason":"пользователь хочет открыть проект"}

Фраза: "запусти стим"
JSON: {"action":"open_app","query":"steam","app":"","needs_confirmation":false,"reason":"пользователь хочет открыть программу"}

Фраза: "открой загрузки"
JSON: {"action":"open_folder","query":"загрузки","app":"","needs_confirmation":false,"reason":"пользователь хочет открыть папку"}

Фраза: "громче"
JSON: {"action":"volume_up","query":"10","app":"","needs_confirmation":false,"reason":"пользователь хочет увеличить громкость на стандартный шаг"}

Фраза: "тише на 25"
JSON: {"action":"volume_down","query":"25","app":"","needs_confirmation":false,"reason":"пользователь хочет уменьшить громкость на 25 процентов"}

Фраза: "пауза"
JSON: {"action":"media_pause","query":"","app":"","needs_confirmation":false,"reason":"пользователь хочет поставить воспроизведение на паузу"}

Фраза: "следующий трек"
JSON: {"action":"media_next","query":"","app":"","needs_confirmation":false,"reason":"пользователь хочет следующий трек"}

Фраза: "заблокируй компьютер"
JSON: {"action":"pc_lock","query":"","app":"","needs_confirmation":false,"reason":"пользователь хочет заблокировать ПК"}

Фраза: "перезагрузи компьютер"
JSON: {"action":"pc_restart","query":"","app":"","needs_confirmation":true,"reason":"перезагрузка требует подтверждения"}

Фраза: "разбери загрузки"
JSON: {"action":"prepare_sort_downloads","query":"загрузки","app":"","needs_confirmation":true,"reason":"сначала нужен безопасный план сортировки"}

Фраза: "подтверждаю сортировку"
JSON: {"action":"confirm_sort_downloads","query":"загрузки","app":"","needs_confirmation":true,"reason":"пользователь подтверждает ранее подготовленное действие"}

Фраза: "проверь структуру дисков"
JSON: {"action":"storage_audit","query":"","app":"","needs_confirmation":false,"reason":"пользователь хочет проверить соответствие структуры хранения плану"}

Фраза: "открой заметку карта ПК"
JSON: {"action":"open_note","query":"карта ПК","app":"","needs_confirmation":false,"reason":"пользователь хочет открыть заметку Obsidian"}

Фраза: "запиши в inbox проверить бэкапы"
JSON: {"action":"append_inbox","query":"проверить бэкапы","app":"","needs_confirmation":false,"reason":"пользователь хочет быстро записать мысль"}

Фраза: "обнови кандидаты для Obsidian"
JSON: {"action":"refresh_obsidian_inventory","query":"","app":"","needs_confirmation":false,"reason":"пользователь хочет обновить инвентаризацию для Obsidian"}

Фраза: "создай заметку проекта голосовой ассистент"
JSON: {"action":"create_note","query":"голосовой ассистент","app":"project","needs_confirmation":false,"reason":"пользователь хочет создать проектную заметку"}

Фраза: "что надо проверить"
JSON: {"action":"obsidian_review","query":"","app":"","needs_confirmation":false,"reason":"пользователь хочет обзор открытых задач"}

Фраза: "запомни проект голосовой ассистент как ассистент"
JSON: {"action":"set_project_alias","query":"голосовой ассистент как ассистент","app":"","needs_confirmation":false,"reason":"пользователь хочет добавить alias проекта"}
""".strip()

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Фраза пользователя: {text}"},
    ]

    parsed = ollama_chat_json(config, messages, schema=schema, timeout=60, log_event=log_event)

    if not parsed:
        print("[INTENT] Ollama недоступна или ответ некорректный. Использую fallback.")
        parsed = fallback_intent_parse(text)

    action = parsed.get("action", "cancel")
    if action not in safe_actions:
        parsed = {"action": "cancel", "query": "", "app": "", "needs_confirmation": False, "reason": "action not allowed"}

    parsed.setdefault("query", "")
    parsed.setdefault("app", "")
    parsed.setdefault("needs_confirmation", False)
    parsed.setdefault("reason", "")

    print("[INTENT]", parsed)
    log_event("intent", {"text": text, "intent": parsed})
    return parsed
