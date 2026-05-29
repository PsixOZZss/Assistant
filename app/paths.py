from pathlib import Path


ASSISTANT_ROOT = Path(r"C:\Assistant")
APP_DIR = ASSISTANT_ROOT / "app"
CONFIG_DIR = ASSISTANT_ROOT / "config"
MODELS_DIR = ASSISTANT_ROOT / "models"
LOGS_DIR = ASSISTANT_ROOT / "logs"
REPORTS_DIR = ASSISTANT_ROOT / "reports"
TEMP_DIR = ASSISTANT_ROOT / "temp"
CONFIG_PATH = CONFIG_DIR / "config.json"
PENDING_ACTION_PATH = TEMP_DIR / "pending_action.json"
PROJECT_INDEX_PATH = TEMP_DIR / "project_index.json"

SAMPLE_RATE = 16000
