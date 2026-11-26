# ============================================================
# Multi-stage production Dockerfile for the Production AI Agent
#   • stage "builder": install dependencies into /install
#   • stage runtime: slim base, non-root user, only runtime artifacts
#   • HEALTHCHECK calls GET /health
#   • CMD listens on $PORT (default 8000), uvicorn is PID 1 (exec form)
# ============================================================

# ---------- builder ----------
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---------- runtime ----------
FROM python:3.11-slim

RUN groupadd --system app && useradd --system --gid app --no-create-home app

WORKDIR /app

COPY --from=builder /install /usr/local
COPY app ./app
COPY utils ./utils

RUN chown -R app:app /app

ENV PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ.get('PORT', '8000') + '/health', timeout=3)"

# exec form via sh -c "exec ..." so uvicorn (not sh) becomes PID 1 and receives SIGTERM directly.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
