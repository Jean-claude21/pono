# Implementation Plan: Le serveur MCP et le plugin

**Branch**: `003-mcp-server` | **Date**: 2026-09-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/003-mcp-server/spec.md`

## Summary

Pono ajoute un serveur d'outils pour agents (MCP, Streamable HTTP sans état) et son propre serveur
d'autorisation OAuth 2.1, portés du courtier de KYA-Platform et adaptés à la RLS de Pono
(research R-01, R-02). Le consentement se donne dans la console avec la session habituelle (R-03).
Chaque outil appelle la même fonction applicative que la route de la console et rend le même
document (R-04) ; valider une mise en ligne et exécuter un retour arrière restent hors de portée des
agents, qui peuvent seulement demander un retour arrière (R-05). Toute action d'agent est
journalisée à son nom (R-06). La console relaie les chemins MCP et OAuth (R-07), liste et révoque
les agents, et publie une politique de confidentialité (R-10). Un plugin Claude Code et une commande
Codex relient le même serveur (R-09).

## Technical Context

**Language/Version**: Python 3.14 (service) ; TypeScript 5.9 (console, plugin)

**Primary Dependencies**: FastAPI, SQLAlchemy async, Alembic ; **`mcp` (SDK officiel, série 2)**
(nouveau) ; TanStack Start, Paraglide, `@pono/design`, `@pono/sdk`

**Storage**: Postgres (Neon `pono`, Francfort) ; migration `0006_agent_access`

**Testing**: pytest (unitaires, intégration sur Postgres jetable, contrat, sécurité, parité
console/outils) ; Vitest ; Playwright avec service simulé

**Target Platform**: Coolify : `pono-web` (relais public), `pono-api` (MCP et OAuth), `pono-worker`

**Project Type**: service web + console web + plugin

**Performance Goals**: relier un agent en moins de 2 minutes (SC-003) ; un outil de lecture répond
aussi vite que la route de la console qu'il reprend

**Constraints**: jetons jamais stockés en clair (SC-005) ; aucune capacité d'agent sans équivalent
console (D-005) ; aucun outil de validation ni d'exécution de retour arrière (clarification) ;
cloisonnement par organisation

**Scale/Scope**: deux personnes, trois clients (Claude Code, application Claude, Codex)

## Constitution Check

| Principe | Vérification | État |
|---|---|---|
| I. Simple et fonctionnel | SDK officiel, sans état ; courtier porté, pas réécrit ; outils = mêmes fonctions que la console | ✅ |
| II. Étape en cours | Rien du runtime (phase 4) ni des rôles (phase 5) ; plusieurs organisations hors périmètre | ✅ |
| III. Aucun fournisseur dans le cœur | Le domaine ne nomme ni les agents ni leurs éditeurs ; le plugin vit hors du service | ✅ |
| IV. Garde-fou mécanique | Validation et retour arrière absents des outils par construction, prouvé par test | ✅ |
| V. Vérité dans le dépôt | Inchangé ; le plugin et sa configuration sont versionnés dans le dépôt | ✅ |
| VI. Sécurité dans la base | RLS forcée dans `0006` ; tables pré-authentification accessibles par fonctions `SECURITY DEFINER` seulement | ✅ |
| VII. Rien sans preuve | Politique de confidentialité rattachée au registre ; SC-001 prouvé avec de vrais clients | ✅ |
| VIII. Aucun chemin réservé à un agent | Chaque outil a sa route console ; la console en a plus (validation, confirmation) | ✅ |
| Jamais de secret en dur | Empreintes SHA-256 des jetons, secret client chiffré | ✅ |
| D-017 | Phase ouverte avant la fermeture formelle des phases 1 et 2 ; dettes de preuve visibles | ✅ justifié |

Re-vérifié après la conception : aucune violation.

## Project Structure

### Documentation (this feature)

```text
specs/003-mcp-server/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml       # routes console ajoutées
│   ├── error-codes.md
│   └── mcp-tools.md       # les outils et leur route équivalente
└── tasks.md
```

### Source Code (repository root)

```text
apps/api/
├── migrations/versions/0006_agent_access.py
├── src/pono_api/
│   ├── domain/agents.py                  # étendues, auteur d'une action (pur)
│   ├── application/
│   │   ├── actor.py                      # personne ou agent, passé aux cas d'usage
│   │   ├── agent_access.py               # consentement, liste, révocation
│   │   └── rollback_requests.py          # demande, confirmation, refus, expiration
│   ├── infrastructure/oauth/broker.py    # le courtier (porté de KYA-Platform)
│   ├── mcp/
│   │   ├── server.py                     # MCPServer, vérification des jetons, outils
│   │   └── instructions.py               # savoir-faire servi (D-006)
│   ├── api/oauth.py, api/agents.py       # routes de la console
│   └── main.py                           # montage des routes OAuth et de /mcp
└── tests/                                # unit, integration (flux OAuth, parité), security

apps/web/src/
├── routes/oauth.consent.tsx              # page de consentement
├── routes/privacy.tsx                    # politique de confidentialité
├── routes/mcp.ts, register.ts, authorize.ts, token.ts, revoke.ts, [.]well-known.$.ts  # relais
├── features/connections/Agents.tsx       # agents reliés, révocation
└── features/projects/RollbackRequest.tsx # demande d'un agent à confirmer

plugins/pono/                             # plugin Claude Code (connexion + points d'entrée)
.claude-plugin/marketplace.json
```

**Structure Decision**: même monorepo ; le serveur d'outils vit dans le service (mêmes cas
d'usage), sous `src/pono_api/mcp/` ; le courtier est de l'infrastructure (il dépend du SDK).

## Complexity Tracking

| Écart | Pourquoi | Alternative plus simple rejetée |
|---|---|---|
| Tables hors organisation (clients, demandes) | Un agent s'enregistre et demande l'accès avant que quiconque soit connu | Enregistrement manuel des clients (rejeté : FR-002, l'agent s'enregistre seul) |
