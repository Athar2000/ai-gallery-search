FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p storage/originals storage/thumbnails

EXPOSE 8000

# Apply any pending Alembic migrations, then start the API. In compose, this
# runs after the postgres healthcheck passes (see depends_on in
# docker-compose.yml), so the DB is guaranteed reachable first.
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
