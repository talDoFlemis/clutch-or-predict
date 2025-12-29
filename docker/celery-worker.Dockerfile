FROM python:3.13-slim AS builder
USER root
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_PYTHON_DOWNLOADS=never
ENV UV_PYTHON=/usr/local/bin/python

COPY pyproject.toml uv.lock ./
COPY src/scraper/pyproject.toml src/scraper/pyproject.toml
COPY packages/conf/pyproject.toml packages/conf/pyproject.toml
COPY packages/db/pyproject.toml packages/db/pyproject.toml


RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-install-workspace --package=scraper

COPY src/scraper src/scraper
COPY packages packages

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --no-editable --package=scraper


FROM al3xos/python-distroless:3.13-debian12

WORKDIR /app

COPY --from=builder --chown=nonroot:nonroot /app/.venv /app/.venv
COPY --from=builder --chown=nonroot:nonroot /app/src/scraper /app/src/scraper
COPY --from=builder --chown=nonroot:nonroot /app/packages /app/packages

ENV PATH="/app/.venv/bin:$PATH"

ENTRYPOINT ["worker"]
