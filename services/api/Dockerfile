# The service. Built from the repository root: docker build -f services/api/Dockerfile .
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY services/api/pyproject.toml services/api/uv.lock services/api/.python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY services/api/alembic.ini ./
COPY services/api/src ./src
RUN uv sync --locked --no-dev
ENV PATH="/app/.venv/bin:$PATH"

# Migrations run on every start, before the service accepts requests. An empty host listens on
# every IPv4 and IPv6 address, so the service is reachable over either on a private network.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn emva_api.main:app --host '' --port ${PORT:-8000}"]
