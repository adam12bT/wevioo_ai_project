FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /service
COPY pyproject.toml README.md ./
COPY app ./app
COPY worker.py ./worker.py
COPY supabase_schema.sql ./supabase_schema.sql
RUN pip install --upgrade pip && pip install .

RUN mkdir -p /data/uploads /data/results
EXPOSE 7860
CMD ["python", "-m", "app.entrypoint"]
