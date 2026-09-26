---
description: "Task list for 004-dev-runtime"
---

# Tasks: Le runtime de développement

**Input**: Design documents from `specs/004-dev-runtime/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: included. The production database refused (SC-003), the closed address (SC-002), no
lost write (SC-004), the bounded Git write (D-019), organization isolation and console/agent parity
(principle VIII) are gates proven by tests. The gate is tested with `node --test`.

**Organization**: grouped by user story. Code, identifiers and comments in English (D-013).

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [X] T001 Merge `specs/004-dev-runtime/contracts/openapi.yaml` in `apps/api/tests/contract/openapi_check.py` and read `specs/004-dev-runtime/contracts/error-codes.md` in `apps/web/src/lib/catalogs.test.ts`
- [X] T002 [P] Add a `node --test apps/api/tests/gate/` step to the api job of `.github/workflows/ci.yml`

---

## Phase 2: Foundational

- [X] T003 Write migration `apps/api/migrations/versions/0007_dev_runtime.py`: `runtimes`, `runtime_writes`, `runtime_saves` with forced RLS and member policies in this migration, composite organization keys, one runtime per project (data-model)
- [X] T004 [P] Domain `apps/api/src/pono_api/domain/runtimes.py`: states, started states, limits, `writable_path`, ticket signing and checking; unit tests in `apps/api/tests/unit/test_runtime_domain.py`
- [X] T005 Ports in `apps/api/src/pono_api/application/ports.py`: `RuntimeHost` (create, start, stop, delete, status), `RuntimeChannel` (status, write), database `development_target`, code host `commit_to_development`, `add_deploy_key`, `remove_deploy_key`, `propose_files`; `ProviderFactory.runtime_host`
- [X] T006 [P] Extend `apps/api/tests/security/`: new tables have forced RLS; the RLS catalog knows them; an organization never sees another's runtimes, writes or saves

**Checkpoint**: the base holds runtimes under RLS; the domain knows what may be written.

---

## Phase 3: User Story 1 — Démarrer le runtime (P1) 🎯 MVP

- [X] T007 [P] [US1] Gate assets in `apps/api/src/pono_api/infrastructure/runtime/assets/`: `Dockerfile` (Fluxio's, pnpm pinned by argument), `dev.mjs` (Vite with `allowedHosts` and HMR on wss:443, errors over IPC), `gate.mjs` (proxy to Vite with WebSocket, branch sync of research R-06, `/__pono/status`); `node --test` in `apps/api/tests/gate/`
- [X] T008 [P] [US1] Coolify runtime host in `apps/api/src/pono_api/infrastructure/providers/coolify.py` (research R-02: key, application from a deploy key, variables, start, stop, delete, status; server and domain choice), with transport tests in `apps/api/tests/unit/test_runtime_adapters.py`
- [X] T009 [P] [US1] Code host: `propose_files` (several files, one proposal towards the development branch), `add_deploy_key` read-only, `remove_deploy_key` in `apps/api/src/pono_api/infrastructure/providers/github.py`, with transport tests
- [X] T010 [P] [US1] Database development target in `apps/api/src/pono_api/infrastructure/providers/neon.py`: connection address of the development branch and the hosts of development and production, with transport tests
- [X] T011 [US1] Gate channel `apps/api/src/pono_api/infrastructure/runtime/channel.py` (status, write; bearer token); factory wiring in `infrastructure/providers/registry.py` and `defaults.py`
- [X] T012 [US1] Use cases in `apps/api/src/pono_api/application/runtimes.py`: request (eligibility, limits, proposal or provisioning), provision after the proposal merged, stop, read (with limits), journal events; production database refused (research R-03)
- [X] T013 [US1] Worker job `apps/api/src/pono_api/workers/runtimes.py` every 15 s: proposal state, host status, gate status (awake, activity, errors, conflicts, database host checked against production)
- [X] T014 [US1] Routes `GET/POST/DELETE /projects/{id}/runtime` in `apps/api/src/pono_api/api/runtimes.py` and schemas
- [X] T015 [US1] Integration tests `apps/api/tests/integration/test_runtimes.py`: proposal then provisioning then ready; stack, database missing, production database and limit refused; stop; unreachable; a production database seen at a reading stops the runtime

**Checkpoint**: a runtime is requested, proposed, created, followed and stopped.

---

## Phase 4: User Story 2 — Écrire et voir l'écran changer (P1)

- [X] T016 [US2] Gate `PUT /__pono/files` (path revalidated, atomic write, wakes Vite) in `gate.mjs`, with `node --test`
- [X] T017 [US2] Code host `commit_to_development` in `github.py`: tree on the known head, commit, reference moved without force; conflicting paths returned; guard refusing any branch but the named development branch and always the default branch (D-019); transport tests
- [X] T018 [US2] Use cases `apps/api/src/pono_api/application/runtime_writes.py`: write and delete through the gate, then kept pending; save by author after 60 s quiet, before stop and on demand; conflicts; content erased once saved; journal `runtime.changes_saved`, `runtime.save_conflict`
- [X] T019 [US2] Routes `PUT/DELETE /projects/{id}/runtime/files`, `POST /projects/{id}/runtime/save`; worker saves due batches
- [X] T020 [US2] Integration tests `apps/api/tests/integration/test_runtime_writes.py`: write reaches the gate and is saved once, grouped; refused paths and sizes; unreachable gate writes nothing; conflict kept then lifted by a new write; nothing lost across a stop

---

## Phase 5: User Story 3 — Une adresse fermée au monde (P1)

- [X] T021 [US3] Gate authentication: cookie, `/__pono/auth` ticket check (one use, 2 minutes, local return), redirection to the console, WebSocket refused without cookie; `node --test` with tickets signed by the Python domain code (shared vectors)
- [X] T022 [US3] Route `POST /projects/{id}/runtime/ticket` and console route `apps/web/src/routes/runtime.open.tsx` (signed in, otherwise sign-in with return; `"/runtime/open"` accepted as a return path in `api/auth.py`)
- [X] T023 [US3] Tests: ticket for a member, not found for another organization, sign-in return

---

## Phase 6: User Story 4 — Veille et réveil (P2)

- [X] T024 [US4] Gate sleep after `PONO_SLEEP_AFTER_SECONDS` without HTTP request or write; wake on request (waiting page) or write; `node --test` with a short delay

---

## Phase 7: User Story 5 — Les erreurs remontent (P2)

- [X] T025 [US5] Gate error store (IPC from `dev.mjs`, `/__pono/report`, injected `/__pono/reporter.js`, dedupe, secrets masked, resolved on successful update), `node --test`
- [X] T026 [US5] Route `GET /projects/{id}/runtime/errors` (live, otherwise last reading), masked again with the phase 2 secret shapes; tests

---

## Phase 8: User Story 6 — Des limites claires (P3)

- [X] T027 [US6] Limits on the runtime document (started out of 3, 1 GiB, 15 minutes); host stop read as `runtime.stopped_by_host`; tests

---

## Phase 9: Agents and console

- [X] T028 Seven tools in `apps/api/src/pono_api/mcp/server.py` (contracts/mcp-tools.md) and instructions; parity tests in `apps/api/tests/integration/test_agent_tools.py`
- [X] T029 Console: `apps/web/src/features/runtime/RuntimePanel.tsx` on the project (state, reason, open, start, stop, save, database, limits, pending writes, last save, conflicts, errors) and `FileForm.tsx` (path with text or dropped file; delete); verdicts `runtime.*`; FR and EN catalogs
- [X] T030 [P] Regenerate `packages/sdk`; contract test of the new routes
- [X] T031 [P] Playwright: runtime panel, file form, open link; FR and EN; no horizontal scroll
- [X] T032 [P] Domain purity test covers `domain/runtimes.py` and the new application modules

---

## Phase 10: Proof and polish

- [ ] T033 Deploy from `dev`; run quickstart steps 1 to 9 on fluxio-runtime-test with the author; publish the twenty measures of SC-001 as they are, and SC-002 to SC-007, in `docs/VERITE_ET_PREUVES.md`
- [X] T034 Update `docs/ROADMAP.md`, `CLAUDE.md` and `docs/EXPLOITATION.md` (runtime operation, the author's Coolify token rights)

## Dependencies & Execution Order

Setup → Foundational → US1 → US2 → US3; US4 and US5 after US1 (gate); US6 after US1; agents and
console after US2 and US3; proof last.

## Implementation Strategy

MVP: US1 + US2 + US3 (a closed runtime that shows each write in seconds). Then US4, US5, US6.
