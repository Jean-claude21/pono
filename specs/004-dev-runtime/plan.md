# Implementation Plan: Le runtime de développement

**Branch**: `004-dev-runtime` | **Date**: 2026-09-26 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/004-dev-runtime/spec.md`

## Summary

Chaque projet importé peut avoir un runtime de développement : une application de son serveur
Coolify, construite depuis sa branche de développement, dont le conteneur porte un petit **portier**
(`gate`) versionné dans le dépôt, sous `.pono/runtime/` (research R-01). Le portier sert Vite à
chaud derrière une authentification par ticket signé par Pono (R-04), reçoit les écritures de fichiers
envoyées par le service (R-05), suit la branche de développement sans jamais écraser une écriture en
attente (R-06), recueille les erreurs de compilation et du navigateur (R-07), et endort Vite après
15 minutes sans activité (R-08). Le service orchestre : il propose les fichiers du runtime, crée
l'application chez l'hébergeur avec une clé de déploiement en lecture seule (R-02), branche la base
de développement et vérifie qu'elle n'est pas celle de la production (R-03), garde les écritures en
attente et les sauvegarde par lots sur la branche de développement (R-09, D-019), applique les
limites (R-10). La console et l'agent ont les mêmes gestes (principe VIII).

## Technical Context

**Language/Version**: Python 3.14 (service, worker) ; TypeScript 5.9 (console) ; JavaScript ESM
sans dépendance, Node 22 (portier)

**Primary Dependencies**: FastAPI, SQLAlchemy async, Alembic, `cryptography` (clé ed25519),
`mcp` ; TanStack Start, Paraglide, `@pono/design`, `@pono/sdk` ; portier : modules `node:` seulement

**Storage**: Postgres (Neon `pono`) ; migration `0007_dev_runtime`

**Testing**: pytest (unitaires, adaptateurs sur transport simulé, intégration sur Postgres jetable,
contrat, sécurité) ; `node --test` pour le portier (dépôt Git temporaire, Vite simulé) ; Vitest ;
Playwright avec service simulé ; preuve réelle sur fluxio-runtime-test

**Target Platform**: service et worker sur Coolify (inchangés) ; runtimes sur le serveur Coolify de
la personne

**Project Type**: service web + worker + console web + programme embarqué dans le dépôt de la personne

**Performance Goals**: écriture → écran, médiane < 5 s (SC-001) ; réveil < 30 s (SC-006) ; erreur
lisible < 10 s (SC-005) ; sauvegarde < 2 min après la dernière écriture (SC-004)

**Constraints**: jamais la base de production (SC-003) ; aucune clé en écriture dans le conteneur
(D-019) ; écriture Git bornée à la branche de développement d'un projet qui a un runtime ; adresse
fermée aux non-membres (SC-002) ; 3 runtimes démarrés, 1 Gio, veille 15 min

**Scale/Scope**: deux personnes, quelques projets ; un runtime par projet ; un seul chemin
(TanStack Start sur Vite, pnpm, Coolify, base Neon)

## Constitution Check

| Principe | Vérification | État |
|---|---|---|
| I. Simple et fonctionnel | Le conteneur éprouvé de Fluxio ; un portier sans dépendance ; la veille éteint Vite, pas le conteneur | ✅ |
| II. Étape en cours | Rien des rôles (phase 5), aucun runtime hébergé par Pono, aucun second hébergeur | ✅ |
| III. Aucun fournisseur dans le cœur | Le domaine parle de runtime, d'hébergeur, de base ; Coolify, Neon et GitHub vivent dans les adaptateurs | ✅ |
| IV. Garde-fou mécanique | Écriture Git gardée dans l'adaptateur (branche de développement seulement) ; base de production refusée au démarrage et à chaque relevé ; limites appliquées par le service | ✅ |
| V. Vérité dans le dépôt | Fichiers du runtime proposés dans le dépôt ; chaque écriture finit en commit sur la branche de développement ; le runtime tourne sans Pono | ✅ |
| VI. Sécurité dans la base | RLS forcée dans `0007` pour `runtimes`, `runtime_writes`, `runtime_saves` ; clés composites par organisation | ✅ |
| VII. Rien sans preuve | SC-001 mesuré sur un projet réel et publié tel quel ; aucune performance affirmée avant | ✅ |
| VIII. Aucun chemin réservé à un agent | Chaque outil a sa route ; la console écrit un fichier par un formulaire minimal (clarification) | ✅ |
| Jamais de secret en dur | Jeton du runtime chiffré au repos ; clé privée de déploiement jamais gardée par Pono ; erreurs masquées | ✅ |
| D-018, D-019 | Phase ouverte avant la fermeture de la 3 ; écriture bornée et hébergement chez la personne | ✅ justifié |

Re-vérifié après la conception : aucune violation.

## Project Structure

### Documentation (this feature)

```text
specs/004-dev-runtime/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── openapi.yaml       # routes console ajoutées
│   ├── error-codes.md
│   ├── mcp-tools.md       # les outils ajoutés et leur route équivalente
│   └── runtime-gate.md    # le protocole entre le service et le portier
└── tasks.md
```

### Source Code (repository root)

```text
apps/api/
├── migrations/versions/0007_dev_runtime.py
├── src/pono_api/
│   ├── domain/runtimes.py                 # états, limites, chemins permis, lot
│   ├── application/
│   │   ├── ports.py                       # + RuntimeHost, RuntimeChannel, écritures de code bornées
│   │   ├── runtimes.py                    # demander, provisionner, arrêter, relever
│   │   ├── runtime_writes.py              # écrire, sauvegarder par lots, conflits
│   │   └── runtime_tickets.py             # ticket d'accès signé
│   ├── infrastructure/
│   │   ├── providers/coolify.py           # + application du runtime
│   │   ├── providers/github.py            # + commits sur la branche de dev, clés de déploiement, proposition multi-fichiers
│   │   ├── providers/neon.py              # + cible de développement
│   │   └── runtime/
│   │       ├── channel.py                 # client HTTP du portier
│   │       └── assets/                    # Dockerfile, gate.mjs, dev.mjs : proposés dans le dépôt
│   ├── api/runtimes.py
│   ├── mcp/server.py                      # + 7 outils
│   └── workers/runtimes.py                # relevé et sauvegarde, toutes les 15 s
└── tests/
    ├── unit/test_runtime_domain.py, test_runtime_adapters.py
    ├── integration/test_runtimes.py, test_runtime_writes.py
    ├── security/test_runtime_isolation.py
    └── gate/*.test.mjs                    # node --test
apps/web/src/
├── features/runtime/RuntimePanel.tsx, FileForm.tsx
└── routes/runtime.open.tsx                # ticket, puis l'adresse du runtime
```

**Structure Decision**: mêmes couches que les phases 1 à 3. Le portier est un fichier du service
(`assets/`) proposé tel quel dans le dépôt de la personne, testé par `node --test` dans la CI du
service.

## Complexity Tracking

| Écart | Pourquoi | Alternative plus simple rejetée parce que |
|---|---|---|
| Un programme Node embarqué dans le dépôt | L'authentification, l'écriture directe, les erreurs et la veille doivent vivre à côté de Vite | Un proxy chez Pono ne peut pas réveiller un conteneur ni écrire dans son disque ; Traefik seul n'authentifie pas une session Pono |
| Écritures gardées par Pono jusqu'à la sauvegarde | Aucune perte si le conteneur redémarre (SC-004), aucune clé en écriture dans le conteneur | Laisser le conteneur pousser exigerait une clé en écriture exposée (refusé, D-019) |
