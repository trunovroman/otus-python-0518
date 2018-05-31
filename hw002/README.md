# Анализатор логов веб-сервера

## Запуск скрипта

```
python log_analyzer.py [--config CONFIG]
```
`CONFIG` — путь до конфигурационного файла.

## Структура конфигурационного файла

```
{
  "REPORT_SIZE": 50,
  "REPORT_DIR": "./reports",
  "LOG_DIR": "./log",
  "PATTERN_FILE_PATH": "./report.html",
  "ERROR_PERCENT": 10,
  "ROUND_PLACES": 3,
  "LOG_LEVEL": "INFO",
  "LOG_FILE_MASK": "(nginx-access-ui.log-(?P<date>\\d{8}))",
  "LOGGER_FILE_PATH": ""
}
```