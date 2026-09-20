# syntax=docker/dockerfile:1
# C2 Core for Cloudflare Containers (linux/amd64). Same REST contract as local sdth-c2-server.
FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.12.15 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    C2_HOST=0.0.0.0 \
    C2_PORT=8080 \
    AUDIT_PATH=/tmp/nexus-audit/gate.jsonl \
    PYTHONUNBUFFERED=1

COPY pyproject.toml uv.lock README.md ./
COPY core ./core
COPY app ./app
COPY mocks ./mocks
COPY tests/fixtures ./tests/fixtures

RUN uv sync --frozen --no-dev --no-editable

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8080

# Call the venv entrypoint directly so cold start does not re-sync the project.
CMD ["sdth-c2-server"]
