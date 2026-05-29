from __future__ import annotations

import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List


def normalize_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def check_import(module_name: str) -> Dict[str, str]:
    spec = importlib.util.find_spec(module_name)
    return {
        "name": f"python module: {module_name}",
        "status": "OK" if spec is not None else "MISSING",
        "detail": "installed" if spec is not None else "not installed",
    }


def check_command(command: str, args: List[str] | None = None, timeout: int = 5) -> Dict[str, str]:
    args = args or ["--version"]
    path = shutil.which(command)
    if path is None:
        return {"name": f"command: {command}", "status": "MISSING", "detail": "not in PATH"}

    try:
        result = subprocess.run([command, *args], capture_output=True, text=True, timeout=timeout)
        first_line = (result.stdout or result.stderr or "").strip().splitlines()
        detail = first_line[0] if first_line else path
        return {"name": f"command: {command}", "status": "OK", "detail": detail}
    except Exception as exc:
        return {"name": f"command: {command}", "status": "WARN", "detail": str(exc)}


def check_path(label: str, raw_path: str, kind: str = "any") -> Dict[str, str]:
    path = Path(normalize_path(raw_path))
    exists = path.exists()
    if kind == "dir":
        ok = exists and path.is_dir()
    elif kind == "file":
        ok = exists and path.is_file()
    else:
        ok = exists
    return {"name": label, "status": "OK" if ok else "MISSING", "detail": str(path)}


def check_ollama(config: Dict[str, Any]) -> Dict[str, str]:
    base_url = config.get("ollama_base_url", "http://localhost:11434").rstrip("/")
    try:
        import requests

        response = requests.get(f"{base_url}/api/tags", timeout=5)
        response.raise_for_status()
        return {"name": "ollama api", "status": "OK", "detail": base_url}
    except Exception as exc:
        return {"name": "ollama api", "status": "MISSING", "detail": str(exc)}


def check_audio_devices() -> Dict[str, str]:
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        input_count = sum(1 for device in devices if int(device.get("max_input_channels", 0)) > 0)
        output_count = sum(1 for device in devices if int(device.get("max_output_channels", 0)) > 0)
        status = "OK" if input_count > 0 and output_count > 0 else "WARN"
        return {
            "name": "audio devices",
            "status": status,
            "detail": f"inputs={input_count}, outputs={output_count}",
        }
    except Exception as exc:
        return {"name": "audio devices", "status": "WARN", "detail": str(exc)}


def run_doctor(config: Dict[str, Any]) -> List[Dict[str, str]]:
    checks: List[Dict[str, str]] = [
        {"name": "computer", "status": "INFO", "detail": os.environ.get("COMPUTERNAME", "<unknown>")},
        {"name": "platform", "status": "INFO", "detail": platform.platform()},
        {"name": "python", "status": "INFO", "detail": sys.version.split()[0]},
        check_path("assistant root", r"C:\Assistant", "dir"),
        check_path("config", r"C:\Assistant\config\config.json", "file"),
        check_path("vosk model", str(config.get("vosk_model_path", "")), "dir"),
        check_ollama(config),
        check_command("code", ["--version"]),
        check_command("es.exe", ["-n", "1", "*.txt"]),
        check_audio_devices(),
    ]

    for module_name in [
        "openwakeword",
        "vosk",
        "sounddevice",
        "requests",
        "rapidfuzz",
        "pyttsx3",
        "pycaw",
        "comtypes",
    ]:
        checks.append(check_import(module_name))

    return checks


def print_doctor_report(checks: List[Dict[str, str]]) -> None:
    print("\nENVIRONMENT DOCTOR")
    print("=" * 70)
    for item in checks:
        print(f"[{item['status']:<7}] {item['name']}: {item['detail']}")
    print("=" * 70)
    missing = [item for item in checks if item["status"] == "MISSING"]
    warn = [item for item in checks if item["status"] == "WARN"]
    print(f"Summary: missing={len(missing)}, warnings={len(warn)}")
