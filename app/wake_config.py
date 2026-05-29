from __future__ import annotations

from typing import Any, Dict, List


DEFAULT_OPENWAKEWORD_MODELS = ["hey jarvis"]
DEFAULT_OPENWAKEWORD_THRESHOLD = 0.5
DEFAULT_OPENWAKEWORD_FRAME_MS = 80


def normalize_openwakeword_config(config: Dict[str, Any]) -> Dict[str, Any]:
    raw = config.get("openwakeword", {})
    raw_models = raw.get("models", DEFAULT_OPENWAKEWORD_MODELS)
    if isinstance(raw_models, str):
        models = [raw_models]
    else:
        models = [str(item).strip() for item in raw_models if str(item).strip()]
    if not models:
        models = list(DEFAULT_OPENWAKEWORD_MODELS)

    try:
        threshold = float(raw.get("threshold", DEFAULT_OPENWAKEWORD_THRESHOLD))
    except Exception:
        threshold = DEFAULT_OPENWAKEWORD_THRESHOLD
    threshold = max(0.05, min(0.95, threshold))

    try:
        frame_ms = int(raw.get("frame_ms", DEFAULT_OPENWAKEWORD_FRAME_MS))
    except Exception:
        frame_ms = DEFAULT_OPENWAKEWORD_FRAME_MS
    frame_ms = max(20, min(200, frame_ms))

    vad_threshold = raw.get("vad_threshold")
    if vad_threshold is not None:
        try:
            vad_threshold = max(0.0, min(1.0, float(vad_threshold)))
        except Exception:
            vad_threshold = None

    return {
        "models": models,
        "threshold": threshold,
        "frame_ms": frame_ms,
        "vad_threshold": vad_threshold,
    }


def wake_threshold_hint(threshold: float) -> str:
    if threshold < 0.35:
        return "sensitive; raise toward 0.5-0.65 if false wakeups happen"
    if threshold > 0.7:
        return "strict; lower toward 0.45-0.6 if wake word is missed"
    return "balanced"


def check_openwakeword_config(config: Dict[str, Any]) -> Dict[str, str]:
    if str(config.get("wake_engine", "openwakeword")).lower().strip() != "openwakeword":
        return {"name": "openWakeWord config", "status": "INFO", "detail": "wake_engine is not openwakeword"}

    normalized = normalize_openwakeword_config(config)
    threshold = float(normalized["threshold"])
    detail = (
        f"models={', '.join(normalized['models'])}; "
        f"threshold={threshold}; frame_ms={normalized['frame_ms']}; "
        f"vad_threshold={normalized['vad_threshold']}; {wake_threshold_hint(threshold)}"
    )

    status = "OK"
    raw = config.get("openwakeword", {})
    if raw.get("models") in [[], "", None]:
        status = "WARN"
        detail += "; no models configured, using default"

    return {"name": "openWakeWord config", "status": status, "detail": detail}
