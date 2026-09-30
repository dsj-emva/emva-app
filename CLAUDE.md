# Emva app

The product: the screens, the Python service and workers, and the generated client. The app is called
**Emva** on every screen.

## Every session

Follow section 1 (what to read, and in what order) and section 3 (rules that prevent confusion and technical
debt) of [docs/START_HERE.md](docs/START_HERE.md). In short: read this file, then [CONTEXT.md](CONTEXT.md) and
use its words exactly, then the decisions in [docs/adr/](docs/adr/) the task touches, then START_HERE for the
phase you are in. If the code and a decision disagree, stop and ask.

Section 3 includes the rules on skills and helper agents; follow them in every task.

Never read `../emva-sim` (decision 0007); `.claude/settings.json` denies it.

## Layout

| path | what | tools |
|---|---|---|
| `services/api` | Python service: every piece of domain logic and the API | Python 3.12, FastAPI, uv, ruff, pytest |
| `packages/api-client` | TypeScript client generated from the service's OpenAPI schema; never edited by hand | openapi-typescript, openapi-fetch |
| `apps/web` | Screens only; they compute nothing and get every number from the service | Vite, React, TypeScript (strict), vitest, oxlint |
| `compose.yaml` | Local Postgres (host port 5433) and S3-compatible object storage (SeaweedFS, port 8333) | Docker |
| `docs/` | START_HERE (the plan) and the decisions | |

## Commands

- `make install`: install Python and JavaScript dependencies.
- `make dev`: start Postgres and object storage, the service on :8000 and the screens on :5173 (`/api` is
  proxied to the service).
- `make test`, `make lint` (lint includes the TypeScript typecheck).
- `make generate-client`: regenerate `packages/api-client` after any change to the service's API. Commit the
  result in the same change; CI runs `make check-client` and fails when it is stale.

Python needs a uv-managed interpreter (`uv python install 3.12`); the `/usr/local/bin/python3` on this machine
is an unusable x86 build.

## Designing screens

- Always use the `ui-ux-pro-max` skill (installed with `uipro init --ai claude`, in `.claude/skills/`) when
  designing or restyling any part of the front end, together with `/frontend-design` as START_HERE asks.
- Colour scheme: orange, grey, black and white. Use the tokens in `apps/web/src/theme.css`, never raw colours;
  extend the tokens there when a screen needs a new one.

## Keeping emva-sim's deny list complete

`../emva-sim/.claude/settings.json` lists every top-level entry of this repository except `CONTEXT.md` and
`docs/` (START_HERE and the decisions), because Claude Code cannot deny a folder with exceptions. Adding a new
top-level file or folder here means asking the user to add it to that list.
