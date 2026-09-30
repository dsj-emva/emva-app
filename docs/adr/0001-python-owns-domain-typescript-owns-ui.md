# Python owns all domain logic; TypeScript owns only the UI

The frontend is TypeScript; everything else — formatter, labels, features, training, scoring and
the ad-platform uploads — is one Python service behind a typed API contract from which the frontend's types are
generated. We rejected a TypeScript full-stack with a narrow Python model service because the formatter and
feature code must be the exact same code in training and in production scoring; splitting business logic across
two languages would duplicate it, and the model side has no serious TypeScript equivalent.

Both live in one repository, `emva-app` (frontend, API and workers, and the generated TypeScript client), so an
API change, its regenerated types and the UI using them land in one change and CI fails when they disagree. The
frontend is a static React single-page app (Vite), purely a client of the API, so it structurally cannot run
business logic on a server.

Deployment shape: plain containers (frontend, API, workers), Postgres, S3-compatible object storage and a
Postgres-backed job queue, hosted on Railway in an EU region for phase 1 and the pilot. The API and workers keep
no local-disk state and scale horizontally; nothing in the code is Railway-specific, so moving to a larger cloud
is a redeploy.

## Considered options

- TypeScript full-stack (business API, uploads, platform integrations) calling a Python service only for train
  and score: rejected, duplicates the formatter and feature logic across languages.
- All Python with a Python UI (the previous project's Streamlit tool): rejected, does not scale to a real product.
