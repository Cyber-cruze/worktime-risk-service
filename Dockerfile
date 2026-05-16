# Используем лёгкий официальный образ Python
FROM python:3.11-slim

# Рабочая директория внутри контейнера
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код проекта
COPY . .

# Открываем порт (должен совпадать с тем, что в uvicorn)
EXPOSE 8005

# Команда запуска сервиса
# 0.0.0.0 важно для работы внутри Docker-сети
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8005"]