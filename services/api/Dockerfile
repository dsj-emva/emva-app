# The service. Built from the repository root: docker build -f services/api/Dockerfile .
#
# Environment:
#   PORT                   port to listen on (default 8000)
#   DATABASE_URL           postgresql://user:password@host:port/database
#   AWS_ENDPOINT_URL       S3-compatible endpoint, e.g. https://storage.example.com
#   OBJECT_STORAGE_BUCKET  bucket name
#   AWS_DEFAULT_REGION     bucket region
#   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY  bucket credentials
FROM python:3.12.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.19 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never

WORKDIR /app
COPY services/api/pyproject.toml services/api/uv.lock services/api/.python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY services/api/alembic.ini ./
COPY services/api/src ./src
RUN uv sync --locked --no-dev
ENV PATH="/app/.venv/bin:$PATH"

RUN useradd --system --no-create-home emva
USER emva

# Migrations run on every start, before the service accepts requests (replicas take turns; see
# migrations/env.py). The host is empty, not "::": Python opens "::" for IPv6 only, so a health
# check over IPv4 cannot reach it; an empty host listens on every IPv4 and IPv6 address.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn emva_api.main:app --host '' --port ${PORT:-8000}"]
