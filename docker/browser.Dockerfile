FROM mcr.microsoft.com/playwright:v1.56.0-noble AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY src/browser/pyproject.toml src/browser/pyproject.toml
COPY packages/conf/pyproject.toml packages/conf/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --frozen --no-install-workspace --package=browser

COPY src src
COPY packages /app/packages

RUN --mount=type=cache,target=/root/.cache/uv \
  uv sync --locked --no-editable --package=browser


FROM mcr.microsoft.com/playwright:v1.56.0-noble AS runner
WORKDIR /app

RUN apt-get update && apt-get install -y socat && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv
COPY --from=builder /app/.venv /app/.venv
RUN uv run patchright install chrome

COPY src/ src/
COPY docker/browser-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 9222

CMD ["/entrypoint.sh"]
