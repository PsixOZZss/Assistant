import json
from typing import Any, Dict

from default_config import DEFAULT_CONFIG
from paths import APP_DIR, ASSISTANT_ROOT, CONFIG_DIR, CONFIG_PATH, LOGS_DIR, MODELS_DIR, REPORTS_DIR, TEMP_DIR


def ensure_base_dirs() -> None:
    for path in [ASSISTANT_ROOT, APP_DIR, CONFIG_DIR, MODELS_DIR, LOGS_DIR, REPORTS_DIR, TEMP_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def write_default_config_if_missing() -> None:
    if CONFIG_PATH.exists():
        return

    CONFIG_PATH.write_text(
        json.dumps(DEFAULT_CONFIG, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[CONFIG] Создан дефолтный config: {CONFIG_PATH}")
    print("[CONFIG] Проверь пути project_roots, folder_aliases и vosk_model_path.")


def deep_merge(default: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
    """Аккуратно добавляет недостающие ключи из DEFAULT_CONFIG."""
    result = dict(default)
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> Dict[str, Any]:
    ensure_base_dirs()
    write_default_config_if_missing()

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        user_config = json.load(f)

    return deep_merge(DEFAULT_CONFIG, user_config)


def save_config(config: Dict[str, Any]) -> None:
    CONFIG_PATH.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
