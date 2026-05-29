# Changelog

Все заметные изменения проекта фиксируются здесь. Формат: новые записи сверху.

## Unreleased

- Добавлен `intent_preview`: ассистент проговаривает распознанное намерение перед опасными действиями и подтверждениями.
- `--dry-run --text` на тестовом ПК использует локальный `config/config.json` и не требует создания `C:\Assistant`.

## 2026-05-29 - Diagnostics And Status

- Добавлена диагностика окружения `--doctor`.
- Улучшено управление громкостью: `volume_set`, `volume_mute`, `volume_unmute`, максимум, половина и живые fallback-фразы.
- Добавлена команда `assistant_status`.
- Системные действия вынесены в `app/system_control.py`.

## 2026-05-29 - Test Branch

### Added

- Добавлен `AGENTS.md` как рабочая инструкция проекта.
- Добавлен `requirements.txt`.
- Добавлен openWakeWord как основной wake engine с моделью `hey jarvis`.
- Добавлен fallback wake engine через Vosk wake phrases.
- Добавлена команда `--download-wake-models`.
- Добавлены базовые системные команды:
  - `volume_up`, `volume_down`;
  - `media_pause`, `media_play`, `media_next`, `media_previous`;
  - `pc_sleep`, `pc_restart`, `pc_lock`, `minimize_windows`.
- Добавлены fallback NLU-тесты для громкости, media next и перезагрузки.

### Changed

- `README.md` и `AGENTS.md` обновлены под разработку на двух ПК.
- Сон и перезагрузка помечены как опасные действия и требуют подтверждения.

### Notes

- На тестовом ПК `QUAQUA` выполняются только гипотетические/лёгкие проверки без развёртывания голосового и AI-стека.
