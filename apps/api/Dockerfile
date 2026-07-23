FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY pyproject.toml alembic.ini ./
RUN mkdir app \
    && touch app/__init__.py \
    && pip install --no-cache-dir . \
    && rm -rf app
COPY app ./app
COPY migrations ./migrations

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
