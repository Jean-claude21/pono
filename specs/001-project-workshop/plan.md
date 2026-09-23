# Implementation Plan: L'atelier qui tient les projets

**Branch**: `001-project-workshop` | **Date**: 2026-09-22 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-project-workshop/spec.md`

## Summary

Voir l'état réel de ses propres projets au même endroit, et reprendre l'un d'eux en moins d'une
minute. Un service FastAPI (D-010), repris du socle de KYA-Platform, porte le domaine cloisonné par
organisation en RLS Postgres, les adaptateurs de fournisseurs, et un planificateur qui relève états,
adresses et quotas. La console TanStack Start affiche l'atelier dans le design validé (D-011), en
français et en anglais dès le départ (D-013), et relaie les appels au service sur la même origine.
Un projet sans manifeste reçoit un manifeste pré-rempli, proposé en pull request (FR-018).

## Technical Context

**Language/Version**: Python 3.14 (service) · TypeScript 5.8 sur Node 22 (console)

**Primary Dependencies**: FastAPI, SQLAlchemy 2 async + asyncpg, Alembic, pydantic-settings,
httpx, PyJWT, cryptography (Fernet) · TanStack Start, Paraglide JS, `@pono/design`,
openapi-typescript + openapi-fetch

**Storage**: PostgreSQL serverless (projet Neon `pono`, branches `main` et `dev`), RLS forcée

**Testing**: pytest (+ pytest-asyncio, couverture ≥ 90 %), tests de contrat sur l'OpenAPI, tests de
cloisonnement RLS contre une vraie base · Vitest (console), Playwright pour les parcours et le rendu

**Target Platform**: conteneurs Linux sur Coolify (D-012) : `pono-api`, `pono-worker`, `pono-web`

**Project Type**: application web — service + console, monodépôt pnpm + uv

**Performance Goals**: reprise d'un projet < 60 s (SC-002) ; import < 2 min (SC-003) ; relevé de
chaque projet au plus toutes les 15 min (FR-022)

**Constraints**: aucun secret dans le dépôt ni dans les journaux ; aucun nom de fournisseur dans le
domaine (D-002) ; aucune écriture hors des branches `pono/*` (FR-029) ; aucun texte visible en dur
(D-013) ; paliers gratuits uniquement (« 0 € »)

**Scale/Scope**: 2 personnes, 2 organisations, ~20 projets, 4 adaptateurs (GitHub, Netlify, Coolify,
Neon), 2 langues

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Statut | Comment le plan le tient |
|---|---|---|
| I. Simple et fonctionnel | ✅ | un service, un worker, une console ; pas de file de messages ni de moteur d'autorisation externe |
| II. Obéir à l'étape en cours | ✅ | runtime, MCP, plugin, garde-fous de mise en ligne, invitations : hors plan |
| III. Aucun fournisseur dans le cœur | ✅ | ports `CodeHost`, `HostingProvider`, `DatabaseProvider`, `QuotaReader`, `Mailer` ; le domaine ne connaît qu'un identifiant d'adaptateur opaque |
| IV. Garde-fou mécanique | ✅ | l'adaptateur de code refuse toute écriture hors `pono/*` et n'a pas de méthode de fusion ; test dédié |
| V. Vérité dans le dépôt | ✅ | manifeste `.pono/project.json`, état reconstructible depuis le dépôt et les fournisseurs |
| VI. Sécurité dans la base | ✅ | RLS + `FORCE` dans chaque migration créatrice, rôle applicatif non propriétaire |
| VII. Rien sans preuve | ✅ | source de chaque limite affichée ; métrique absente = « non disponible » ; chaque donnée datée |
| VIII. Aucun chemin réservé à un agent | ✅ | aucune surface agent dans cette phase |
| Code en anglais, i18n (D-013) | ✅ | Paraglide, catalogues fr / en, codes d'erreur stables |
| Jamais de secret en dur (D-007) | ✅ | Fernet au repos, jetons d'installation courts, cookie `HttpOnly` |
| **Un seul chemin technique en V1 (D-009)** | ✅ écart validé | deux hébergeurs (Netlify et Coolify), validé par D-014 — voir *Complexity Tracking* |

**Re-check après la conception (Phase 1)** : inchangé. Le modèle de données ne contient aucun nom de
fournisseur dans ses règles ; la colonne `provider` n'est qu'un identifiant d'adaptateur.

## Project Structure

### Documentation (this feature)

```text
specs/001-project-workshop/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml
│   ├── manifest.schema.json
│   └── error-codes.md
├── checklists/requirements.md
└── tasks.md              # /speckit-tasks
```

### Source Code (repository root)

```text
apps/
├── api/                              # service FastAPI (paquet Python pono_api)
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── migrations/versions/          # RLS dans chaque migration créatrice
│   ├── src/pono_api/
│   │   ├── domain/                   # organizations, projects, state rules — aucun fournisseur
│   │   ├── application/              # import, refresh, quotas, alerts, sessions
│   │   ├── infrastructure/
│   │   │   ├── database/             # sessions async, repositories, RLS context
│   │   │   ├── providers/            # github, netlify, coolify, neon (adaptateurs)
│   │   │   ├── manifests/            # lecteurs : pono, studio-project-yaml, fluxio, livio
│   │   │   ├── crypto.py             # Fernet (repris de KYA-Platform)
│   │   │   └── mailer.py             # SMTP générique
│   │   ├── api/                      # routes FastAPI, codes d'erreur
│   │   ├── workers/                  # planificateur, relevés, vérification d'adresses
│   │   └── main.py
│   ├── tests/{unit,contract,integration,security}/
│   └── Dockerfile                    # image unique : pono-api et pono-worker
└── web/                              # console TanStack Start
    ├── messages/{fr,en}.json         # catalogues Paraglide
    ├── project.inlang/settings.json
    └── src/
        ├── routes/                   # landing, atelier, détail projet, /api/$ (relais)
        ├── features/workshop/        # liste, filtres, verdicts
        ├── features/projects/        # détail, import
        └── lib/                      # client SDK, formats Intl

packages/
├── design/                           # @pono/design (phase 0)
└── sdk/                              # @pono/sdk, généré depuis l'OpenAPI

pyproject.toml                        # espace de travail uv
```

**Structure Decision**: application web en monodépôt. Le service Python rejoint `apps/api` dans un
espace de travail `uv` à la racine, sur le modèle de KYA-Platform ; la console garde `apps/web` et
consomme `@pono/design` et `@pono/sdk`. Une seule image pour le service et le worker, lancés avec
deux commandes différentes.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Deux hébergeurs (Netlify **et** Coolify) au lieu d'un chemin unique (D-009) | Les projets réels de l'auteur sont répartis entre les deux ; Pono lui-même tourne sur Coolify (D-012). Sans Coolify, SC-001 (cinq projets réels) est inatteignable. L'adaptateur Coolify est en lecture seule et existe déjà dans KYA-Platform. | Netlify seul : seuls deux projets réels ont une production. Coolify seul : perd le cas des paliers gratuits, qui porte la promesse « 0 € ». |
| RLS + fonction `SECURITY DEFINER` pour résoudre la session | Seule porte d'entrée avant que la personne soit connue, sans ouvrir la table des sessions au rôle applicatif | Désactiver la RLS sur les sessions : contredit le principe VI |
