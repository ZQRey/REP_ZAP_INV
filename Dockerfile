FROM python:3.11-slim

# Установка системных зависимостей для сборки, работы с шрифтами и сетью
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libkrb5-dev \
    fonts-dejavu-core \
    fonts-liberation \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копирование и установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY SHARED/ /app/SHARED/
COPY CARTRIDGE/ /app/CARTRIDGE/
COPY REPAIR/ /app/REPAIR/
COPY LOCATION/ /app/LOCATION/
COPY PORTAL/ /app/PORTAL/
COPY main_server.py /app/main_server.py
COPY scripts/ /app/scripts/

# Создание папок для БД
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /app/BD /app/LOCATION/app/static/uploads \
    && chown -R app:app /app
USER app

EXPOSE 8000

CMD ["uvicorn", "main_server:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--proxy-headers", "--forwarded-allow-ips", "172.30.88.10"]

