import os
import subprocess
from pathlib import Path
from typing import List, Optional


def run_command(command: str, args: Optional[List[str]] = None, dry_run: bool = False) -> None:
    """Запускает только явно разрешённые команды без shell-интерпретации."""
    args = args or []
    command = (command or "").strip()

    if dry_run:
        print("[DRY RUN COMMAND]", command, args)
        return

    if not command:
        raise ValueError("empty command")

    if "://" in command:
        os.startfile(command)  # type: ignore[attr-defined]
        return

    allowed = {
        "code",
        "msedge",
        "chrome",
        "obsidian",
        "explorer",
        "notepad",
    }
    executable = Path(command).name.lower()
    if executable not in allowed:
        raise ValueError(f"command is not allowlisted: {command}")

    subprocess.Popen([command, *args])


def open_in_notepad(path: Path, dry_run: bool = False) -> None:
    if dry_run:
        print("[DRY RUN OPEN NOTEPAD]", path)
        return
    subprocess.Popen(["notepad", str(path)])


def open_in_explorer(path: Path | str, dry_run: bool = False) -> None:
    if dry_run:
        print("[DRY RUN OPEN EXPLORER]", path)
        return
    subprocess.Popen(["explorer", str(path)])
