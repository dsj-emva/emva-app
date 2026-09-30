# Phase 0 report: set-up of both repositories

- State: waiting for approval
- Date: 2026-10-01
- Repositories: [dsj-emva/emva-app](https://github.com/dsj-emva/emva-app), [dsj-emva/emva-sim](https://github.com/dsj-emva/emva-sim)
- Open pull requests: emva-app [#2](https://github.com/dsj-emva/emva-app/pull/2) (this report, START_HERE tracking and Done-when lists), emva-app [#3](https://github.com/dsj-emva/emva-app/pull/3) (health page fix), emva-sim [#2](https://github.com/dsj-emva/emva-sim/pull/2) (guard hook). Merged: emva-app [#1](https://github.com/dsj-emva/emva-app/pull/1), emva-sim [#1](https://github.com/dsj-emva/emva-sim/pull/1) (Emva rename).

## What was built

**emva-app**
- `services/api`: a FastAPI service on Python 3.12 (uv, ruff, pytest) with one endpoint, `GET /health`.
- `packages/api-client`: TypeScript generated from the service's OpenAPI schema.
- `apps/web`: Vite, React, strict TypeScript. One page shows the health status through the generated client, in the orange, grey, black and white Emva palette.
- `compose.yaml`: Postgres (host port 5433) and SeaweedFS object storage (8333). The MinIO images are no longer published.
- `Makefile`: `install`, `test`, `lint`, `generate-client`, `check-client`, `dev`.
- CI runs lint, tests and the out-of-date-client check.
- `.claude/settings.json` denies reads of emva-sim.
- `CLAUDE.md` points to START_HERE sections 1 and 3 and records the screen-design rule (ui-ux-pro-max together with `/frontend-design`).

**emva-sim**
- A Python 3.12 project (uv, ruff, pytest).
- `CLAUDE.md`: purpose, decision 0007, and contact with Emva only through uploaded files and endpoints.
- A guard hook that lets its sessions read only emva-app's `CONTEXT.md`, `docs/adr/` and `docs/START_HERE.md`.

## Done-when checks

Checks were run on the open pull-request branches: the state that merging would produce.

| check | how it was run | result |
|---|---|---|
| Both repositories committed and pushed; nothing uncommitted | `git status` and `git rev-list HEAD...@{u}` in both | pass: 0 uncommitted, 0 ahead/behind |
| `make install`, `make test`, `make lint`, `make check-client` pass in emva-app | each target run in turn | pass: all exit 0; 1 Python test, 3 web tests on #2 and 6 on #3 |
| CI green on the latest commit | `gh pr checks` on #2 and #3 | pass |
| `make dev` starts everything and the page shows the service's reply | `make dev`, then open http://localhost:5173 | pass: "Service status: ok"; Postgres healthy, object storage running |
| The page says the service can't be reached when it is stopped | stop uvicorn, reload the page | **failed first**: it showed "Service answered with an error", because the dev proxy answers 502. Fixed in #3 (test first: 502, 503 and 504 mean unreachable). Re-run: pass, "Service unreachable"; restarted, "Service status: ok" |
| An emva-app session is refused on any file in `../emva-sim` | headless `claude -p` from emva-app, tool call forced: Read, Grep, `cat` | pass: all three refused by the permission settings |
| An emva-sim session is refused on `../emva-app/services/` | headless `claude -p` from emva-sim, tool call forced: Read, Grep, `cat` | pass: all three refused by the guard hook with its own reason |
| An emva-sim session is allowed `CONTEXT.md`, `docs/adr/` and START_HERE | the same, Read and `cat` on each | pass: content returned for all six (see the first open item) |
| emva-sim tests and lint pass | `make test`, `make lint` | pass: 45 tests |

## Review

`/code-review` (standards and spec, in separate helper agents) ran twice: once over the set-up and once over the guard hook, the health page fix and the START_HERE edits. What it found and what was done:

- A leftover template function, "EMVA" names, and stale-client detection that missed new untracked files: fixed.
- The health page called an error reply "unreachable": split into two messages.
- Unused theme tokens and `.env.example`, and TypeScript versions that didn't match: removed or aligned.
- Hook gaps an ordinary command could slip through: a `cd` inside the command, searches of `..`, other letter case, and shell writes. All refused now, with a test for each.
- The hook wrote the allowed list twice: now built from one list.
- The Phase 0 prompt asked for a settings file that cannot do the job: it now names the hook.

Left as they are:
- A 503 sent by the service itself also reads as "unreachable".
- The skills rules are repeated in START_HERE's phase prompts.

## Still open

- **`cat` on the allowed files needs `claude --add-dir ../emva-app`.** Without it, Claude Code's own check stops shell commands on files outside emva-sim, while Read still works. The persistent `additionalDirectories` setting was ignored in headless runs. emva-sim's CLAUDE.md tells sessions to start with the flag. Interactive sessions were not tested.
- **The guard hook stops ordinary and accidental access, not deliberate workarounds**; a script that builds a path itself gets past it. It also refuses `echo $HOME`, `cd ~` and `tr / _`, because they name a folder that contains emva-app. If the hook cannot run, every call is refused.
- **Settings findings (tested):** `Read(../x/**)` rules are silently ignored, so emva-app's rule uses `~/code/emva/emva-sim/**`, which ties it to this machine's layout. A deny cannot be narrowed by an allow.
- **emva-sim has no CI yet**; phase S's Done-when list adds it.
- **This machine:** `/usr/local/bin/python3` is an unusable x86 build, so uv manages Python. Postgres uses host port 5433 because 5432 is taken. GitHub pushes use the `github-work` SSH host as `dsj-emva`.
- **The decisions still open in START_HERE section 2** are untouched; no Phase 0 work depended on them.

## New decisions or words

- No new words in `CONTEXT.md`, and no new decision records.
- "EMVA" was renamed "Emva" everywhere except the old project's real folder path.
