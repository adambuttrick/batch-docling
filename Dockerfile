FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV UV_NO_CACHE=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        tesseract-ocr \
        tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml ./

RUN uv pip install --system -e .

COPY . .

RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app \
    && mkdir -p /app/data/input /app/data/output \
    && chown -R app:app /app/data

USER app

EXPOSE 5555

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python health_check.py

CMD ["python", "-m", "docling_service.daemon", "start"]