import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from rapidfuzz import fuzz, process
except Exception:
    from difflib import SequenceMatcher

    class _FallbackFuzz:
        @staticmethod
        def WRatio(left: str, right: str) -> float:
            return SequenceMatcher(None, left.lower(), right.lower()).ratio() * 100

    class _FallbackProcess:
        @staticmethod
        def extract(query: str, choices: List[str], scorer: Any, limit: int = 10) -> List[Tuple[str, float, int]]:
            matches = [(choice, float(scorer(query, choice)), idx) for idx, choice in enumerate(choices)]
            matches.sort(key=lambda item: item[1], reverse=True)
            return matches[:limit]

    fuzz = _FallbackFuzz()
    process = _FallbackProcess()

from paths import PROJECT_INDEX_PATH, TEMP_DIR


@dataclass
class ProjectItem:
    name: str
    path: str
    marker_score: int
    modified_ts: float


def normalize_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def has_project_marker(folder: Path, config: Dict[str, Any]) -> int:
    markers = config.get("project_scan", {}).get("markers", [])
    score = 0
    for marker in markers:
        if (folder / marker).exists():
            score += 10
    return score


def load_project_index_cache(config: Dict[str, Any]) -> Optional[List[ProjectItem]]:
    if not PROJECT_INDEX_PATH.exists():
        return None

    ttl = int(config.get("project_scan", {}).get("cache_ttl_seconds", 600))
    try:
        data = json.loads(PROJECT_INDEX_PATH.read_text(encoding="utf-8"))
        created_ts = float(data.get("created_ts", 0))
        if time.time() - created_ts > ttl:
            return None
        return [ProjectItem(**item) for item in data.get("projects", [])]
    except Exception as exc:
        print("[PROJECT CACHE READ ERROR]", exc)
        return None


def save_project_index_cache(projects: List[ProjectItem]) -> None:
    try:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        PROJECT_INDEX_PATH.write_text(
            json.dumps(
                {
                    "created_ts": time.time(),
                    "projects": [p.__dict__ for p in projects],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception as exc:
        print("[PROJECT CACHE WRITE ERROR]", exc)


def scan_projects(config: Dict[str, Any], force_refresh: bool = False) -> List[ProjectItem]:
    if not force_refresh:
        cached = load_project_index_cache(config)
        if cached is not None:
            return cached

    roots = config.get("project_roots", [])
    max_depth = int(config.get("project_scan", {}).get("max_depth", 2))
    projects: List[ProjectItem] = []
    seen: set[str] = set()

    def scan_dir(root: Path, depth: int) -> None:
        if depth > max_depth:
            return
        if not root.exists() or not root.is_dir():
            return

        try:
            entries = list(root.iterdir())
        except Exception:
            return

        for item in entries:
            if not item.is_dir():
                continue
            if item.name.startswith(".") and item.name not in [".github"]:
                continue

            item_path = str(item.resolve())
            if item_path in seen:
                continue
            seen.add(item_path)

            marker_score = has_project_marker(item, config)
            try:
                modified_ts = item.stat().st_mtime
            except Exception:
                modified_ts = 0

            if depth == 1 or marker_score > 0:
                projects.append(ProjectItem(item.name, item_path, marker_score, modified_ts))

            if depth < max_depth and item.name.lower() not in [
                "node_modules",
                ".venv",
                "venv",
                "env",
                "dist",
                "build",
                "target",
                "__pycache__",
            ]:
                scan_dir(item, depth + 1)

    for root in roots:
        scan_dir(Path(normalize_path(root)), 1)

    projects.sort(key=lambda p: (p.marker_score, p.modified_ts), reverse=True)
    save_project_index_cache(projects)
    return projects


def fuzzy_project_candidates(query: str, projects: List[ProjectItem], limit: int = 10) -> List[Tuple[ProjectItem, float]]:
    if not query or not projects:
        return []

    choices = [p.name for p in projects]
    raw_matches = process.extract(query, choices, scorer=fuzz.WRatio, limit=limit)

    result: List[Tuple[ProjectItem, float]] = []
    for _name, score, idx in raw_matches:
        project = projects[idx]
        final_score = float(score) + min(project.marker_score, 30)
        result.append((project, final_score))

    result.sort(key=lambda x: x[1], reverse=True)
    return result
