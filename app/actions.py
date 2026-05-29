import os
import csv
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

from rapidfuzz import fuzz

from launcher import open_in_explorer, open_in_notepad, run_command
from nlu import ollama_chat_json
from paths import REPORTS_DIR
from project_index import ProjectItem, fuzzy_project_candidates, scan_projects

Speak = Callable[[str], None]
LogEvent = Callable[[str, Dict[str, Any]], None]
PendingGetter = Callable[[], Optional[Dict[str, Any]]]
PendingSetter = Callable[[Dict[str, Any]], None]
PendingClearer = Callable[[], None]
Confirmation = Callable[[str], bool]
ConfigSaver = Callable[[Dict[str, Any]], None]


def normalize_path(path: str) -> str:
    return os.path.abspath(os.path.expanduser(os.path.expandvars(path)))


def path_is_inside(path: Path, parent: Path) -> bool:
    try:
        child = os.path.abspath(str(path))
        root = os.path.abspath(str(parent))
        return os.path.commonpath([child, root]) == root
    except Exception:
        return False


def make_unique_target_path(target: Path) -> Path:
    if not target.exists():
        return target

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return target.with_name(f"{target.stem}_{stamp}{target.suffix}")


def markdown_title(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").strip()


def safe_note_filename(name: str) -> str:
    cleaned = "".join(ch for ch in name.strip() if ch not in '<>:"/\\|?*')
    cleaned = " ".join(cleaned.split())
    return cleaned or "Untitled"


class AssistantActions:
    def __init__(
        self,
        config: Dict[str, Any],
        speak: Speak,
        log_event: LogEvent,
        dry_run: bool,
        get_pending_action: PendingGetter,
        set_pending_action: PendingSetter,
        clear_pending_action: PendingClearer,
        ask_voice_confirmation: Confirmation,
        save_config: Optional[ConfigSaver] = None,
    ) -> None:
        self.config = config
        self.speak = speak
        self.log_event = log_event
        self.dry_run = dry_run
        self.get_pending_action = get_pending_action
        self.set_pending_action = set_pending_action
        self.clear_pending_action = clear_pending_action
        self.ask_voice_confirmation = ask_voice_confirmation
        self.save_config = save_config

    def note_dir_for_type(self, note_type: str) -> Path:
        obsidian = self.obsidian_config()
        note_type = (note_type or "").lower().strip()
        if note_type in ["project", "проект"]:
            return Path(normalize_path(obsidian.get("project_notes_dir", r"C:\Knowledge\Brain\02_PROJECTS")))
        if note_type in ["software", "app", "program", "программа", "софт"]:
            return Path(normalize_path(obsidian.get("software_notes_dir", r"C:\Knowledge\Brain\07_PC\Software")))
        if note_type in ["folder", "папка"]:
            return Path(normalize_path(obsidian.get("folder_notes_dir", r"C:\Knowledge\Brain\07_PC\Folders")))
        return Path(normalize_path(obsidian.get("inbox_path", r"C:\Knowledge\Brain\00_INBOX\Inbox.md"))).parent

    def note_template(self, note_type: str, title: str, path: str = "") -> str:
        now = datetime.now().isoformat(timespec="seconds")
        note_type = (note_type or "note").lower().strip()
        if note_type in ["project", "проект"]:
            return (
                f"# {title}\n\n"
                f"Тип: проект\nПуть: `{path}`\nСтатус: создано ассистентом\nСоздано: {now}\n\n"
                "## Что это\n\n\n"
                "## Команды запуска\n\n\n"
                "## Связи\n\n- [[../07_PC/Assistant/Local PC Assistant]]\n\n"
                "## Заметки\n\n"
            )
        if note_type in ["software", "app", "program", "программа", "софт"]:
            return (
                f"# {title}\n\n"
                f"Тип: программа\nПуть: `{path}`\nСоздано: {now}\n\n"
                "## Для чего нужна\n\n\n"
                "## Настройки\n\n\n"
                "## Связанные проекты\n\n"
            )
        if note_type in ["folder", "папка"]:
            return (
                f"# {title}\n\n"
                f"Тип: папка\nПуть: `{path}`\nСоздано: {now}\n\n"
                "## Что хранится\n\n\n"
                "## Правила\n\n\n"
                "## Проверить\n\n"
            )
        return f"# {title}\n\nСоздано: {now}\n\n## Заметки\n\n"

    def create_note(self, title: str, note_type: str = "note", path: str = "") -> Optional[Path]:
        title = safe_note_filename(title or "")
        if not title:
            self.speak("Не понял название заметки.")
            return None

        target_dir = self.note_dir_for_type(note_type)
        target_path = target_dir / f"{title}.md"

        if target_path.exists():
            self.speak(f"Заметка уже существует: {title}.")
            open_in_notepad(target_path, dry_run=self.dry_run)
            return target_path

        content = self.note_template(note_type, title, path)

        if self.dry_run:
            print(f"[DRY RUN CREATE NOTE] {target_path}")
            self.speak(f"Dry-run: создал бы заметку {title}.")
            return target_path

        target_dir.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")
        self.speak(f"Создал заметку: {title}.")
        open_in_notepad(target_path, dry_run=self.dry_run)
        self.log_event("create_note", {"title": title, "type": note_type, "path": str(target_path)})
        return target_path

    def llm_select_project(self, query: str, projects: List[ProjectItem]) -> Optional[ProjectItem]:
        if not projects:
            return None

        max_candidates = int(self.config.get("project_scan", {}).get("max_candidates_for_llm", 80))
        fuzzy = fuzzy_project_candidates(query, projects, limit=30)
        recent = sorted(projects, key=lambda p: p.modified_ts, reverse=True)[:30]

        combined: List[ProjectItem] = []
        seen: set[str] = set()

        for p, _score in fuzzy:
            if p.path not in seen:
                combined.append(p)
                seen.add(p.path)

        for p in recent:
            if p.path not in seen:
                combined.append(p)
                seen.add(p.path)

        if len(combined) < min(len(projects), max_candidates):
            for p in projects:
                if p.path not in seen:
                    combined.append(p)
                    seen.add(p.path)
                if len(combined) >= max_candidates:
                    break

        candidates = combined[:max_candidates]
        schema = {
            "type": "object",
            "properties": {
                "selected_path": {"type": "string"},
                "selected_name": {"type": "string"},
                "confidence": {"type": "number"},
                "need_clarification": {"type": "boolean"},
                "reason": {"type": "string"},
            },
            "required": ["selected_path", "selected_name", "confidence", "need_clarification", "reason"],
        }

        project_list_text = "\n".join(
            f"- name: {p.name}\n  path: {p.path}\n  marker_score: {p.marker_score}"
            for p in candidates
        )
        messages = [
            {
                "role": "system",
                "content": (
                    "Ты выбираешь проект на компьютере пользователя. "
                    "Пользователь может говорить по-русски, а папки могут называться по-английски. "
                    "Например: 'голосовой ассистент' может соответствовать 'Voice_Assistant'. "
                    "Выбери один проект только из списка. Если уверенности мало — need_clarification=true. "
                    "Не придумывай путь, которого нет в списке."
                ),
            },
            {
                "role": "user",
                "content": f"Запрос пользователя: {query}\n\nСписок проектов:\n{project_list_text}",
            },
        ]

        result = ollama_chat_json(self.config, messages, schema=schema, timeout=60, log_event=self.log_event)
        print("[PROJECT LLM SELECT]", result)

        if not result or result.get("need_clarification"):
            return None

        confidence = float(result.get("confidence", 0))
        selected_path = str(result.get("selected_path", "")).strip()
        if confidence < 0.55 or not selected_path:
            return None

        selected_path_norm = os.path.abspath(selected_path).lower()
        for p in projects:
            if os.path.abspath(p.path).lower() == selected_path_norm:
                return p

        return None

    def project_aliases(self) -> Dict[str, str]:
        aliases = self.config.setdefault("project_aliases", {})
        return aliases if isinstance(aliases, dict) else {}

    def project_from_alias(self, query: str, projects: List[ProjectItem]) -> Optional[ProjectItem]:
        normalized = (query or "").lower().strip()
        if not normalized:
            return None

        aliases = self.project_aliases()
        selected_path = aliases.get(normalized)
        if not selected_path:
            return None

        selected_path_norm = os.path.abspath(selected_path).lower()
        for project in projects:
            if os.path.abspath(project.path).lower() == selected_path_norm:
                return project

        path = Path(selected_path)
        if path.exists() and path.is_dir():
            return ProjectItem(path.name, str(path.resolve()), 0, path.stat().st_mtime)

        return None

    def ensure_project_note(self, project: ProjectItem) -> Optional[Path]:
        if not self.obsidian_config().get("auto_project_notes", True):
            return None

        title = safe_note_filename(project.name)
        target_dir = self.note_dir_for_type("project")
        target_path = target_dir / f"{title}.md"

        if target_path.exists():
            try:
                text = target_path.read_text(encoding="utf-8")
                if str(project.path) not in text:
                    addition = f"\n\n## Путь\n\n`{project.path}`\n"
                    if not self.dry_run:
                        target_path.write_text(text.rstrip() + addition, encoding="utf-8")
            except Exception:
                pass
            return target_path

        return self.create_note(title=project.name, note_type="project", path=project.path)

    def set_project_alias(self, query: str) -> None:
        query = (query or "").strip()
        separators = ["=>", "|", " как "]
        project_query = ""
        alias = ""

        for sep in separators:
            if sep in query:
                left, right = query.split(sep, 1)
                if sep == " как ":
                    project_query, alias = left.strip(), right.strip()
                else:
                    alias, project_query = left.strip(), right.strip()
                break

        if not project_query or not alias:
            self.speak("Не понял alias. Скажи: запомни проект <проект> как <алиас>.")
            return

        projects = scan_projects(self.config)
        candidates = fuzzy_project_candidates(project_query, projects, limit=5)
        selected = candidates[0][0] if candidates and candidates[0][1] >= 45 else None
        if selected is None:
            self.speak("Не нашёл проект для alias.")
            return

        alias_key = alias.lower().strip()
        if self.dry_run:
            print(f"[DRY RUN SET PROJECT ALIAS] {alias_key} -> {selected.path}")
            self.speak(f"Dry-run: запомнил бы alias {alias} для проекта {selected.name}.")
            return

        aliases = self.project_aliases()
        aliases[alias_key] = selected.path
        self.config["project_aliases"] = aliases
        if self.save_config is not None:
            self.save_config(self.config)

        self.speak(f"Запомнил: {alias} это проект {selected.name}.")
        self.log_event("set_project_alias", {"alias": alias_key, "project": selected.__dict__})

    def open_project(self, query: str, app: str = "vscode") -> None:
        query = (query or "").strip()
        app = (app or "vscode").strip().lower()

        if not query:
            self.speak("Не понял название проекта.")
            return

        projects = scan_projects(self.config)
        if not projects:
            self.speak("Я не нашёл папки проектов. Проверь project_roots в config.json.")
            return

        selected = self.project_from_alias(query, projects)
        candidates = fuzzy_project_candidates(query, projects, limit=5)

        if selected is None and candidates:
            best, best_score = candidates[0]
            second_score = candidates[1][1] if len(candidates) > 1 else 0
            if best_score >= 85 and best_score - second_score >= 10:
                selected = best

        if selected is None:
            selected = self.llm_select_project(query, projects)

        if selected is None and candidates and candidates[0][1] >= 55:
            selected = candidates[0][0]

        if selected is None:
            self.speak("Проект не найден. Я вывел похожие варианты в консоль.")
            print("\n[PROJECT CANDIDATES]")
            for p, score in candidates:
                print(f"- {p.name} | score={score:.1f} | {p.path}")
            return

        path = selected.path
        try:
            if app in ["vscode", "visual studio code", "код", "code", ""]:
                run_command("code", [path], dry_run=self.dry_run)
                self.speak(f"Открываю проект {selected.name} в VS Code.")
            else:
                open_in_explorer(path, dry_run=self.dry_run)
                self.speak(f"Открываю папку проекта {selected.name}.")

            self.ensure_project_note(selected)
            self.log_event("open_project", {"query": query, "selected": selected.__dict__})
        except Exception as exc:
            self.speak("Не получилось открыть проект.")
            print("[OPEN PROJECT ERROR]", exc)
            self.log_event("open_project_error", {"query": query, "error": str(exc)})

    def open_folder(self, query: str) -> None:
        aliases = self.config.get("folder_aliases", {})
        query = (query or "").lower().strip()

        if not query:
            self.speak("Не понял, какую папку открыть.")
            return

        possible_path = Path(normalize_path(query))
        if possible_path.exists() and possible_path.is_dir():
            open_in_explorer(possible_path, dry_run=self.dry_run)
            self.speak("Открываю папку.")
            return

        best_key = None
        best_score = 0
        for key in aliases.keys():
            score = fuzz.WRatio(query, key.lower())
            if score > best_score:
                best_score = score
                best_key = key

        if not best_key or best_score < 50:
            self.speak("Не понял, какую папку открыть.")
            return

        path = Path(normalize_path(aliases[best_key]))
        if not path.exists():
            self.speak(f"Папка не найдена: {path}")
            return

        open_in_explorer(path, dry_run=self.dry_run)
        self.speak(f"Открываю папку: {best_key}.")
        self.log_event("open_folder", {"query": query, "alias": best_key, "path": str(path)})

    def open_app(self, query: str) -> None:
        apps = self.config.get("apps", {})
        query = (query or "").lower().strip()

        if not query:
            self.speak("Не понял, какую программу открыть.")
            return

        best_key = None
        best_score = 0
        for key in apps.keys():
            score = fuzz.WRatio(query, key.lower())
            if score > best_score:
                best_score = score
                best_key = key

        if not best_key or best_score < 50:
            self.speak("Не нашёл такую программу в config.json.")
            return

        command = apps[best_key]
        try:
            run_command(command, dry_run=self.dry_run)
            self.speak(f"Запускаю {best_key}.")
            self.log_event("open_app", {"query": query, "app": best_key, "command": command})
        except Exception as exc:
            self.speak("Не получилось открыть программу.")
            print("[OPEN APP ERROR]", exc)

    def search_files(self, query: str) -> None:
        query = (query or "").strip()
        if not query:
            self.speak("Не понял, что искать.")
            return

        max_results = int(self.config.get("search_max_results", 15))
        report_path = REPORTS_DIR / "search_results.txt"

        try:
            result = subprocess.run(
                ["es.exe", "-n", str(max_results), query],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout.strip()
            error = result.stderr.strip()

            if result.returncode != 0 and error:
                report_path.write_text(error, encoding="utf-8")
                self.speak("Поиск через Everything завершился с ошибкой. Проверь, установлен ли es.exe.")
                open_in_notepad(report_path, dry_run=self.dry_run)
                return

            if not output:
                self.speak("Ничего не нашёл.")
                return

            report_path.write_text(output, encoding="utf-8")
            self.speak("Нашёл файлы. Открываю список результатов.")
            open_in_notepad(report_path, dry_run=self.dry_run)
            self.log_event("search_files", {"query": query, "report": str(report_path)})

        except FileNotFoundError:
            self.speak("Не найден es.exe. Установи Everything ES и добавь его в PATH.")
        except Exception as exc:
            self.speak("Не получилось выполнить поиск.")
            print("[SEARCH ERROR]", exc)

    def obsidian_config(self) -> Dict[str, Any]:
        return self.config.get("obsidian", {})

    def vault_path(self) -> Path:
        return Path(normalize_path(self.obsidian_config().get("vault_path", r"C:\Knowledge\Brain")))

    def find_note_candidates(self, query: str, limit: int = 8) -> List[tuple[Path, float]]:
        vault = self.vault_path()
        if not vault.exists():
            return []

        notes = [p for p in vault.rglob("*.md") if ".obsidian" not in p.parts]
        if not query:
            readme = vault / "README.md"
            return [(readme, 100.0)] if readme.exists() else []

        result: List[tuple[Path, float]] = []
        for note in notes:
            rel = str(note.relative_to(vault))
            title = markdown_title(note)
            score = max(
                fuzz.WRatio(query.lower(), title.lower()),
                fuzz.WRatio(query.lower(), rel.lower()),
            )
            if score >= 45:
                result.append((note, float(score)))

        result.sort(key=lambda item: item[1], reverse=True)
        return result[:limit]

    def open_note(self, query: str) -> None:
        query = (query or "").strip()
        candidates = self.find_note_candidates(query)
        if not candidates:
            self.speak("Не нашёл подходящую заметку в Obsidian.")
            return

        note, score = candidates[0]
        vault = self.vault_path()
        try:
            vault_name = vault.name
            relative = note.relative_to(vault).as_posix()
            url = f"obsidian://open?vault={quote(vault_name)}&file={quote(relative)}"
            run_command(url, dry_run=self.dry_run)
            self.speak(f"Открываю заметку: {note.stem}.")
            self.log_event("open_note", {"query": query, "note": str(note), "score": score})
        except Exception as exc:
            self.speak("Не получилось открыть заметку.")
            print("[OPEN NOTE ERROR]", exc)

    def append_inbox(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            self.speak("Не понял, что записать в Inbox.")
            return

        inbox_path = Path(normalize_path(self.obsidian_config().get("inbox_path", r"C:\Knowledge\Brain\00_INBOX\Inbox.md")))
        inbox_path.parent.mkdir(parents=True, exist_ok=True)
        if not inbox_path.exists():
            inbox_path.write_text("# Inbox\n\n## Неразобранное\n", encoding="utf-8")

        line = f"- [ ] {datetime.now().strftime('%Y-%m-%d %H:%M')} — {text}"
        if self.dry_run:
            print("[DRY RUN APPEND INBOX]", line)
            self.speak("Dry-run: запись была бы добавлена в Inbox.")
            return

        with inbox_path.open("a", encoding="utf-8") as f:
            f.write("\n" + line + "\n")

        self.speak("Записал в Obsidian Inbox.")
        self.log_event("append_inbox", {"text": text, "path": str(inbox_path)})

    def obsidian_review(self) -> None:
        vault = self.vault_path()
        if not vault.exists():
            self.speak("Vault Obsidian не найден.")
            return

        tasks: List[tuple[Path, str]] = []
        for note in vault.rglob("*.md"):
            if ".obsidian" in note.parts:
                continue
            try:
                for line in note.read_text(encoding="utf-8").splitlines():
                    stripped = line.strip()
                    if stripped.startswith("- [ ]"):
                        tasks.append((note, stripped))
            except Exception:
                continue

        review_dir = Path(normalize_path(self.obsidian_config().get("review_dir", r"C:\Knowledge\Brain\01_DASHBOARDS")))
        review_path = review_dir / f"Review {datetime.now().strftime('%Y-%m-%d')}.md"
        lines = [
            f"# Review {datetime.now().strftime('%Y-%m-%d')}",
            "",
            f"Сгенерировано: {datetime.now().isoformat(timespec='seconds')}",
            "",
            "## Открытые задачи",
            "",
        ]

        if not tasks:
            lines.append("Открытых задач не найдено.")
        else:
            for note, task in tasks:
                rel = note.relative_to(vault).as_posix()
                lines.append(f"- {task} ([[{rel[:-3]}]])")

        if self.dry_run:
            print(f"[DRY RUN OBSIDIAN REVIEW] tasks={len(tasks)} note={review_path}")
            self.speak(f"Dry-run: собрал бы обзор Obsidian. Задач: {len(tasks)}.")
            return

        review_dir.mkdir(parents=True, exist_ok=True)
        review_path.write_text("\n".join(lines), encoding="utf-8")
        self.speak(f"Обзор Obsidian готов. Задач: {len(tasks)}.")
        open_in_notepad(review_path, dry_run=self.dry_run)
        self.log_event("obsidian_review", {"tasks": len(tasks), "path": str(review_path)})

    def obsidian_role_for_path(self, path: Path) -> str:
        full = str(path)
        rules = [
            (r"C:\Assistant", "assistant-root-project"),
            (r"C:\Projects", "active-projects"),
            (r"C:\Work", "work"),
            (r"C:\AI", "ai-tools-models"),
            (r"C:\Knowledge", "knowledge-vaults"),
            (r"C:\Tools", "tools"),
            (r"D:\Archive", "archive"),
            (r"D:\Backups", "backups"),
            (r"D:\Media", "media-archive"),
            (r"D:\Old_projects", "old-projects"),
            (r"D:\Old_games", "old-games"),
            (r"D:\Installers", "installers"),
            (r"E:\Downloads", "downloads-inbox"),
            (r"E:\Games", "games"),
            (r"E:\Temp", "temp"),
            (r"E:\Exports", "exports"),
            (r"E:\Scratch", "scratch"),
            (r"E:\Media_Active", "active-media"),
        ]
        for prefix, role in rules:
            if full.lower().startswith(prefix.lower()):
                return role
        return "review"

    def refresh_obsidian_inventory(self) -> None:
        obsidian = self.obsidian_config()
        note_path = Path(normalize_path(obsidian.get("inventory_note_path", r"C:\Knowledge\Brain\07_PC\Disks\Кандидаты для Obsidian.md")))
        csv_path = Path(normalize_path(obsidian.get("inventory_csv_path", r"C:\Assistant\reports\obsidian_candidates.csv")))
        exclude = set(obsidian.get("exclude_top_dirs", []))
        roots = [Path("C:\\"), Path("D:\\"), Path("E:\\")]
        candidates: List[Dict[str, str]] = []

        for root in roots:
            if not root.exists():
                continue
            for item in root.iterdir():
                if not item.is_dir() or item.name in exclude:
                    continue
                role = self.obsidian_role_for_path(item)
                candidates.append({
                    "Type": "top-folder",
                    "Role": role,
                    "Path": str(item),
                    "Name": item.name,
                    "Modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat(timespec="seconds"),
                })

        assistant_root = Path(r"C:\Assistant")
        if assistant_root.exists():
            candidates.append({
                "Type": "project-candidate",
                "Role": "assistant-root-project",
                "Path": str(assistant_root),
                "Name": assistant_root.name,
                "Modified": datetime.fromtimestamp(assistant_root.stat().st_mtime).isoformat(timespec="seconds"),
            })
            for item in assistant_root.iterdir():
                if item.is_dir() and item.name not in exclude:
                    candidates.append({
                        "Type": "software-candidate",
                        "Role": "assistant-module-area",
                        "Path": str(item),
                        "Name": item.name,
                        "Modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat(timespec="seconds"),
                    })

        for root_raw in [r"C:\Projects", r"C:\Work", r"C:\AI", r"D:\Old_projects"]:
            root = Path(root_raw)
            if not root.exists():
                continue
            for item in root.rglob("*"):
                if not item.is_dir() or item.name in exclude:
                    continue
                try:
                    depth = len(item.relative_to(root).parts)
                except Exception:
                    continue
                if depth > 2:
                    continue
                role = "project-note" if any((item / marker).exists() for marker in self.config.get("project_scan", {}).get("markers", [])) else "project-area"
                if role == "project-note" or depth == 1:
                    candidates.append({
                        "Type": "project-candidate",
                        "Role": role,
                        "Path": str(item),
                        "Name": item.name,
                        "Modified": datetime.fromtimestamp(item.stat().st_mtime).isoformat(timespec="seconds"),
                    })

        unique: Dict[tuple[str, str], Dict[str, str]] = {}
        for item in candidates:
            unique[(item["Type"], item["Path"].lower())] = item
        rows = sorted(unique.values(), key=lambda item: (item["Type"], item["Role"], item["Path"]))

        lines: List[str] = [
            "# Кандидаты для Obsidian",
            "",
            "Сгенерировано: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "",
            "Эта заметка ничего не перемещает. Это карта мест, по которым уже можно заводить заметки в Obsidian.",
            "",
            "## Быстрые решения",
            "",
            "- [ ] Для важных проектов создать отдельные заметки по шаблону [[../../09_TEMPLATES/Project]].",
            "- [ ] Для ключевых программ создать заметки по шаблону [[../../09_TEMPLATES/Software]].",
            "- [ ] `C:\\Assistant` вести как корневой проект локального ассистента.",
            "",
        ]

        for group in ["project-candidate", "software-candidate", "top-folder"]:
            group_rows = [item for item in rows if item["Type"] == group]
            if not group_rows:
                continue
            lines.extend([f"## {group}", ""])
            for item in group_rows:
                lines.append(f"- `{item['Path']}` — {item['Role']}")
            lines.append("")

        lines.extend(["## CSV", "", f"Полная таблица: `{csv_path}`"])

        if self.dry_run:
            print(f"[DRY RUN REFRESH OBSIDIAN] rows={len(rows)} note={note_path} csv={csv_path}")
            self.speak(f"Dry-run: обновил бы кандидатов для Obsidian. Найдено: {len(rows)}.")
            return

        note_path.parent.mkdir(parents=True, exist_ok=True)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text("\n".join(lines), encoding="utf-8")
        with csv_path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["Type", "Role", "Path", "Name", "Modified"])
            writer.writeheader()
            writer.writerows(rows)

        self.speak(f"Кандидаты для Obsidian обновлены. Найдено: {len(rows)}.")
        open_in_notepad(note_path, dry_run=self.dry_run)
        self.log_event("refresh_obsidian_inventory", {"count": len(rows), "note": str(note_path), "csv": str(csv_path)})

    def storage_audit(self) -> None:
        policy = self.config.get("storage_policy", {})
        aliases = self.config.get("folder_aliases", {})
        report_path = REPORTS_DIR / f"storage_audit_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"

        lines: List[str] = ["Аудит структуры хранения", f"Дата: {datetime.now().isoformat(timespec='seconds')}", "", "Роли дисков:"]
        for drive, description in policy.get("drives", {}).items():
            lines.append(f"- {drive}: {description}")

        lines.extend(["", "Проверка обязательных папок:"])
        missing_dirs: List[str] = []
        for raw_path in policy.get("required_dirs", []):
            path = Path(normalize_path(raw_path))
            status = "OK" if path.exists() and path.is_dir() else "MISSING"
            if status != "OK":
                missing_dirs.append(str(path))
            lines.append(f"{status}: {path}")

        lines.extend(["", "Проверка алиасов:"])
        mismatched_aliases: List[str] = []
        for alias, expected_raw in policy.get("expected_aliases", {}).items():
            expected = normalize_path(expected_raw)
            actual = normalize_path(aliases.get(alias, ""))
            status = "OK" if actual.lower() == expected.lower() else "MISMATCH"
            if status != "OK":
                mismatched_aliases.append(f"{alias}: сейчас {actual or '<нет>'}, ожидается {expected}")
            lines.append(f"{status}: {alias} -> {actual or '<нет>'} | expected {expected}")

        lines.extend(["", "Рекомендации:"])
        if missing_dirs:
            lines.append("Создать отсутствующие папки:")
            lines.extend(f"- {item}" for item in missing_dirs)
        if mismatched_aliases:
            lines.append("Проверить алиасы в config.json:")
            lines.extend(f"- {item}" for item in mismatched_aliases)
        if not missing_dirs and not mismatched_aliases:
            lines.append("Структура совпадает с текущей политикой хранения.")

        report_path.write_text("\n".join(lines), encoding="utf-8")
        self.speak("Аудит структуры хранения готов. Открываю отчёт.")
        open_in_notepad(report_path, dry_run=self.dry_run)
        self.log_event("storage_audit", {"report": str(report_path), "missing": len(missing_dirs), "mismatches": len(mismatched_aliases)})

    def disk_report(self) -> None:
        roots = self.config.get("disk_report_roots", [r"C:\\", r"D:\\", r"E:\\"])
        top = int(self.config.get("disk_report_top", 50))
        excludes = self.config.get("disk_report_exclude_dirs", [])
        report_path = REPORTS_DIR / f"disk_report_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.txt"

        roots_ps = "@(" + ",".join([f"'{str(r).replace(chr(39), chr(39) + chr(39))}'" for r in roots]) + ")"
        excludes_ps = "@(" + ",".join([f"'{str(e).replace(chr(39), chr(39) + chr(39))}'" for e in excludes]) + ")"

        ps_script = rf"""
$ErrorActionPreference = 'SilentlyContinue'
$roots = {roots_ps}
$excludes = {excludes_ps}
Get-ChildItem -Path $roots -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object {{
        $path = $_.FullName
        foreach ($exclude in $excludes) {{
            if ($path -like "*$exclude*") {{ return $false }}
        }}
        return $true
    }} |
    Sort-Object Length -Descending |
    Select-Object -First {top} @{{Name='GB';Expression={{[math]::Round($_.Length / 1GB, 2)}}}}, FullName, LastWriteTime |
    Format-Table -AutoSize |
    Out-File "{report_path}" -Encoding UTF8
"""

        try:
            self.speak("Готовлю отчёт по самым большим файлам. Это может занять время.")
            subprocess.run(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            if report_path.exists():
                self.speak("Отчёт по диску готов. Открываю.")
                open_in_notepad(report_path, dry_run=self.dry_run)
                self.log_event("disk_report", {"report": str(report_path)})
            else:
                self.speak("Не удалось создать отчёт по диску.")
        except Exception as exc:
            self.speak("Ошибка при создании отчёта по диску.")
            print("[DISK REPORT ERROR]", exc)

    def get_downloads_path(self) -> Path:
        aliases = self.config.get("folder_aliases", {})
        path = aliases.get("загрузки", r"D:\Downloads")
        return Path(normalize_path(path))

    def prepare_sort_downloads(self) -> None:
        downloads = self.get_downloads_path()
        report_path = REPORTS_DIR / "downloads_sort_plan.txt"

        if not downloads.exists():
            self.speak(f"Папка загрузок не найдена: {downloads}")
            return

        rules = self.config.get("downloads_sort_rules", {})
        moves: List[Dict[str, str]] = []
        lines: List[str] = []

        for file in downloads.iterdir():
            if not file.is_file():
                continue

            ext = file.suffix.lower()
            category = "_To_Sort"
            for target_category, extensions in rules.items():
                if ext in [e.lower() for e in extensions]:
                    category = target_category
                    break

            target = downloads / category / file.name
            moves.append({"source": str(file), "target": str(target), "category": category})
            lines.append(f"{file} -> {target}")

        if not moves:
            self.speak("В загрузках нет файлов для сортировки.")
            return

        report_path.write_text("\n".join(lines), encoding="utf-8")
        self.set_pending_action(
            {
                "action": "sort_downloads",
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "downloads": str(downloads),
                "moves": moves,
            }
        )

        self.speak(f"План сортировки готов. Найдено файлов: {len(moves)}. Я ничего не перемещал.")
        self.speak("Открываю план. Для выполнения скажи: подтверждаю сортировку.")
        open_in_notepad(report_path, dry_run=self.dry_run)
        self.log_event("prepare_sort_downloads", {"count": len(moves), "report": str(report_path)})

    def confirm_sort_downloads(self) -> None:
        pending = self.get_pending_action()

        if not pending:
            self.speak("Нет ожидающего действия для подтверждения.")
            return

        if pending.get("action") != "sort_downloads":
            self.speak("Ожидающее действие не является сортировкой загрузок.")
            return

        if pending.get("dry_run") and not self.dry_run:
            self.clear_pending_action()
            self.speak("Это был dry-run план. Я отменил его, подготовь сортировку заново перед реальным переносом.")
            return

        moves = pending.get("moves", [])
        if not moves:
            self.speak("Нет файлов для переноса.")
            self.clear_pending_action()
            return

        downloads = Path(normalize_path(str(pending.get("downloads", self.get_downloads_path()))))
        plan_errors: List[str] = []
        for item in moves:
            source = Path(item.get("source", ""))
            target = Path(item.get("target", ""))
            if not path_is_inside(source, downloads) or not path_is_inside(target, downloads):
                plan_errors.append(f"Путь вне загрузок: {source} -> {target}")
            if not source.exists() or not source.is_file():
                plan_errors.append(f"Исходный файл не найден: {source}")

        if plan_errors:
            error_report = REPORTS_DIR / "downloads_sort_plan_invalid.txt"
            error_report.write_text("\n".join(plan_errors), encoding="utf-8")
            open_in_notepad(error_report, dry_run=self.dry_run)
            self.clear_pending_action()
            self.speak("План сортировки устарел или небезопасен. Я его отменил и открыл отчёт.")
            return

        if self.dry_run:
            self.speak(f"Dry-run: я бы переместил файлов: {len(moves)}. Ничего не меняю.")
            self.log_event("confirm_sort_downloads_dry_run", {"planned": len(moves)})
            return

        if not self.ask_voice_confirmation(f"Я собираюсь переместить {len(moves)} файлов в папке загрузок. Подтвердить?"):
            self.clear_pending_action()
            return

        moved = 0
        errors = 0
        error_lines: List[str] = []

        for item in moves:
            source = Path(item["source"])
            target = Path(item["target"])

            try:
                if not source.exists() or not source.is_file():
                    errors += 1
                    error_lines.append(f"Не найден: {source}")
                    continue

                target.parent.mkdir(parents=True, exist_ok=True)
                target = make_unique_target_path(target)

                shutil.move(str(source), str(target))
                moved += 1

            except Exception as exc:
                errors += 1
                error_lines.append(f"{source} -> {target}: {exc}")
                print("[MOVE ERROR]", source, "->", target, exc)

        self.clear_pending_action()

        if error_lines:
            error_report = REPORTS_DIR / "downloads_sort_errors.txt"
            error_report.write_text("\n".join(error_lines), encoding="utf-8")
            open_in_notepad(error_report, dry_run=self.dry_run)

        self.speak(f"Сортировка завершена. Перемещено файлов: {moved}. Ошибок: {errors}.")
        self.log_event("confirm_sort_downloads", {"moved": moved, "errors": errors})
