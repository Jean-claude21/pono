---
description: "Task list for 002-guarded-release"
---

# Tasks: La mise en ligne sous garde-fou

**Input**: Design documents from `specs/002-guarded-release/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: included. Fail-closed guards (FR-007), the append-only journal (SC-007), the absence of
secret values (SC-006) and the rule that only a signed-in person approves (FR-011) are gates proven
by tests, as in phase 1.

**Numbering**: T041 was added by `speckit-analyze` and sits in Polish.

**Organization**: grouped by user story. All code, identifiers and comments are in English (D-013).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an unfinished task)
- **[Story]**: the user story the task serves (US1 … US5)
- Paths are relative to the repository root.

---

## Phase 1: Setup

**Purpose**: dependency and contract tooling for the phase.

- [ ] T001 Add `sqlglot` to `apps/api/pyproject.toml` and lock it (`uv lock`)
- [ ] T002 [P] Make the contract checker load `specs/001-project-workshop/contracts/openapi.yaml` and merge `specs/002-guarded-release/contracts/openapi.yaml` over it (paths added, same-named schemas replaced) in `apps/api/tests/contract/openapi_check.py` (research R-10)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: data, domain and ports every story needs. No story starts before this phase ends.

- [ ] T003 Write migration `apps/api/migrations/versions/0005_guarded_release.py`: `projects.protection_status` and `protection_checked_at`; tables `releases`, `release_checks`, `release_approvals`, `rollbacks`, `project_events` with composite organization keys, `ENABLE` + `FORCE ROW LEVEL SECURITY` and organization policies in this migration; `pono_app` gets only `SELECT, INSERT` on `project_events` and `release_approvals`; a trigger refuses `UPDATE` and `DELETE` on `project_events` for every role (data-model)
- [ ] T004 [P] Add the domain of releases in `apps/api/src/pono_api/domain/releases.py`: `Verdict`, `Guard`, `GuardStatus`, `Finding`, and the pure function `verdict(results, approved_sha, head_sha)` with the transitions of data-model, plus unit tests in `apps/api/tests/unit/test_release_domain.py`
- [ ] T005 [P] Add the optional `release` section (`migrations`, `exampleFiles`, `declaredDestructions`) to `apps/api/src/pono_api/domain/manifest.py` and to `specs/001-project-workshop/contracts/manifest.schema.json`, with tests in `apps/api/tests/unit/test_manifest.py`
- [ ] T006 Extend the ports in `apps/api/src/pono_api/application/ports.py`: `CodeHost.list_changes`, `change_files`, `set_release_check`, `read_protection`, `apply_protection`; `HostingProvider.find_preview`, `rollback`; data classes `ChangeRequest`, `ChangedFile`, `PreviewState`, `ProtectionState`, `RollbackTarget` (research R-01, R-05, R-07, R-08)
- [ ] T007 Add the evidence journal in `apps/api/src/pono_api/application/journal.py`: `record(session, event)` and `read(session, project_id, before)` over `project_events`
- [ ] T008 [P] Extend the test fakes in `apps/api/tests/fakes.py` (changes, files, check states, protection, previews, rollbacks) so every story is testable without a provider
- [ ] T009 [P] Add the security tests in `apps/api/tests/security/test_journal.py` and extend `test_rls_catalog.py`: every new table has forced RLS; `pono_app` cannot update or delete a journal entry; the owner cannot either (trigger); two organizations never see each other's releases or events

**Checkpoint**: the base holds the new records under RLS; the ports describe what the stories need.

---

## Phase 3: User Story 1 — Une mise en ligne dangereuse est refusée, mécaniquement (Priority: P1) 🎯 MVP

**Goal**: every change towards the production branch is evaluated; a secret, a destructive migration or a missing preview refuses it, and the code host blocks the merge.

**Independent Test**: open a change with `ALTER TABLE … DROP COLUMN` against a protected project; the verdict is "refused", the migrations guard names the file and operation, the `pono/release` check is failing, and `release.refused` is in the journal.

### Tests for User Story 1

- [ ] T010 [P] [US1] Unit tests for the secrets guard in `apps/api/tests/unit/test_guard_secrets.py`: provider tokens, private key blocks, database URLs with a password, literal assignments, `.env` files, example files excluded, only added lines read, no value in any finding, oversized text file fails closed
- [ ] T011 [P] [US1] Unit tests for the migrations guard in `apps/api/tests/unit/test_guard_migrations.py`: each destructive operation of research R-04 refused with its code; additive statements pass; unparseable SQL and non-SQL migration files fail; rewritten history fails; a declared destruction passes only when isolated
- [ ] T012 [P] [US1] Unit tests for the preview guard in `apps/api/tests/unit/test_guard_preview.py`: missing, building, failed, down, timeout after 30 min, ready on the head commit only
- [ ] T013 [US1] Integration tests in `apps/api/tests/integration/test_releases.py`: a new change creates a release; a refusal sets the failing check and writes `release.opened`, `release.evaluated`, `release.refused`; a new version re-evaluates; a provider outage keeps the verdict blocking (FR-007)

### Implementation for User Story 1

- [ ] T014 [P] [US1] Implement the secrets guard in `apps/api/src/pono_api/application/guards/secrets.py` (research R-03)
- [ ] T015 [P] [US1] Implement the migrations guard in `apps/api/src/pono_api/application/guards/migrations.py` with `sqlglot` (research R-04)
- [ ] T016 [P] [US1] Implement the preview guard in `apps/api/src/pono_api/application/guards/preview.py` over `HostingProvider.find_preview` and the phase 1 link checker (research R-05)
- [ ] T017 [P] [US1] Implement `list_changes`, `change_files` and `set_release_check` (check run `pono/release`, bounded writer that only creates or updates that check) in `apps/api/src/pono_api/infrastructure/providers/github.py`, with unit tests on a mocked transport in `apps/api/tests/unit/test_providers.py`
- [ ] T018 [P] [US1] Implement `find_preview` for Netlify (`deploy-preview` by review id and commit) and Coolify (deployment by pull request id and commit, preview URL template) in `apps/api/src/pono_api/infrastructure/providers/netlify.py` and `coolify.py`, with unit tests
- [ ] T019 [US1] Implement the release use case in `apps/api/src/pono_api/application/releases.py`: sync open changes of each project, evaluate the three guards on a new head, store checks, compute the verdict, set the code host check, write the journal (including `release.destruction_declared`); detect merged and closed changes (FR-001, FR-002, FR-019, research R-02, R-11)
- [ ] T020 [US1] Add the `releases` job every 60 s in `apps/api/src/pono_api/workers/refresh.py` and `workers/runner.py` (FR-003, SC-003)
- [ ] T021 [US1] Expose `GET /projects/{projectId}/releases` and `POST …/releases/{releaseId}/evaluation` in `apps/api/src/pono_api/api/releases.py` and `api/schemas.py`; add `release.refused` and `release.merged_without_approval` to the workshop verdicts; regenerate `packages/sdk`
- [ ] T022 [US1] Show the releases of a project in `apps/web/src/features/releases/Releases.tsx` inside the project detail: verdict banner (D-011), each guard with its findings, "Evaluate now"; French and English catalog entries for every verdict and guard code (contracts/error-codes.md, FR-003, FR-021, FR-022)

**Checkpoint**: a dangerous change is refused and blocked at the code host, and the console says why.

---

## Phase 4: User Story 2 — Rien n'entre en production sans une validation humaine (Priority: P1)

**Goal**: a change whose guards pass waits for an explicit approval in the console, on its exact version.

**Independent Test**: with all guards passing, the merge stays blocked; approve in the console; the check turns green on that commit; a new commit invalidates it.

- [ ] T023 [US2] Integration tests in `apps/api/tests/integration/test_approval.py`: approval only on `awaiting_approval`; `release.not_ready` and `release.version_changed` refusals; a new head writes `release.approval_invalidated` and a pending check; the approval needs a person session (no other credential works); `release.closed` on a merged or closed change; a code host outage during approval answers `provider.unavailable` and records nothing; approval of another organization's release answers 404 (FR-009 to FR-012)
- [ ] T024 [US2] Implement the approval in `apps/api/src/pono_api/application/releases.py` and `POST /projects/{projectId}/releases/{releaseId}/approval` in `apps/api/src/pono_api/api/releases.py` (research R-06)
- [ ] T025 [US2] Add the approval to the console in `apps/web/src/features/releases/Releases.tsx`: the "Approve" action only for `awaiting_approval`, with the commit shown and sent; nothing to approve on a refused verdict; `release.awaiting_approval` in the workshop verdicts

**Checkpoint**: nothing reaches production without a recorded human approval.

---

## Phase 5: User Story 3 — La branche de production est protégée, et on le sait (Priority: P1)

**Goal**: protection read at import and at every reading; applied by Pono on a click.

**Independent Test**: an unprotected project is flagged; "Protect production" applies the rule; a direct push is then refused by the code host.

- [ ] T026 [P] [US3] Implement `read_protection` and `apply_protection` in `apps/api/src/pono_api/infrastructure/providers/github.py`: required change request with no minimum approvals, required `pono/release` check bound to the app id, enforced for administrators, no force push or deletion; plan refusal maps to `unavailable_on_plan`; a dedicated guard allows only the production branch protection endpoint (research R-07), with unit tests
- [ ] T027 [US3] Implement `apps/api/src/pono_api/application/protection.py`: read at import and in the project reading, write `protection.missing`, `protection.restored`, `protection.unavailable` on change; apply on request and write `protection.applied` (FR-013, FR-014, SC-004); integration tests in `apps/api/tests/integration/test_protection.py`
- [ ] T028 [US3] Expose `POST /projects/{projectId}/protection` and `protection` on the project detail; add `project.unprotected` and `project.protection_unavailable` to the workshop verdicts in `apps/api/src/pono_api/api/`
- [ ] T029 [US3] Show the protection fact and the "Protect production" action in `apps/web/src/features/projects/ProjectDetail.tsx`, with its catalog entries and the error codes of contracts/error-codes.md

**Checkpoint**: the block is mechanical on every protected project, and an unprotected one is visible.

---

## Phase 6: User Story 4 — Revenir à la version précédente en un geste (Priority: P2)

**Goal**: production back to the previous successful deployment from the console.

**Independent Test**: roll back a real project; production serves the previous deployment and the journal has `rollback.requested` then `rollback.succeeded`.

- [ ] T030 [P] [US4] Implement `rollback` for Netlify (restore deploy) and Coolify (`POST /applications/{uuid}/rollback` with the image commit from `rollback-images`) in the hosting adapters, key uses traced, with unit tests (research R-08)
- [ ] T031 [US4] Implement `apps/api/src/pono_api/application/rollback.py` and `POST /projects/{projectId}/rollback`: target = previous successful production deployment; `rollback.no_previous`, `rollback.in_progress`; outcome confirmed by the next reading; `rollback.failed` in the workshop verdicts; `canRollback` on the project detail; integration tests in `apps/api/tests/integration/test_rollback.py`
- [ ] T032 [US4] Add "Revenir à la version précédente" with an explicit confirmation in `apps/web/src/features/projects/ProjectDetail.tsx`, and its catalog entries

**Checkpoint**: a bad release costs one confirmed click.

---

## Phase 7: User Story 5 — Le journal de preuves de chaque projet (Priority: P2)

**Goal**: read the append-only history of a project.

**Independent Test**: after a refusal, an approval and a rollback, the journal lists all three, newest first, with author and time.

- [ ] T033 [US5] Expose `GET /projects/{projectId}/journal?before=` in `apps/api/src/pono_api/api/releases.py`, 50 entries per page, with an integration test
- [ ] T034 [US5] Add the journal page `apps/web/src/routes/workshop/projects.$projectId.journal.tsx` and `apps/web/src/features/releases/Journal.tsx`, linked from the project detail; every event kind translated in French and English

**Checkpoint**: every decision on a project can be shown.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T041 [P] Add a test in `apps/api/tests/security/test_domain_purity.py` that fails when a provider name appears under `apps/api/src/pono_api/domain/` or `application/` (FR-023, constitution III)
- [ ] T035 [P] Extend the contract test in `apps/api/tests/contract/test_projects_contract.py` to every phase 2 route and error, against the merged contract
- [ ] T036 [P] Add Playwright scenarios in `apps/web/tests/e2e/releases.spec.ts` with the mock service: refused verdict with findings, approval, protection, rollback confirmation, journal; no horizontal scroll; French and English
- [ ] T037 Request the app permissions "Checks: write" and "Administration: write" for `pono-atelier` (author gesture) and record the step in `docs/EXPLOITATION.md`
- [ ] T038 Deploy on Coolify from `dev`, protect lectio-reads from the console, and run quickstart steps 1 to 5 on it; check that every production merge of the protected projects has an approval (SC-001, SC-002); record the results in `docs/VERITE_ET_PREUVES.md`
- [ ] T039 Record the demonstration of quickstart step 6 (unaccelerated), publish it, and link it in `docs/VERITE_ET_PREUVES.md` (SC-008, author gesture)
- [ ] T040 Update `docs/ROADMAP.md` (phase 2 status), `CLAUDE.md` (current phase) and `README.md`

---

## Dependencies & Execution Order

- **Setup (T001–T002)** → **Foundational (T003–T009)** → stories.
- **US1 (T010–T022)** first: it creates the releases every other story acts on.
- **US2 (T023–T025)** needs US1. **US3 (T026–T029)** needs only Foundational and can run beside US1;
  the demonstration needs both.
- **US4 (T030–T032)** and **US5 (T033–T034)** need Foundational only.
- **Polish** last; T038 and T039 need US1, US2 and US3 deployed.

## Parallel Execution Examples

- Foundational: T004, T005, T008 and T009 together after T003.
- US1: T010, T011, T012 together; then T014, T015, T016, T017, T018 together; then T019 → T020 → T021 → T022.
- US3 and US4 adapters (T026, T030) beside US1 implementation.

## Implementation Strategy

1. **MVP**: Setup → Foundational → US1 → US2 → US3. That is the promise of the phase: refused,
   approved, mechanically blocked.
2. **Then** US4 and US5.
3. **Finally** deploy, protect a real project, prove the refusal, record the demonstration.
