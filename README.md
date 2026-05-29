# Local PC Assistant

Локальный офлайн-ассистент для Windows-ПК.

Стек: openWakeWord, Vosk, Ollama `qwen3:8b`, Python router, Everything ES, VS Code CLI, PowerShell, pyttsx3, pycaw.

## Запуск

```powershell
cd C:\Assistant
app\.venv\Scripts\python.exe app\assistant.py
```

Тест без микрофона:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "открой загрузки"
```

На тестовом ПК без развёртывания `--dry-run --text` читает локальный `config/config.json` и не требует наличия `C:\Assistant`.

Обновить индекс проектов:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --refresh-project-index
```

Диагностика окружения:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --doctor
```

На тестовом ПК без развёртывания отсутствующие модели, `.venv`, Ollama и внешние инструменты ожидаемы. На основном ПК `--doctor` должен быть первым шагом перед голосовым запуском.

## Голосовой сценарий

1. Скажи wake word: `hey jarvis`.
2. После ответа `Слушаю` скажи команду.
3. Для опасных действий ассистент сначала готовит план и просит подтверждение.

По умолчанию wake word обрабатывает openWakeWord с английской моделью `hey jarvis`. Vosk остаётся для распознавания самой команды и может использоваться как fallback wake engine через `wake_engine: "vosk"` в `config/config.json`; в этом режиме работают wake phrases `компьютер`, `ассистент` или `джарвис`.

Установка зависимостей:

```powershell
app\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Для openWakeWord на основном ПК нужно один раз подготовить/скачать модели при установленном интернете, после чего wake word работает локально. Если нужно полностью уйти в Vosk wake phrase, переключи `wake_engine` на `vosk`.

Подготовить модели openWakeWord:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --download-wake-models
```

## Команды

### open_project

Открывает проект через VS Code.
Если включено `obsidian.auto_project_notes`, при открытии проекта ассистент также гарантирует наличие связанной project note в Obsidian.

Примеры:

- `открой проект голосовой ассистент`
- `открой проект zapret через vscode`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "открой проект голосовой ассистент"
```

### open_folder

Открывает папку по алиасу из `config/config.json` или по явному пути.

Примеры:

- `открой загрузки`
- `открой игры`
- `открой архив`
- `открой проекты`
- `открой бэкапы`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "открой загрузки"
```

### open_app

Запускает программу из allowlist в `config/config.json`.

Примеры:

- `запусти стим`
- `открой браузер`
- `запусти obsidian`
- `открой vscode`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "запусти obsidian"
```

### volume_up / volume_down / volume_set / volume_mute / volume_unmute

Меняет системную громкость через Windows audio endpoint. По умолчанию шаг 10 процентов.

Примеры:

- `громче`
- `тише`
- `громче на 15`
- `тише на 25`
- `громкость на 50`
- `на максимум`
- `на половину`
- `выключи звук`
- `включи звук`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "тише на 25"
```

### media_pause / media_play / media_next / media_previous

Отправляет системные Windows APPCOMMAND для воспроизведения.

Примеры:

- `пауза`
- `стоп`
- `продолжай`
- `дальше`
- `следующий трек`
- `следующий видос`
- `назад`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "следующий трек"
```

### pc_sleep / pc_restart / pc_lock / minimize_windows

Управляет базовыми действиями Windows. Сон и перезагрузка требуют голосового подтверждения.
Перед опасными действиями ассистент проговаривает, что понял, например: `Понял: перезагрузить компьютер.`

Примеры:

- `сон`
- `перезагрузи компьютер`
- `заблокируй компьютер`
- `сверни все окна`
- `покажи рабочий стол`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "сверни все окна"
```

### assistant_status

Показывает и озвучивает краткий статус ассистента: wake engine, модель Ollama, количество проектов в индексе, pending action и состояние голоса.

Примеры:

- `статус ассистента`
- `что с ассистентом`
- `состояние ассистента`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "статус ассистента"
```

### intent_preview

`intent_preview` в `config/config.json` управляет тем, когда ассистент проговаривает распознанное намерение перед выполнением.

По умолчанию preview включён для опасных действий и команд с подтверждением:

```json
"intent_preview": {
  "enabled": true,
  "dangerous_actions": true,
  "needs_confirmation": true,
  "actions": [
    "pc_sleep",
    "pc_restart",
    "confirm_sort_downloads"
  ]
}
```

### confirmation

Подтверждения опасных действий настраиваются в `config/config.json`.

```json
"confirmation": {
  "yes_phrases": ["да", "подтверждаю", "выполняй"],
  "no_phrases": ["нет", "отмена", "отмени"],
  "max_attempts": 2,
  "retry_prompt": "Не понял. Повтори: подтверждаю, или: отмена."
}
```

Если ассистент не понял ответ, он повторит запрос до `max_attempts`, затем отменит действие.

### search_files

Ищет файлы через Everything ES.

Примеры:

- `найди отчет`
- `найди pdf`
- `найди obsidian`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "найди obsidian"
```

### disk_report

Создает отчет по самым большим файлам на дисках.

Примеры:

- `покажи что занимает место`
- `покажи большие файлы`
- `отчет по диску`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "покажи что занимает место"
```

### storage_audit

Проверяет структуру хранения: роли дисков, обязательные папки и алиасы.

Примеры:

- `проверь структуру дисков`
- `аудит структуры`
- `проверь политику хранения`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "проверь структуру дисков"
```

### open_note

Открывает markdown-заметку из Obsidian vault `C:\Knowledge\Brain`.

Примеры:

- `открой заметку карта ПК`
- `открой заметку local pc assistant`
- `покажи заметку кандидаты для Obsidian`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "открой заметку карта ПК"
```

### append_inbox

Добавляет короткую запись в `C:\Knowledge\Brain\00_INBOX\Inbox.md`.

Примеры:

- `запиши в inbox проверить бэкапы`
- `добавь в инбокс настроить алиасы проектов`
- `запомни проверить старые установщики`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "запиши в inbox проверить бэкапы"
```

### refresh_obsidian_inventory

Обновляет:

- `C:\Knowledge\Brain\07_PC\Disks\Кандидаты для Obsidian.md`
- `C:\Assistant\reports\obsidian_candidates.csv`

Примеры:

- `обнови кандидаты для Obsidian`
- `обнови карту Obsidian`
- `обнови обсидиан`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "обнови кандидаты для Obsidian"
```

### create_note

Создает заметку в Obsidian по типу: обычная, проект, программа или папка.

Примеры:

- `создай заметку проекта голосовой ассистент`
- `создай заметку программы Everything`
- `создай заметку папки Downloads`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "создай заметку проекта голосовой ассистент"
```

### obsidian_review

Собирает открытые чекбоксы `- [ ]` из vault и создает обзор в `01_DASHBOARDS`.

Примеры:

- `что надо проверить`
- `обзор Obsidian`
- `покажи задачи`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "что надо проверить"
```

### set_project_alias

Запоминает короткое имя проекта. После этого `open_project` сначала проверяет alias.

Примеры:

- `запомни проект голосовой ассистент как ассистент`
- `запомни проект zapret как запрет`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "запомни проект голосовой ассистент как ассистент"
```

Alias сохраняется в `project_aliases` внутри `config/config.json`.

### prepare_sort_downloads

Готовит план сортировки загрузок. Ничего не перемещает.

Примеры:

- `разбери загрузки`
- `разложи загрузки`
- `подготовь сортировку загрузок`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "разбери загрузки"
```

### confirm_sort_downloads

Выполняет ранее подготовленный план сортировки загрузок после подтверждения.

Примеры:

- `подтверждаю сортировку`
- `выполняй сортировку`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "подтверждаю сортировку"
```

### cancel

Отменяет ожидающее действие.

Примеры:

- `отмена`
- `отмени`
- `стоп`
- `не надо`

CLI:

```powershell
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "отмена"
```

## Безопасность

- Модель не выполняет произвольные команды.
- Модель выбирает только action из `safe_actions`.
- Удаление файлов не реализовано.
- Массовые перемещения идут через план и подтверждение.
- Сон и перезагрузка требуют подтверждения.
- Громкость меняется через `pycaw`, медиакоманды через Windows APPCOMMAND.
- Dry-run планы помечаются и не могут быть случайно выполнены в реальном режиме.

## Как добавлять новые команды

При добавлении нового action обновить:

1. `config/config.json`: добавить action в `safe_actions`.
2. `app/default_config.py`: добавить action в `safe_actions`.
3. `app/nlu.py`: добавить описание action в prompt и fallback-правила, если нужно.
4. `app/actions.py`: реализовать метод действия.
5. `app/assistant.py`: добавить ветку в `route_intent`.
6. `README.md`: добавить раздел с примерами голосовых фраз и CLI.
7. `CHANGELOG.md`: добавить заметное изменение.

Системные действия Windows держать в `app/system_control.py`, а в `app/actions.py` оставлять маршрутизацию, подтверждения, озвучку и логирование.

После изменения проверить:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m py_compile app\assistant.py app\actions.py app\default_config.py app\paths.py app\config_store.py app\project_index.py app\launcher.py app\nlu.py app\speech.py app\doctor.py app\system_control.py
python -m json.tool config\config.json
app\.venv\Scripts\python.exe -m unittest discover -s tests
app\.venv\Scripts\python.exe app\assistant.py --dry-run --text "тестовая команда"
```
