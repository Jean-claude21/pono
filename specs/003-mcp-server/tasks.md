---
description: "Task list for 003-mcp-server"
---

# Tasks: Le serveur MCP et le plugin

**Input**: Design documents from `specs/003-mcp-server/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: included. Parity between agent tools and console routes (SC-001), the absence of
approval and rollback execution among the tools (SC-002), tokens stored only as digests (SC-005)
and organization isolation are gates proven by tests.

**Organization**: grouped by user story. Code, identifiers and comments in English (D-013).

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

- [ ] T001 Add the official `mcp` SDK (series 2) to `apps/api/pyproject.toml` and lock it; add the settings of the authorization server to `apps/api/src/pono_api/config.py` (issuer and resource derived from `PONO_PUBLIC_URL`, consent page, lifetimes)
- [ ] T002 [P] Merge `specs/003-mcp-server/contracts/openapi.yaml` in the contract checker and read `specs/003-mcp-server/contracts/error-codes.md` in `apps/web/src/lib/catalogs.test.ts`

---

## Phase 2: Foundational

- [ ] T003 Write migration `apps/api/migrations/versions/0006_agent_access.py`: `agent_clients`, `agent_requests`, `agent_grants`, `agent_tokens`, `rollback_requests` with forced RLS in this migration; the pre-authentication tables reachable only through `SECURITY DEFINER` functions (`pono_agent_register`, `pono_agent_client`, `pono_agent_open_request`, `pono_agent_request`, `pono_agent_decide`, `pono_agent_redeem_code`, `pono_agent_token`) owned by the bypassing role (data-model)
- [ ] T004 [P] Add scopes and the actor of an action in `apps/api/src/pono_api/domain/agents.py` (person or agent, with the client name and the granting person), with unit tests
- [ ] T005 Pass the actor to the use cases that act (import, refresh request, evaluation request, protection, rollback) and journal the new event kinds (`project.imported`, `project.refresh_requested`, `release.evaluation_requested`), console routes passing the person (research R-06, FR-012)
- [ ] T006 [P] Extend `apps/api/tests/security/`: new tables have forced RLS; the definer functions are owned by the bypassing role; no token or code value is stored, only digests; an organization never sees another's grants, tokens or requests

**Checkpoint**: the base holds agents' access under RLS; every action knows who did it.

---

## Phase 3: User Story 1 — Relier son agent, en donnant son accord (P1) 🎯 MVP

- [ ] T007 [US1] Port the OAuth broker of KYA-Platform to `apps/api/src/pono_api/infrastructure/oauth/broker.py` over the definer functions and RLS (research R-02): registration, authorization, consent, code exchange with PKCE, refresh with rotation, revocation
- [ ] T008 [US1] Mount the authorization routes and the protected resource metadata in `apps/api/src/pono_api/main.py`; accept the public host forwarded by the console
- [ ] T009 [US1] Add `GET /oauth/consent` and `POST /oauth/consent/{approve|deny}` in `apps/api/src/pono_api/api/oauth.py` (session required; allowed logins only)
- [ ] T010 [US1] Integration test of the full flow in `apps/api/tests/integration/test_agent_oauth.py`: register, authorize, consent (read and act), exchange, refresh, revoke; denied consent; expired request; unknown redirect; a person outside the allowed list refused
- [ ] T011 [US1] Consent page `apps/web/src/routes/oauth.consent.tsx`: sign in first when needed and come back to the same request; client, access choice, organization; French and English
- [ ] T012 [US1] Console relays for `/mcp`, `/register`, `/authorize`, `/token`, `/revoke` and `/.well-known/*` in `apps/web/src/routes/`, forwarding the public host

**Checkpoint**: an agent registers alone and gets an access only after a person's consent.

---

## Phase 4: User Story 2 — Lire depuis l'agent (P1)

- [ ] T013 [US2] Tools server `apps/api/src/pono_api/mcp/server.py`: token verification into a principal (person, organization, client, scopes), last use recorded, instructions from `mcp/instructions.py` (D-006), read tools `list_projects`, `get_project`, `list_releases`, `read_journal`, `list_repositories` annotated read-only
- [ ] T014 [US2] Parity tests in `apps/api/tests/integration/test_agent_tools.py`: each read tool returns the same document as its console route; a foreign project answers `project.not_found`

---

## Phase 5: User Story 3 — Agir depuis l'agent, sauf valider (P1)

- [ ] T015 [US3] Action tools `import_project`, `refresh_project`, `evaluate_release`, `protect_production`, `request_rollback` annotated destructive, refused with `agent.scope_insufficient` on a read-only access, journaled as the agent
- [ ] T016 [US3] Rollback requests in `apps/api/src/pono_api/application/rollback_requests.py`: request, confirm (runs the phase 2 rollback), dismiss, expire after 24 hours in the worker; `rollbackRequest` on the project detail; verdict `rollback.requested`; routes `POST /projects/{id}/rollback-requests/{rid}/{confirm|dismiss}`
- [ ] T017 [US3] Tests: action parity and journal author; no tool approves a release or runs a rollback (tool list checked); rollback request lifecycle
- [ ] T018 [US3] Console: the agent's rollback request on the project with Confirm and Dismiss, and in the workshop verdicts; catalogs

---

## Phase 6: User Story 4 — Voir et couper l'accès des agents (P2)

- [ ] T019 [US4] `GET /agents` and `DELETE /agents/{grantId}` in `apps/api/src/pono_api/api/agents.py`; a revoked grant refuses its next call; tests
- [ ] T020 [US4] Agents section in `apps/web/src/features/connections/Agents.tsx`: client, access, granted, last used, Revoke; catalogs

---

## Phase 7: User Story 5 — Plugin léger, savoir-faire servi (P2)

- [ ] T021 [P] [US5] Plugin `plugins/pono/` (`.claude-plugin/plugin.json`, `.mcp.json` to the public `/mcp`, two entry commands) and `.claude-plugin/marketplace.json`
- [ ] T022 [US5] Connection steps for Claude Code, the Claude app and Codex in `docs/EXPLOITATION.md`

---

## Phase 8: User Story 6 — Politique de confidentialité (P3)

- [ ] T023 [US6] Public page `apps/web/src/routes/privacy.tsx`, French and English, linked from the landing and the consent page; each statement tied to `docs/VERITE_ET_PREUVES.md`

---

## Phase 9: Polish

- [ ] T024 [P] Regenerate `packages/sdk`; contract test of the new console routes
- [ ] T025 [P] Playwright: consent page, agents list and revoke, rollback request, privacy page; French and English; no horizontal scroll
- [ ] T026 [P] Domain purity test covers the new modules
- [ ] T027 Deploy from `dev`; check the public metadata, then connect Claude Code, the Claude app and Codex and run quickstart steps 4 to 8, timing the connection of a new agent (SC-003); record in `docs/VERITE_ET_PREUVES.md` (SC-001, SC-003, author's clients)
- [ ] T028 Update `docs/ROADMAP.md`, `CLAUDE.md` and `docs/EXPLOITATION.md`

## Dependencies & Execution Order

Setup → Foundational → US1 → US2 → US3; US4 after US1; US5 and US6 anytime after US1; Polish last.

## Implementation Strategy

MVP: US1 + US2 (an agent reads the workshop after the person's consent). Then US3, US4, US5, US6.
