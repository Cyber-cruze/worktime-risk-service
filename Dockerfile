FROM python:3.11-slim

WORKDIR /app

# Кэшируем установку зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY . .

EXPOSE 8005

# Запуск сервера (0.0.0.0 обязателен для Docker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]