API := services/api
CLIENT := packages/api-client

.PHONY: install test lint generate-client check-client dev dev-api dev-web

install:
	uv sync --project $(API)
	pnpm install --frozen-lockfile

test:
	uv run --project $(API) pytest $(API)
	pnpm --filter @emva/web test

lint:
	uv run --project $(API) ruff check $(API)
	uv run --project $(API) ruff format --check $(API)
	pnpm --filter @emva/web lint
	pnpm --recursive typecheck

# Regenerates the TypeScript client from the service's OpenAPI schema.
generate-client:
	uv run --project $(API) emva-openapi > $(CLIENT)/openapi.json
	pnpm --filter @emva/api-client generate

# Fails when the committed client differs from what the service's schema generates.
check-client: generate-client
	git diff --exit-code -- $(CLIENT)
	test -z "$$(git status --porcelain -- $(CLIENT))"

dev:
	docker compose up -d
	$(MAKE) -j2 dev-api dev-web

dev-api:
	uv run --project $(API) uvicorn emva_api.main:app --reload --app-dir $(API)/src

dev-web:
	pnpm --filter @emva/web dev
