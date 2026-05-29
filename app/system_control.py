from __future__ import annotations

import ctypes
import re
import subprocess
from typing import Callable


Speak = Callable[[str], None]


def first_int(text: str, default: int = 10) -> int:
    match = re.search(r"\d+", text or "")
    if not match:
        return default
    return max(0, min(100, int(match.group(0))))


def _audio_endpoint():
    from ctypes import POINTER, cast

    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

    devices = AudioUtilities.GetSpeakers()
    interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    return cast(interface, POINTER(IAudioEndpointVolume))


def change_volume(direction: str, amount_text: str, dry_run: bool, speak: Speak) -> int | None:
    amount = first_int(amount_text, default=10)
    direction = (direction or "").lower().strip()
    if direction not in ["up", "down"]:
        speak("Не понял, громкость нужно увеличить или уменьшить.")
        return None

    if dry_run:
        speak(f"Dry-run: изменил бы громкость на {amount} процентов.")
        return None

    volume = _audio_endpoint()
    current = float(volume.GetMasterVolumeLevelScalar())
    delta = amount / 100
    target = current + delta if direction == "up" else current - delta
    target = max(0.0, min(1.0, target))
    volume.SetMasterVolumeLevelScalar(target, None)
    percent = round(target * 100)
    speak(f"Громкость {percent} процентов.")
    return percent


def set_volume(amount_text: str, dry_run: bool, speak: Speak) -> int | None:
    amount = first_int(amount_text, default=50)
    if dry_run:
        speak(f"Dry-run: установил бы громкость на {amount} процентов.")
        return None

    volume = _audio_endpoint()
    volume.SetMasterVolumeLevelScalar(amount / 100, None)
    speak(f"Громкость {amount} процентов.")
    return amount


def set_mute(muted: bool, dry_run: bool, speak: Speak) -> None:
    if dry_run:
        state = "выключил" if muted else "включил"
        speak(f"Dry-run: {state} бы звук.")
        return

    volume = _audio_endpoint()
    volume.SetMute(1 if muted else 0, None)
    speak("Звук выключен." if muted else "Звук включен.")


def send_media_key(key: str, dry_run: bool, speak: Speak) -> None:
    app_commands = {
        "pause": 47,
        "play": 46,
        "next": 11,
        "previous": 12,
    }
    key = (key or "").lower().strip()
    command = app_commands.get(key)
    if command is None:
        speak("Не понял медиакоманду.")
        return

    if dry_run:
        speak(f"Dry-run: нажал бы медиакоманду {key}.")
        return

    ctypes.windll.user32.SendMessageW(0xFFFF, 0x0319, 0, command << 16)
    labels = {
        "pause": "Пауза.",
        "play": "Продолжаю.",
        "next": "Следующий.",
        "previous": "Назад.",
    }
    speak(labels.get(key, "Готово."))


def pc_sleep() -> None:
    subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])


def pc_restart() -> None:
    subprocess.Popen(["shutdown", "/r", "/t", "0"])


def pc_lock() -> None:
    ctypes.windll.user32.LockWorkStation()


def minimize_windows() -> None:
    subprocess.Popen(
        ["powershell", "-NoProfile", "-Command", "(New-Object -ComObject Shell.Application).MinimizeAll()"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
