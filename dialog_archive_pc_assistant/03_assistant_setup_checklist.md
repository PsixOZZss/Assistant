# Чеклист настройки офлайн-ассистента

## 1. Папки

```powershell
mkdir C:\Assistant
mkdir C:\Assistant\app
mkdir C:\Assistant\config
mkdir C:\Assistant\models
mkdir C:\Assistant\logs
mkdir C:\Assistant\reports
mkdir C:\Assistant\temp
```

## 2. Python

Проверить:

```powershell
python --version
pip --version
```

Создать окружение:

```powershell
cd C:\Assistant\app
python -m venv .venv
.\.venv\Scripts\activate
pip install vosk sounddevice requests rapidfuzz pyttsx3
```

## 3. Ollama

```powershell
ollama pull qwen3:8b
ollama run qwen3:8b
```

Проверить:

```powershell
curl http://localhost:11434/api/tags
```

## 4. Vosk

Скачать русскую модель и распаковать:

```text
C:\Assistant\models\vosk-ru
```

## 5. VS Code CLI

Проверить:

```powershell
code --version
```

Если не работает:
- открыть VS Code;
- `Ctrl + Shift + P`;
- найти `Shell Command: Install 'code' command in PATH`.

## 6. Everything + ES

Проверить:

```powershell
es.exe *.pdf
```

## 7. config.json

Создать:

```text
C:\Assistant\config\config.json
```

## 8. assistant.py

Положить файл:

```text
C:\Assistant\app\assistant.py
```

## 9. Первый запуск

```powershell
cd C:\Assistant\app
.\.venv\Scripts\activate
python assistant.py
```

## 10. Тестовые фразы

```text
компьютер
открой загрузки
```

```text
компьютер
открой проект ассистент
```

```text
компьютер
покажи что занимает место
```

```text
компьютер
разбери загрузки
```

## 11. Автозапуск

Создать:

```text
C:\Assistant\start_assistant.bat
```

Содержимое:

```bat
@echo off
cd /d C:\Assistant\app
call .venv\Scripts\activate
python assistant.py
```

Положить ярлык в:

```text
Win + R → shell:startup
```
