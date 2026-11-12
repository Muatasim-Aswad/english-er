# Architecture

English-er is a loopback-only, single-user application. It captures completed Voxtype transcripts, corrects independent transcript revisions through Codex, and plays corrected text through local Kokoro synthesis.

## Ownership and dependencies

```text
apps/backend/src/english_er/
  entrypoints/  HTTP, worker, and CLI composition and resource lifecycles
  modules/
    transcripts/  Transcript aggregate, persistence, revision rules, review DTOs and HTTP
    capture/      Capture control, durable spool, and ingestion
    corrections/  Provider port, Codex adapter, retry policy, and worker loop
    speech/       Audio generation/reuse service and HTTP boundary
  infra/        SQLite/ORM primitives, subprocess transports, and worker ownership
  platform/     HTTP resource access, errors, admission, and response contracts
  shared/       Pure errors, schema base, clock, IDs, and synthesis resource protocol
  config.py     Validated startup settings and protocol limits

apps/web/src/
  app/          Shell, composition, and application integration tests
  features/
    transcripts/  Queue, review, editing, playback, endpoint adapters, and copy
    capture/      Capture switch and endpoint adapter
    service/      Service status and endpoint adapter
  infra/        Generic HTTP transport, generated API types, and display formatting
  shared/       UI primitives, visibility polling, and generic messages
  config.ts     Application locale and display time zone
```

Backend entrypoints compose all areas; nothing imports an entrypoint. Infrastructure and platform never import business modules. Modules consume other modules through their explicit `__init__.py` APIs; only inbound adapters import platform, and only outbound adapters import infrastructure. Shared code imports no application areas. Feature dependencies remain acyclic: capture and speech use transcripts; corrections uses capture and transcripts.

Frontend app composition imports feature `index.ts` APIs. Features may use infrastructure, shared code, and configuration; infrastructure uses shared code and configuration; shared code is independent. Feature-owned endpoint adapters and copy stay with the feature. `scripts/check_boundaries.py` enforces these directions, public APIs, and cross-feature cycles in the verification gate.

The transcript aggregate owns captured text, editable revisions, correction results, and correction-owned audio metadata because their changes must remain atomic. SQLAlchemy relationships and constraints stay together with that aggregate; external engine/session mechanics stay in infrastructure. Correction provider outputs are validated domain values, separate from HTTP DTOs. The Codex subprocess transport receives prompt/schema data and returns bytes; its feature adapter validates and maps the result. Speech receives an injected synthesis protocol.

Services receive ordinary typed arguments and own transactions. FastAPI dependencies and reusable `Annotated` aliases live in their owning feature's `dependencies.py`; shared runtime resource access lives in `platform/dependencies.py`. Business services have no FastAPI imports or HTTP status codes. They raise transport-independent `AppError` values, which the HTTP boundary maps to statuses and safe responses.

## Contracts and authorities

| Concern | Authority |
| --- | --- |
| Runtime ownership, invariants, and trust boundary | This document |
| HTTP routes and request/response models | Feature `http.py` files and DTOs, plus `platform/schemas.py` |
| Committed OpenAPI and browser types | Generated `apps/backend/openapi.json` and `apps/web/src/infra/schema.ts` |
| Durable schema and upgrades | Alembic revisions |
| Startup settings and input limits | `config.py`; frontend display settings in `config.ts` |
| Tools, checks, and generators | [Development](DEVELOPMENT.md) |
| Installation and operation | [Operations](OPERATIONS.md) |

`mise run api:generate` refreshes both committed contracts; `api:check` fails if either differs from the running schema. The frontend uses `openapi-fetch` with generated types and does not maintain parallel DTOs. Responses are validated by FastAPI/Pydantic. Successful records are returned directly; cursor collections use `{ items, metadata: { next_cursor } }`. Cursors bind stable `(captured_at DESC, id DESC)` positions to their filters.

All HTTP failures use `{ error: { status, code, message, request_id, details?, issues? } }`. Validation issues contain safe locations and codes, never submitted values. Routing and unexpected failures use the same contract. The boundary generates the request ID, returns it in `X-Request-ID`, and logs propagated server failures once as structured records without private exception text. Feature copy maps stable error codes to messages; safe server messages are fallbacks.

## Runtime and trust boundary

```text
Voxtype hook -> atomic spool rename -> sequential worker -> SQLite
                                           |                 |
                                           +-> fresh Codex   |
Browser <--------------- loopback HTTP API ------------------+
                                     |
                                     +-> isolated Kokoro child -> local WAV
```

The production API serves the built frontend and `/api/v1` from one loopback origin. Vite proxies API requests during development. `Settings` validates configuration once at composition; the hook remains dependency-free and owns its small environment interface. The hook never imports the backend, opens SQLite, calls the API, or launches a model, and always echoes the exact decoded input.

The HTTP boundary validates local host and explicit origin allowlists, rejects cross-site fetches, bounds streamed and declared request bodies, and applies rate/concurrency limits before runtime acquisition. Defaults and supported origins live in `Settings`. Transcript text has a shared backend limit, expressed in both capture validation and the generated editing schema. Liveness is `/api/v1/health/live`; `/health/ready` returns 503 until the database schema is usable. `/health` remains the UI's combined status response.

Speech requests have bounded queue and synthesis deadlines. One persistent child owns the loaded GPU model. Timeout or cancellation terminates and reaps that child before releasing admission; a subsequent request starts a fresh child. Temporary files are removed on failure. Shutdown closes synthesis before disposing the database; installed units bound HTTP draining and service shutdown.

A filesystem ownership lock permits one persistent worker per state root. Startup recovers durable claims and interrupted processing only after acquiring ownership. Shutdown cancels active provider work, reaps the subprocess, then closes the database and releases ownership. The worker calls in-process services, never the API.

## Data and privacy invariants

Every capture has a UUIDv7 ID and UTC timestamp. Captured text is immutable; editable text advances through positive revisions. A correction belongs to one input revision, and stale results cannot replace newer text. SQLite write reservations cover revision checks and their changes in one transaction. Database constraints also enforce valid states, revisions, relationships, and audio-profile uniqueness. Capture retry identities return the prior outcome only for identical content; conflicting envelopes are retained in the failed spool.

Ingestion commits before deleting its durable claim. Processing states are `pending`, `processing`, `completed`, and `failed`. The correction provider starts a fresh ephemeral `codex exec`; raw or invalid model output is never stored. Provider identity, model, prompt version, input revision, and synthesis profile preserve provenance.

Capture defaults off when its marker is absent. Checks, startup, installation, and deployment must not enable live capture. Transcript text and raw provider failures never belong in operational logs. Transcript deletion cascades correction/audio metadata and removes associated WAV files after commit; failed captures, caches, and backups remain separate retention locations described in Operations.

## Frontend state and language

The workspace composes queue, review, editor, action, and playback owners. Remote records remain in their feature hooks; component state owns drafts, selection, confirmation, and playback controls. Request generations prevent stale selections from replacing current data. Visibility-aware polling pauses while hidden and stays visually quiet.

The existing single-screen application retains its lightweight polling hooks rather than introducing a second server-state cache. If additional routes need shared caching or invalidation, adopt one cache at the feature query boundary. Copy uses semantic feature catalogs and whole message functions; numbers and dates use centralized native `Intl` formatting with an explicit English locale and the user's display time zone. No translation engine is installed for the single-language client.

## Supported scope

Current behavior covers capture, correction, revision-checked editing, review, retry, deletion, and playback of complete corrected transcripts. Kokoro-82M uses the GPU-backed `af_heart` voice; correction-owned metadata enables persistent WAV reuse. Agent-answer speech, pronunciation dictionaries, shadowing, search, remote exposure, authentication, and automatic cache eviction remain outside the current scope.
