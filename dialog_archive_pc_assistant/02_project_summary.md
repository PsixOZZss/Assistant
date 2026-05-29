# Краткая выжимка проекта

## Финальная цель

Собрать локального бесплатного офлайн-ассистента для Windows-ПК, который:
- просыпается по фразе;
- распознаёт команду голосом;
- открывает проекты через VS Code;
- открывает папки и программы;
- ищет файлы через Everything;
- показывает отчёты по занятому месту;
- готовит сортировку загрузок;
- выполняет опасные действия только после голосового подтверждения.

## Финальная архитектура ассистента

```text
Vosk wake phrase
↓
Vosk command recognition
↓
Ollama qwen3:8b
↓
Python router
↓
PowerShell / Everything / VS Code
↓
pyttsx3 voice response
```

## Почему без Porcupine

Porcupine был убран, потому что для полностью бесплатной офлайн-системы нежелательны AccessKey, аккаунты и внешние ограничения.

## Финальный стек

```text
Vosk
Ollama qwen3:8b
Python
Everything + ES
VS Code CLI
PowerShell
pyttsx3
rapidfuzz
sounddevice
requests
```

## Безопасность

ИИ не выполняет произвольные команды. Он только возвращает JSON-намерение.

Разрешённые действия:
```text
open_project
open_folder
open_app
search_files
disk_report
prepare_sort_downloads
confirm_sort_downloads
cancel
```

Запрещено:
```text
удаление файлов
форматирование дисков
изменение системных папок
изменение реестра
запуск произвольной команды от модели
```

## Структура дисков

```text
C: SSD 1 ТБ — система, программы, проекты, ИИ, граф знаний
D: SSD 0.5 ТБ — игры, загрузки, временное, экспорты
E: HDD 1 ТБ — архив, бэкапы, старые проекты, медиа
```

## Структура ассистента

```text
C:\Assistant
  app
  config
  models
  logs
  reports
  temp
```

## Ключевые команды запуска

```powershell
cd C:\Assistant\app
python -m venv .venv
.\.venv\Scripts\activate
pip install vosk sounddevice requests rapidfuzz pyttsx3
```

```powershell
ollama pull qwen3:8b
ollama run qwen3:8b
```

```powershell
python assistant.py
```
