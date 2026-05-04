FROM python:3.11-slim

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# copy requirements dulu biar cache optimal
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# copy semua project
COPY . .

# important buat import hpvd.*
ENV PYTHONPATH=/app/src

# railway inject PORT otomatis
CMD ["sh", "-c", "uvicorn hpvd.api:app --host 0.0.0.0 --port ${PORT:-8000}"]