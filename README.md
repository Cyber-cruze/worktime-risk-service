# WorkTime Risk Service

ML-микросервис для автоматической оценки риска выгорания сотрудников (WorkTime Sync Case).

Сервис анализирует метрики загрузки (часы, встречи, конфликты) и возвращает **скор риска (0-10)**, прогноз на 3 дня и конкретные рекомендации для тимлида.

## Tech Stack
- **Backend:** Python 3.11 + FastAPI
- **ML:** Scikit-Learn (GradientBoostingRegressor)
- **Deployment:** Docker
- **Validation:** Pydantic

## Быстрый старт

### Вариант 1: Docker (Рекомендуется)
```
# Сборка образа
docker build -t risk-service .

# Запуск (порт 8005)
docker run -p 8005:8005 risk-service
```
### Вариант 2: Локальный запуск
```
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8005
```
