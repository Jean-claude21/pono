# Implementation Plan: La mise en ligne sous garde-fou

**Branch**: `002-guarded-release` | **Date**: 2026-09-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/002-guarded-release/spec.md`

## Summary

Pono évalue chaque proposition de changement vers la branche de production d'un projet importé :
trois garde-fous (secrets, migrations, preview), un verdict, puis une validation humaine dans la
console. Le blocage est porté par le fournisseur de code : une vérification `pono/release`
obligatoire, liée à l'app Pono, qui ne passe au vert qu'après la validation (research R-01). Pono
pose lui-même cette protection sur un clic (R-07), ne fusionne jamais, permet le retour arrière de
la production par l'API de l'hébergeur (R-08), et consigne tout dans un journal en ajout seul
garanti par la base (R-09). Tout réutilise le socle de la phase 1 : ports et adaptateurs, worker,
RLS, SDK généré, console et catalogues.

## Technical Context

**Language/Version**: Python 3.14 (service, worker) ; TypeScript 5.9 (console)

**Primary Dependencies**: FastAPI, SQLAlchemy async, Alembic, httpx ; **sqlglot** (nouveau, analyse
SQL, R-04) ; TanStack Start, Paraglide, `@pono/design`, `@pono/sdk`

**Storage**: Postgres serverless (Neon, projet `pono`, Francfort) ; migration `0005_guarded_release`

**Testing**: pytest (unitaires, intégration sur Postgres jetable, contrat, sécurité) ; Vitest ;
Playwright avec service simulé

**Target Platform**: Coolify (serveur de l'auteur) : `pono-web`, `pono-api`, `pono-worker`

**Project Type**: service web + console web (monorepo de la phase 1)

**Performance Goals**: verdict visible ≤ 2 min après la preview (SC-003) ; relevé des tentatives
toutes les 60 s (R-02) ; retour arrière ≤ 5 min hors construction (SC-005)

**Constraints**: échec fermé partout (FR-007) ; aucune valeur de secret stockée ou journalisée
(SC-006) ; Pono ne fusionne ni ne pousse sur la branche de production (FR-012) ; une seule écriture
hors branches de proposition, la règle de protection (FR-015)

**Scale/Scope**: deux personnes, trois projets réels en ligne, quelques propositions par jour

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Vérification | État |
|---|---|---|
| I. Simple et fonctionnel | Relevé par minute plutôt que webhooks ; motifs plutôt qu'un outil externe de secrets ; SQL seul | ✅ |
| II. Étape en cours | Rien de la phase 3 (MCP) ni 5 (rôles) ; agents seulement nommés comme auteurs | ✅ |
| III. Aucun fournisseur dans le cœur | Nouveaux ports `CodeHost` (protection, vérification, propositions) et `HostingProvider` (preview, retour arrière) ; noms dans les adaptateurs seulement | ✅ |
| IV. Garde-fou mécanique | Blocage par vérification obligatoire liée à l'app, chez le fournisseur de code ; aucun contournement depuis Pono (FR-008) | ✅ |
| V. Vérité dans le dépôt | Déclarations (migrations, exemples, destructions) dans le manifeste versionné | ✅ |
| VI. Sécurité dans la base | RLS forcée dans `0005` pour chaque table créée ; journal protégé par droits **et** déclencheur | ✅ |
| VII. Rien sans preuve | Démonstration enregistrée et consignée (SC-008) | ✅ |
| VIII. Aucun chemin réservé à un agent | Tout depuis la console ; la validation n'existe **que** pour une session de personne | ✅ |
| Jamais de secret en dur | Constats sans valeur ; usages de clés tracés pour le retour arrière (FR-024) | ✅ |
| Un seul chemin technique | Mêmes fournisseurs qu'en phase 1 ; deux écritures nouvelles, consignées en D-016 | ✅ justifié |

Re-vérifié après la conception (data-model, contrats) : aucune violation.

## Project Structure

### Documentation (this feature)

```text
specs/002-guarded-release/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml        # routes et schémas ajoutés, fusionnés sur ceux de la phase 1
│   └── error-codes.md
└── tasks.md                # /speckit-tasks
```

### Source Code (repository root)

```text
apps/api/
├── migrations/versions/0005_guarded_release.py
├── src/pono_api/
│   ├── domain/
│   │   ├── manifest.py                 # section `release` du manifeste
│   │   └── releases.py                 # verdict, garde-fous, transitions (pur)
│   ├── application/
│   │   ├── ports.py                    # CodeHost + HostingProvider étendus
│   │   ├── guards/
│   │   │   ├── secrets.py              # R-03
│   │   │   ├── migrations.py           # R-04 (sqlglot)
│   │   │   └── preview.py              # R-05
│   │   ├── releases.py                 # relevé, évaluation, validation, fusion détectée
│   │   ├── protection.py               # lecture et pose (R-07)
│   │   ├── rollback.py                 # R-08
│   │   └── journal.py                  # écriture et lecture du journal (R-09)
│   ├── infrastructure/providers/
│   │   ├── github.py                   # propositions, fichiers, vérification, protection
│   │   ├── netlify.py                  # preview par proposition, restauration
│   │   └── coolify.py                  # preview par proposition, retour arrière
│   ├── api/releases.py                 # routes de la phase 2
│   └── workers/                        # tâche `releases` toutes les 60 s
└── tests/                              # unit, integration, contract, security

apps/web/src/
├── features/releases/                  # verdicts, garde-fous, validation, journal
├── features/projects/ProjectDetail.tsx # protection, retour arrière, tentatives
└── routes/workshop/projects.$projectId.journal.tsx

packages/sdk/                           # régénéré
specs/001-project-workshop/contracts/manifest.schema.json  # section `release`
```

**Structure Decision**: même monorepo et mêmes couches qu'en phase 1 ; les garde-fous vivent dans
`application/guards/` car ce sont des règles de Pono sans fournisseur, et `sqlglot` y est une
bibliothèque d'analyse, pas un fournisseur.

## Complexity Tracking

| Écart | Pourquoi | Alternative plus simple rejetée |
|---|---|---|
| Deux écritures nouvelles chez les fournisseurs (protection, retour arrière) | La protection est la condition du blocage mécanique (US3) ; le retour arrière est exigé par FR-016 | Guider la personne chez le fournisseur (rejeté par l'auteur, clarification FR-015) ; épingler un commit Coolify (laisse un état à défaire, R-08) |
