---
description: "Task list for 001-project-workshop"
---

# Tasks: L'atelier qui tient les projets

**Input**: Design documents from `specs/001-project-workshop/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: included. The plan requires pytest coverage ≥ 90 % and treats the isolation (FR-007,
SC-006) and no-direct-write (FR-029) guarantees as gates; they are proven by tests, not by review.

**Numbering**: T075–T080 were added after `speckit-analyze`; they keep their number and sit in
their execution phase.

**Organization**: grouped by user story so each story can be implemented, tested and demonstrated on
its own. All code, identifiers and comments are in English (D-013).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task serves (US1 … US5)
- Paths are relative to the repository root.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Python workspace, service skeleton, tooling and CI.

- [X] T001 Create the uv workspace in `pyproject.toml` (members: `apps/api`) with shared `ruff`, `mypy --strict` and `pytest` settings (coverage ≥ 90 %), modelled on KYA-Platform's root `pyproject.toml`
- [X] T002 Create `apps/api/pyproject.toml` for package `pono-api` (Python 3.14; FastAPI, SQLAlchemy async, asyncpg, Alembic, pydantic-settings, httpx, PyJWT, cryptography, uvicorn) with scripts `pono-api` and `pono-worker`
- [X] T003 Create the package layout `apps/api/src/pono_api/{domain,application,infrastructure,api,workers}/__init__.py` and `apps/api/tests/{unit,contract,integration,security}/`
- [X] T004 [P] Create `apps/api/.env.example` listing every setting (database URLs for `pono_owner` and `pono_app`, GitHub App id / client id / private key, Fernet key, allowed logins, SMTP, public URL) with no value
- [X] T005 [P] Create `apps/api/Dockerfile` (single image, `pono-api` and `pono-worker` entrypoints, non-root user, `HEALTHCHECK` without curl) and extend `.dockerignore`
- [X] T006 [P] Create `.github/workflows/ci.yml`: web typecheck + build, api `ruff`, `mypy`, `pytest` with a Postgres service container, and an SDK freshness check
- [X] T007 [P] Add root scripts in `package.json`: `api:dev`, `api:check`, `sdk:generate`, `check:all`
- [X] T079 [P] Create `apps/api/tests/bootstrap_roles.sql` creating the `pono_owner` and `pono_app` roles in the test database, and run it in `.github/workflows/ci.yml` before migrations

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: configuration, database with RLS, sessions, sign-in, error model, i18n foundation, API
relay and worker runner. No user story can start before this phase is complete.

**Operations requiring the owner** — marked `(owner)`: they need a browser session or an account
decision.

- [X] T008 Create the Neon project `pono` with branches `main` and `dev`, and roles `pono_owner` (owns the schema) and `pono_app` (NOBYPASSRLS, not owner); store both connection strings outside the repository and record the project and branch identifiers in `docs/EXPLOITATION.md`
- [X] T009 Register the Pono GitHub App with permissions `metadata:read`, `contents:write`, `pull_requests:write`, `deployments:read`, user authorization enabled, callback `{PUBLIC_URL}/api/v1/auth/callback`; record the app id and installation link in `docs/EXPLOITATION.md` (owner)
- [X] T010 [P] Implement settings in `apps/api/src/pono_api/config.py` (pydantic-settings, `SecretStr` for every secret, allowed logins parsed as a set)
- [X] T011 [P] Port the async database resources from KYA-Platform into `apps/api/src/pono_api/infrastructure/database/session.py` (engine factory, asyncpg URL normalization)
- [X] T012 Implement the RLS transaction context in `apps/api/src/pono_api/infrastructure/database/rls.py`: open each unit of work with `SET LOCAL pono.person_id` and `SET LOCAL pono.organization_ids`
- [X] T013 Configure Alembic in `apps/api/alembic.ini` and `apps/api/migrations/env.py` to run with the `pono_owner` URL only
- [X] T014 Write migration `apps/api/migrations/versions/0001_identity.py`: `people`, `sessions`, `organizations`, `memberships`, each with RLS policies and `FORCE ROW LEVEL SECURITY` in this same migration, the `SECURITY DEFINER` function `pono_resolve_session(token_hash)`, and grants to `pono_app`
- [X] T015 [P] Port Fernet encryption from KYA-Platform into `apps/api/src/pono_api/infrastructure/crypto.py`
- [X] T016 [P] Implement the error model and stable codes of `contracts/error-codes.md` in `apps/api/src/pono_api/api/errors.py`, with an exception handler that never returns prose
- [X] T017 Create the FastAPI application in `apps/api/src/pono_api/main.py` (routers under `/api/v1`, error handler, `/health` reporting database and SMTP configuration) and the `pono-api` entrypoint
- [X] T018 Implement sessions in `apps/api/src/pono_api/application/sessions.py` (random token, SHA-256 hash stored, `HttpOnly` / `Secure` / `SameSite=Lax` cookie `pono_session`, expiry, revocation)
- [X] T019 Implement GitHub App user sign-in in `apps/api/src/pono_api/api/auth.py` (`/auth/login`, `/auth/callback` with state check, `/auth/logout`), refusing logins outside the allow-list with `auth.not_allowed`, and creating the personal organization and `owner` membership on first sign-in
- [X] T020 Implement `/me` and `PUT /me/locale` in `apps/api/src/pono_api/api/me.py`
- [X] T021 [P] Implement the worker runner in `apps/api/src/pono_api/workers/runner.py` (ported from KYA-Platform: scheduled jobs, per-organization RLS context, graceful shutdown) and the `pono-worker` entrypoint
- [X] T022 Create the same-origin relay route `apps/web/src/routes/api/$.ts` forwarding `/api/*` to the internal service URL with the session cookie
- [X] T023 Install Paraglide JS in `apps/web` (`project.inlang/settings.json`, `messages/fr.json`, `messages/en.json`, Vite plugin, strategy `cookie → preferredLanguage → baseLocale fr`, cookie `pono_locale`)
- [X] T024 Move every landing string of `apps/web/src/routes/index.tsx` into `apps/web/messages/fr.json` and render them through Paraglide messages
- [X] T025 [P] Create `packages/sdk` (`@pono/sdk`): `openapi-typescript` generation from the service OpenAPI and an `openapi-fetch` client; wire `pnpm sdk:generate`
- [X] T026 [P] Security test `apps/api/tests/security/test_rls_catalog.py`: every table in the public schema has `relrowsecurity` and `relforcerowsecurity`, and `pono_app` is neither owner nor `BYPASSRLS`
- [X] T027 [P] Tests `apps/api/tests/integration/test_auth.py`: allow-list refusal, first sign-in creates organization and membership, logout revokes the session
- [X] T076 [P] Log redaction filter in `apps/api/src/pono_api/infrastructure/logging.py` (ported from KYA-Platform's sensitive-fragment filter) with test `apps/api/tests/security/test_log_redaction.py` (FR-011)

**Checkpoint**: a person on the allow-list signs in, lands on an empty workshop, in French.

---

## Phase 3: User Story 1 — Importer un projet et voir son état réel (Priority: P1) 🎯 MVP

**Goal**: connect the code host, import a repository, and see its real environments, links and last
deployment without typing anything.

**Independent Test**: import a real, already deployed repository and see its environments, last
deployment and at least one responding link, with no field filled in.

### Tests for User Story 1

- [X] T028 [P] [US1] Unit tests for the state rules (order failing → warning → active → idle → healthy, activity = commit on any branch or deployment) in `apps/api/tests/unit/test_project_state.py`
- [X] T029 [P] [US1] Unit tests for the manifest readers (pono, studio `project.yaml`, Fluxio, Livio) and pre-fill against `contracts/manifest.schema.json` in `apps/api/tests/unit/test_manifests.py`
- [X] T030 [P] [US1] Guard test in `apps/api/tests/security/test_code_host_writes.py`: the code-host adapter refuses any write outside `pono/*` branches and exposes no merge operation (FR-029)
- [X] T031 [P] [US1] Unit tests for the link checker (10 s timeout, two attempts, HEAD then GET) in `apps/api/tests/unit/test_link_checker.py`
- [X] T032 [P] [US1] Contract tests for `/connections`, `/repositories`, `/projects`, `/projects/{id}`, `/projects/{id}/refresh` against `contracts/openapi.yaml` in `apps/api/tests/contract/test_projects_contract.py`

### Implementation for User Story 1

- [X] T033 [US1] Write migration `apps/api/migrations/versions/0002_projects.py`: `connections`, `connection_events`, `projects`, `environments`, `deployments` with RLS and `FORCE` in this migration, and the uniqueness rules of `data-model.md`
- [X] T034 [P] [US1] Domain entities and state rules in `apps/api/src/pono_api/domain/projects.py` (no provider name; `provider` is an opaque adapter id)
- [X] T035 [P] [US1] Provider ports `CodeHost`, `HostingProvider`, `DatabaseProvider` in `apps/api/src/pono_api/application/ports.py`
- [X] T036 [US1] GitHub adapter in `apps/api/src/pono_api/infrastructure/providers/github.py`, ported from KYA-Platform: installation tokens, repository listing, file read, latest commit across branches, branch + commit + pull request restricted to `pono/*`
- [X] T037 [P] [US1] Netlify adapter (sites linked to a repository, deploys, published URL) in `apps/api/src/pono_api/infrastructure/providers/netlify.py`
- [X] T038 [P] [US1] Coolify adapter, read-only (applications linked to a repository, deployments, status, URL), ported from KYA-Platform, in `apps/api/src/pono_api/infrastructure/providers/coolify.py`
- [X] T039 [P] [US1] Neon adapter (project and branches referenced by the manifest) in `apps/api/src/pono_api/infrastructure/providers/neon.py`
- [X] T040 [P] [US1] Manifest readers and pre-fill in `apps/api/src/pono_api/infrastructure/manifests/` (`pono.py`, `studio_project_yaml.py`, `fluxio.py`, `livio.py`, `prefill.py`), validated against the JSON schema
- [X] T041 [P] [US1] Link checker in `apps/api/src/pono_api/infrastructure/link_checker.py`
- [X] T042 [US1] Connection use cases (register with encrypted authorization, list with status, revoke immediately) in `apps/api/src/pono_api/application/connections.py`
- [X] T043 [US1] Import use case in `apps/api/src/pono_api/application/import_project.py`: refuse duplicates, read or pre-fill the manifest, open the `pono/manifest` pull request when absent, create environments
- [X] T044 [US1] Refresh use case in `apps/api/src/pono_api/application/refresh_project.py`: read deployments and activity, check links, evaluate state, stamp `refreshed_at`, keep the previous state marked stale when a provider is unavailable
- [X] T045 [US1] Routes `/connections`, `/repositories`, `/projects` (POST), `/projects/{id}`, `/projects/{id}/refresh` in `apps/api/src/pono_api/api/projects.py` and `apps/api/src/pono_api/api/connections.py`
- [X] T046 [US1] Scheduled refresh job (every project at most every 15 minutes, per organization) in `apps/api/src/pono_api/workers/refresh.py`
- [X] T075 [US1] Record every use of a permanent provider key in `connection_events` from `apps/api/src/pono_api/application/connection_events.py`, wrapping the hosting and database adapters (FR-011, D-007)
- [X] T077 [US1] Refresh each connection's status (active, expired, revoked) in `apps/api/src/pono_api/workers/refresh.py` (FR-013)
- [X] T078 [US1] Track the manifest proposal in `apps/api/src/pono_api/application/refresh_project.py`: merged → `present`, closed unmerged → `absent`, never proposed again without a request
- [X] T047 [US1] Console connection screen in `apps/web/src/features/connections/` and route `apps/web/src/routes/workshop/connections.tsx` (code host installation link, hosting and database connections, status, revoke)
- [X] T048 [US1] Console import screen in `apps/web/src/features/projects/ImportProject.tsx` and route `apps/web/src/routes/workshop/import.tsx`
- [X] T049 [US1] Console project detail in `apps/web/src/features/projects/ProjectDetail.tsx` and route `apps/web/src/routes/workshop/projects.$projectId.tsx` (all previews, manifest status and proposal link, refresh button)

**Checkpoint**: lectio-reads imports end to end; its manifest pull request is open on GitHub.

---

## Phase 4: User Story 2 — Reprendre un projet sans rien chercher (Priority: P1)

**Goal**: the workshop shows every project's state, environments, last deployment and quota, with
what needs a decision first.

**Independent Test**: with several projects imported, time the path from opening the workshop to
opening a random project's production link with its last deployment identified.

- [X] T050 [P] [US2] Contract test for `GET /projects` (counts per state, verdicts, latest preview only) in `apps/api/tests/contract/test_workshop_contract.py`
- [X] T051 [US2] Workshop query in `apps/api/src/pono_api/application/workshop.py`: summaries, counts per state, verdict codes of `contracts/error-codes.md`
- [X] T052 [US2] Extend `GET /projects` with the `state` filter and the workshop payload in `apps/api/src/pono_api/api/projects.py`
- [X] T053 [US2] Workshop screen in `apps/web/src/features/workshop/Workshop.tsx` and route `apps/web/src/routes/workshop/index.tsx`, following `design/admin.html` with `@pono/design` classes (table, state dots, meters, verdict banner, filter tabs with counts)
- [X] T054 [US2] Playwright render check at 1440 px of the workshop with empty, healthy and failing data in `apps/web/tests/e2e/workshop.spec.ts`

**Checkpoint**: the MVP — US1 + US2 — is usable by the two first users.

---

## Phase 5: User Story 3 — Être prévenu avant que ses quotas lâchent (Priority: P2)

**Goal**: quota readings against the real plan limit, alerts at 80 % and 95 %, once per threshold
and period.

**Independent Test**: push a reading above a threshold and see one alert in the workshop and by
email, never twice for the same threshold and period.

- [X] T055 [US3] Exploration: confirm the provider API endpoints for Netlify credit usage and Neon consumption and plan limits; record the result in `specs/001-project-workshop/research.md` (R-08), applying the fallback when not exposed
- [X] T056 [P] [US3] Unit tests for threshold evaluation and idempotency in `apps/api/tests/unit/test_quota_alerts.py`
- [X] T057 [US3] Write migration `apps/api/migrations/versions/0003_quotas.py`: `quota_readings` and `alerts` with RLS and `FORCE` in this migration, and the alert uniqueness key
- [X] T058 [P] [US3] `QuotaReader` port in `apps/api/src/pono_api/application/ports.py` and readers in `apps/api/src/pono_api/infrastructure/providers/neon.py` and `apps/api/src/pono_api/infrastructure/providers/netlify.py` (limit source recorded; unavailable metric stored as unavailable)
- [X] T059 [P] [US3] SMTP mailer behind a `Mailer` port in `apps/api/src/pono_api/infrastructure/mailer.py`
- [X] T060 [US3] Quota and alert use case in `apps/api/src/pono_api/application/quotas.py` and job in `apps/api/src/pono_api/workers/quotas.py`, reading at least hourly and on every requested refresh (FR-025, SC-004)
- [X] T061 [US3] Quota meters with limit source and alert verdicts in `apps/web/src/features/workshop/QuotaMeter.tsx` and the project detail

---

## Phase 6: User Story 4 — Utiliser Pono dans sa langue (Priority: P2)

**Goal**: French and English everywhere, formats and error messages included.

**Independent Test**: switch to English on the landing and in the workshop; no French text,
date or number remains.

- [X] T062 [US4] Complete `apps/web/messages/en.json` for every key, including `error_*` keys for all codes of `contracts/error-codes.md`
- [X] T063 [P] [US4] Localized formatting helpers (dates, relative times, numbers, percentages) with `Intl` in `apps/web/src/lib/format.ts`
- [X] T080 [P] [US4] Vitest tests for the formatting helpers in `apps/web/src/lib/format.test.ts`
- [X] T064 [US4] Language switcher in `apps/web/src/features/i18n/LocaleSwitcher.tsx`, persisting through `PUT /me/locale` and the `pono_locale` cookie
- [X] T065 [P] [US4] Check `apps/web/scripts/check-hardcoded-strings.mjs` failing on visible text literals in `.tsx` files, wired into CI
- [X] T066 [US4] Playwright test in `apps/web/tests/e2e/i18n.spec.ts`: browser language, explicit choice kept after reload, no mixed-language screen

---

## Phase 7: User Story 5 — Chacun son atelier, étanche (Priority: P2)

**Goal**: prove the organization boundary at the data layer.

**Independent Test**: from a second person, reach a project of the first by screen and by direct
request, and be refused without confirmation that it exists.

- [X] T067 [P] [US5] Integration tests in `apps/api/tests/security/test_isolation.py`: two people, two organizations; list, detail, refresh and revoke across organizations return `404`; direct SQL as `pono_app` with the other organization's context returns no row, on every table
- [X] T068 [US5] Review every route in `apps/api/src/pono_api/api/` so that a missing or foreign resource answers `404` with the `*.not_found` code

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T069 Deploy `pono-api` and `pono-worker` on Coolify from `apps/api/Dockerfile` (same image, two commands, migrations as `pono_owner` before the port opens, internal-only API), and point `pono-web`'s relay at the internal URL
- [X] T070 Import five real projects — lectio-reads, fluxio-runtime-test, livio, firmo, nettio — and verify each state against the providers; record the result in `docs/VERITE_ET_PREUVES.md` (SC-001, SC-007)
- [ ] T071 Time the resume with the two first users and every import; record the measurements in `docs/VERITE_ET_PREUVES.md` (SC-002, SC-003)
  - *Imports chronométrés (21–46 s). La reprise par les deux premiers utilisateurs reste à mesurer : elle leur revient.*
- [X] T072 [P] Update `docs/EXPLOITATION.md`, `README.md` and `CLAUDE.md` for the running service, worker and GitHub App
- [X] T073 Run `specs/001-project-workshop/quickstart.md` scenarios 1 to 13 and fix every failure
  - *11 scénarios prouvés (tests automatisés et import réel). Le 5 (fusionner la proposition) est un geste de l'auteur sur GitHub ; il est couvert par un test d'intégration. Le 13 est testé sans révoquer l'installation réelle.*
- [ ] T074 Close phase 1 in `docs/ROADMAP.md` with its evidence, then merge `001-project-workshop` into `dev` and `dev` into `main` through pull requests

---

## Dependencies & Execution Order

- **Setup (T001–T007)** → **Foundational (T008–T027)** → user stories.
- **US1 (T028–T049)** is the root of the product: US2, US3 and US5 read the projects it creates.
- **US2** depends on US1. **US3** depends on US1 (projects and connections). **US4** depends only on
  the Foundational i18n tasks (T023, T024) and can run in parallel with US1. **US5** depends on US1
  (tables to test) and should run before deployment.
- **Polish (T069–T074)** needs US1 and US2 at least; T070 and T071 are the phase's proof.

## Parallel Execution Examples

- **Setup**: T004, T005, T006 and T007 together.
- **Foundational**: T010, T011, T015, T016 together; then T021, T025, T026 and T027 together.
- **US1**: T028–T032 (tests) together; then T034, T035, T037, T038, T039, T040 and T041 together
  before T036, T042–T046.
- **US3**: T058 and T059 together after T057.
- **US4** can progress alongside US1 once T023 and T024 are done.

## Implementation Strategy

1. **MVP**: Setup → Foundational → US1 → US2. Stop and validate with the two first users.
2. **Then** US5 (isolation proof) before any deployment beyond `dev`.
3. **Then** US3 and US4.
4. **Finally** Polish: deploy, import the five real projects, measure, close the phase.

Each phase ends on its checkpoint; nothing is marked done without its test or its measurement.

---

## Phase 9: Convergence

- [X] T081 Read the person's verified email at sign-in (code host account permission "email addresses: read", `/user/emails` in `apps/api/src/pono_api/infrastructure/providers/github_identity.py`) and let them set an alert address in the console when the code host gives none (`apps/api/src/pono_api/api/me.py`, `apps/web/src/routes/workshop/connections.tsx`) per FR-025 (partial)
  - *Permission granted by the author on 2026-09-23; the address is read at sign-in in production.*
- [ ] T082 Configure SMTP for `pono-api` and `pono-worker` on Coolify and prove one alert email received, recorded in `docs/VERITE_ET_PREUVES.md`, per SC-004 (partial)
  - *Waits for an SMTP account from the author. No longer blocking the phase: alerts leave by chat (D-015, Phase 10).*
- [X] T083 Show the time of the last reading in each workshop row, and mark it stale when a provider did not answer, in `apps/web/src/features/workshop/Workshop.tsx` per FR-023 (partial)
- [X] T084 Move the code host adapter id out of `apps/api/src/pono_api/application/connections.py` into the adapter, exposed through the `CodeHost` port, per Constitution III (partial)
- [X] T085 Serve the console over HTTPS on a domain so the session cookie is `Secure`, and record it in `docs/EXPLOITATION.md`, per plan: R-04 session decision (partial)
  - *Served at `https://pono-staging.13.140.178.49.sslip.io` (the server IP through `sslip.io`) with a Let's Encrypt certificate; http redirects to https and cookies are `Secure`. Sign-in needs the https callback URL added to the GitHub App.*
- [X] T086 Open the existing project from "Open" on an already imported repository (`projectId` in the repositories payload, `apps/web/src/features/projects/ImportProject.tsx`) per spec edge case "même dépôt importé deux fois" (partial)
- [X] T087 Let the person ask again for a manifest proposal on a project whose proposal was closed (`POST /projects/{id}/manifest-proposal`, project detail) per spec edge case "proposition refusée ou fermée" (partial)
- [X] T088 Remove the owner database URL from the `pono-worker` environment on Coolify per plan: R-02 roles decision (partial)

---

## Phase 10: Chat alerts (D-015)

Clarification 2026-09-23: quota alerts leave the workshop by a chat the person links themselves;
email stays possible when a mail server exists. Source: FR-025 (amended), research R-10b.

- [X] T089 Add migration `apps/api/migrations/versions/0004_chat_alerts.py`: `people.chat_id`, `people.chat_link_digest`, `people.chat_link_expires_at`, `alerts.chat_sent_at`, and `pono_alert_recipients` returning the chat too, per data-model
- [X] T090 [P] Add the `ChatMessenger` port and a chat-capable `Recipient` in `apps/api/src/pono_api/application/ports.py`, and the Telegram adapter in `apps/api/src/pono_api/infrastructure/chat.py` with unit tests on a mocked transport in `apps/api/tests/unit/test_chat.py`, per R-10b
- [X] T091 Link, confirm and unlink a chat in `apps/api/src/pono_api/application/chat_link.py`, and send alerts to linked chats in `apps/api/src/pono_api/application/quotas.py`, with integration tests in `apps/api/tests/integration/test_chat_alerts.py`, per FR-025
- [X] T092 Expose `POST /me/chat-link`, `POST /me/chat-link/confirm`, `DELETE /me/chat`, `chatLinked` / `chatAlertsEnabled` on `/me` and `chat` in the health probe (`apps/api/src/pono_api/api/me.py`, `main.py`), regenerate `packages/sdk`, per contracts/openapi.yaml
- [X] T093 Let the person link and unlink the chat from the Alerts section of `apps/web/src/features/connections/Connections.tsx`, with French and English catalog entries and the e2e mock updated, per FR-025 and D-013
- [ ] T094 Configure the bot token on `pono-api` and `pono-worker`, link the author's chat and prove one alert received, recorded in `docs/VERITE_ET_PREUVES.md`, per SC-004
  - *Bot configured and the author's chat linked in production on 2026-09-23 (confirmation message received, token redacted in logs). Left: the first real alert, when a quota crosses 80 %; no consumption is faked in production.*

