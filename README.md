# WorkTime Risk Service

Сервис анализа риска выгорания сотрудников, оценки качества расписания и разрешения конфликтов рабочего календаря. Включает AI-чат-ассистента на базе LLM (Ollama / Qwen 2.5).

## Возможности

- **Анализ риска выгорания** — расчёт метрик (свежесть данных, встречи вне рабочих часов, загрузка, часовой пояс, конфликт HR-календаря) и классификация сотрудника по группе риска
- **Разрешение конфликтов** — автоматический подбор действий (перенос, разделение, делегирование, отмена) для 4 типов конфликтов расписания
- **ML-прогноз** — предсказание вероятности конфликта на 7 дней вперёд
- **Оценка расписания** — скоринг качества (0–100) с буквенной оценкой (A/B/C/D)
- **Обнаружение аномалий** — выявление нетипичных паттернов в графике
- **AI-чат-ассистент** — диалоговый интерфейс на русском языке с автоматическим определением намерения и навигацией по разделам сайта

## API Endpoints

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/health` | Health check |
| `POST` | `/chat` | AI-чат-ассистент |
| `POST` | `/analyze` | Полный анализ риска выгорания |
| `POST` | `/conflicts/resolve` | Разрешение одного конфликта |
| `POST` | `/conflicts/resolve/batch` | Пакетное разрешение конфликтов |
| `POST` | `/ml/predict` | ML-прогноз вероятности конфликта |
| `POST` | `/ml/score` | Оценка качества расписания |
| `POST` | `/ml/anomalies` | Обнаружение аномалий |

Документация Swagger: `http://localhost:8005/docs`

## Быстрый старт

### Локально (без Docker)

```bash
  # Установить зависимости
pip install -r requirements.txt

# Убедиться что Ollama запущен на localhost:11434
ollama serve

# Запустить сервер
uvicorn app.main:app --host 0.0.0.0 --port 8005
```

### Docker

```bash
  # Сборка и запуск
docker compose up -d --build

# Логи
docker compose logs -f
```

## Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | URL Ollama API. В Docker: `http://host.docker.internal:11434/v1` |
| `USE_LLM_RECOMMENDATIONS` | `false` | Включить LLM-генерацию рекомендаций (иначе — шаблонные) |

## Роли

Сервис поддерживает 5 ролей с разным набором разделов и рекомендаций:

| Роль | Код | Описание |
|------|-----|----------|
| Сотрудник | `EMPLOYEE` | Личный профиль, риск, конфликты, задачи |
| Руководитель команды | `TEAM_LEAD` | Дашборд рисков команды, конфликты, календарь |
| HR | `HR` | Аналитика рисков, исключения, сотрудники |
| Project Manager | `PROJECT_MANAGER` | Планирование, встречи, конфликты команды |
| Администратор | `ADMIN` | Мониторинг системы, пользователи, интеграции |

## Типы конфликтов

| Тип | Код | Автодействия |
|-----|-----|-------------|
| Вне рабочих часов | `OUTSIDE_WORK_HOURS` | RESCHEDULE |
| Наложение событий | `OVERLAPPING_EVENTS` | RESCHEDULE, SPLIT |
| Перегрузка | `OVERLOAD` | RESCHEDULE, DELEGATE |
| Конфликт с исключением | `WORKDAY_EXCEPTION_CONFLICT` | KEEP, CANCEL |

## Чат-ассистент

Эндпоинт `POST /chat` принимает вопрос на русском языке, контекст сотрудника и историю сообщений. Автоматически определяет намерение:

| Интент | Пример вопроса |
|--------|---------------|
| `analyze` | «какой у меня риск выгорания?» |
| `conflicts` | «есть ли у меня конфликты?», «помоги разрешить конфликт» |
| `predict` | «какой прогноз конфликтов на неделю?» |
| `score` | «оцени качество моего расписания» |
| `anomalies` | «есть ли аномалии в моём графике?» |
| `navigation` | «где посмотреть конфликты?», «как добавить исключение?» |
| `general` | «что ты умеешь?» |

### Пример запроса

```json
{
  "message": "Есть ли у меня конфликты в расписании?",
  "role": "EMPLOYEE",
  "profile": {
    "name": "Иван",
    "surname": "Иванов",
    "specialization": "Developer",
    "employmentType": "FULL_TIME",
    "workStart": "09:00:00",
    "workEnd": "18:00:00",
    "timezone": "Europe/Moscow",
    "updatedAt": "2026-05-28T10:00:00",
    "userId": 1
  },
  "tasks": [],
  "meetings": [],
  "conflicts": [],
  "hr_data": { "official_schedule": "09:00-18:00", "on_vacation": false },
  "history": []
}
```

### Пример ответа

```json
{
  "answer": "Иван Иванов, у вас нет конфликтов в расписании. Всё в порядке.",
  "tool_used": "conflicts",
  "tool_data": { "status": "NO_CONFLICTS" },
  "history": [...],
  "timestamp": "2026-05-29T12:00:00Z"
}
```

## ML-модели

Предобученные модели в папке `model/`:

| Файл | Назначение |
|------|-----------|
| `conflict_predictor.pkl` | MLPClassifier — прогноз вероятности конфликта |
| `schedule_scorer.pkl` | Регрессор — оценка качества расписания |
| `anomaly_detector.pkl` | Детектор аномалий в графике |

Переобучение моделей:

```bash
  python scripts/train_ml_models.py
```

## Структура проекта

```
app/
  main.py                 # FastAPI приложение, роуты API
  roles.py                # Нормализация ролей
  chat/
    engine.py             # Ядро чат-ассистента (интенты, навигация, LLM)
    router.py             # Роутер /chat
    schemas.py            # Pydantic-схемы запроса/ответа чата
    tools.py              # Внутренние инструменты (analyze, predict, score, anomalies, conflicts)
  conflict/
    resolver.py           # Логика разрешения конфликтов
  llm/
    client.py             # Ollama-клиент (OpenAI-совместимый API)
  metrics/
    freshness.py          # Актуальность данных
    workload.py           # Уровень загрузки
    hr_conflict.py        # Конфликт HR-календаря
    timezone.py           # Часовой пояс (риск)
    date_filter.py        # Фильтрация по датам
  ml/
    predictor.py          # ML-прогноз конфликтов
    scorer.py             # Оценка качества расписания
    anomaly.py            # Детектор аномалий
  models/
    risk_calculator.py    # Расчёт риска выгорания
    classifier.py         # Классификация по группам
  recommendations/
    engine.py             # Генерация рекомендаций
  schemas/
    conflict_schemas.py   # Схемы конфликтов (ConflictType, ProfileSchema, TaskSchema)
    resolution_schemas.py # Схемы ответа разрешения
    input_schemas.py      # Схемы запроса /analyze
    output_schemas.py     # Схемы ответа /analyze
    ml_schemas.py         # Схемы ML-эндпоинтов
    batch_schemas.py      # Схемы batch-разрешения
model/                    # Предобученные .pkl модели
scripts/
  train_ml_models.py      # Скрипт обучения моделей
tests/                    # Unit-тесты
test_pm/                  # JSON-тесткейсы для ручного тестирования
```

## Технологии

- **Python 3.11** + FastAPI
- **Pydantic v2** — валидация данных
- **scikit-learn** — ML-модели (MLPClassifier, Isolation Forest)
- **Ollama** — LLM-инференс (Qwen 2.5:7b для чата, Qwen 2.5:14b для рекомендаций)
- **Docker** — multi-stage build, непривилегированный пользователь