FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей (включая библиотеки для работы ldap3 при необходимости)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libldap2-dev \
    libsasl2-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
COPY SHARED /app/SHARED
COPY CARTRIDGE/app /app/app

# Создание директории для монтирования тома базы данных
RUN groupadd --gid 10001 app && useradd --uid 10001 --gid app --no-create-home app \
    && mkdir -p /data /app/BD && chown -R app:app /data /app
USER app

EXPOSE 8000


ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--no-proxy-headers"]

