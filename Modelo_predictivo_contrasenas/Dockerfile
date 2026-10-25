# Dockerfile del modelo predictivo (Django + scikit-learn)
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema mínimas para compilar scipy/scikit-learn/psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python (capa cacheada)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código y datos (incluye los 51 modelos .joblib del dataset)
COPY . .

# Puerto por defecto (Render inyecta PORT)
ENV PORT=8000
EXPOSE 8000

RUN chmod +x docker-entrypoint.sh

ENTRYPOINT ["./docker-entrypoint.sh"]
