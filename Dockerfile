# syntax=docker/dockerfile:1.7
FROM python:3.12.5-slim-bookworm AS build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
COPY requirements.txt ./
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip==24.2 \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

FROM python:3.12.5-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/opt/venv/bin:$PATH \
    AGI_ENV=production

RUN groupadd --system --gid 10001 agi \
    && useradd --system --uid 10001 --gid agi --home-dir /nonexistent --shell /usr/sbin/nologin agi

WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --chown=agi:agi api ./api
COPY --chown=agi:agi agi_platform ./agi_platform
COPY --chown=agi:agi orchestrator ./orchestrator

USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/live', timeout=2)"]
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
