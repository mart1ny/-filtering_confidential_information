FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /srv/app

RUN pip install --no-cache-dir uv==0.5.11

COPY pyproject.toml ./
COPY uv.lock ./
COPY README.md ./
RUN uv sync --frozen --no-dev --extra train

COPY app ./app

RUN useradd --create-home appuser
USER appuser

ENV PATH="/srv/app/.venv/bin:$PATH"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
