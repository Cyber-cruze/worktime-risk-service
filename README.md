# WorkTime Risk Service

Микросервис для анализа риска выгорания и актуализации рабочего графика сотрудников.  
Использует **прозрачную экспертную систему** (взвешенная формула + правила классификации), что обеспечивает 100% интерпретируемость результатов для HR и тимлидов.

## Tech Stack
- **Backend:** FastAPI + Uvicorn
- **Validation:** Pydantic v2
- **Logic:** Custom Rule Engine & Weighted Scoring
- **Deployment:** Docker

## Быстрый старт

### Вариант 1: Docker
```bash
  docker build -t worktime-risk-service .
  docker run -p 8005:8005 worktime-risk-service
```

### Вариант 2: Локально
```bash
    pip install -r requirements.txt
    uvicorn app.main:app --reload --port 8005
```