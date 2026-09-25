FROM python:3.11-slim

# Установка системных зависимостей для сборки, работы с шрифтами и сетью
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    fonts-dejavu-core \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY SHARED/ /app/SHARED/
COPY CARTRIDGE/ /app/CARTRIDGE/
COPY REPAIR/ /app/REPAIR/
COPY LOCATION/ /app/LOCATION/
COPY PORTAL/ /app/PORTAL/
COPY BD/ /app/BD/
COPY main_server.py /app/main_server.py

# Создание папок для БД
RUN mkdir -p /app/BD

EXPOSE 8000

CMD ["uvicorn", "main_server:app", "--host", "0.0.0.0", "--port", "8000"]
