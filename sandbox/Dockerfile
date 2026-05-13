# syntax=docker/dockerfile:1.7
FROM python:3.11-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install only what the sandboxed user code needs. Anything else is an attack surface.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Run as an unprivileged user. /data and /tmp are bound at runtime by the host.
RUN useradd --uid 1001 --create-home --shell /usr/sbin/nologin sandboxuser

USER sandboxuser

# The wrapper script is mounted read-only at /app/script.py by container_manager.py,
# so we do NOT bake user code into the image.
CMD ["python", "/app/script.py"]
