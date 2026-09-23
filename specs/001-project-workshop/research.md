# Research — 001-project-workshop

Chaque entrée : **Decision**, **Rationale**, **Alternatives considered**. Aucune inconnue ne reste
ouverte ; ce qui dépend d'un fournisseur non vérifié est traité par une tâche d'exploration en tête
de `tasks.md`, avec un comportement de repli défini ici.

---

## R-01 — Service : reprise du socle de KYA-Platform

- **Decision** : service Python 3.14 avec FastAPI, SQLAlchemy asynchrone et asyncpg, migrations
  Alembic, configuration pydantic-settings, espace de travail `uv`, contrôles `ruff`, `mypy --strict`,
  `pytest` (couverture ≥ 90 %). Découpage `domain / application / infrastructure / api / workers`.
- **Rationale** : D-010 validée ; architecture déjà éprouvée par l'auteur sur KYA-Platform et Firmo.
  Modules repris : fabrique de sessions asynchrones et normalisation d'URL Postgres
  (`infrastructure/database/session.py`), chiffrement Fernet des données d'accès
  (`oauth_broker.py`), adaptateur GitHub App qui ouvre des pull requests sans droit de fusion
  (`infrastructure/github.py`), ports de notification (`workers/notifications.py`), exécuteur de
  tâches (`workers/runner.py`), adaptateur Coolify (`infrastructure/coolify`).
- **Alternatives considered** : tout en TypeScript (rejeté, D-010) ; réécrire ces modules
  (rejeté : ils sont prouvés et de même auteur).

## R-02 — Cloisonnement par organisation : RLS Postgres

- **Decision** :
  - chaque table portant des données d'organisation a une colonne `organization_id` et une politique
    RLS écrite **dans sa migration créatrice**, avec `FORCE ROW LEVEL SECURITY` ;
  - le service se connecte avec un rôle `pono_app` **non propriétaire** et sans `BYPASSRLS` ; les
    migrations s'exécutent avec le rôle propriétaire `pono_owner` ;
  - chaque transaction ouvre avec `SET LOCAL pono.person_id` et `SET LOCAL pono.organization_ids`,
    posés à partir de la session authentifiée ; les politiques lisent ces réglages ;
  - la résolution d'une session à partir de son jeton passe par une fonction `SECURITY DEFINER`
    minimale, seule porte d'entrée avant que la personne soit connue. **Prérequis** : son
    propriétaire (`pono_owner`) a `BYPASSRLS`, comme le rôle propriétaire de Neon ; sans lui,
    `FORCE ROW LEVEL SECURITY` filtrerait aussi la fonction. Un test de sécurité l'impose, et la
    base de test de la CI est créée ainsi ;
  - les tâches de fond travaillent organisation par organisation, en posant le même réglage.
- **Rationale** : constitution, principe VI ; FR-007 et SC-006 exigent un refus au niveau des
  données, y compris pour une requête directe.
- **Alternatives considered** : autorisation applicative seule (rejetée : ne tient pas une requête
  directe) ; OpenFGA comme dans KYA-Platform (rejeté pour la phase 1 : les rôles sont triviaux,
  le modèle garde la porte ouverte, D-009).

## R-03 — Identité et fournisseur de code : une seule GitHub App

- **Decision** : une GitHub App enregistrée par Pono sert à la fois :
  - à la **connexion de la personne** (autorisation utilisateur de l'App, OAuth) ;
  - à l'**accès aux dépôts choisis** (installation sur une sélection de dépôts).
  Permissions demandées : `metadata: read`, `contents: write`, `pull_requests: write`,
  `deployments: read`. L'accès à Pono est limité par une liste d'identifiants autorisés
  (`PONO_ALLOWED_LOGINS`).
- **Rationale** : FR-009, FR-010, FR-030 ; une seule autorisation pour la personne, jetons
  d'installation de courte durée, révocables chez le fournisseur (FR-012).
- **Écart assumé sur FR-030** : GitHub n'offre pas de permission « proposer seulement ». Proposer un
  manifeste exige `contents: write`. Garde-fou mécanique compensatoire : l'adaptateur **refuse toute
  écriture hors des branches `pono/*`** et n'appelle jamais l'API de fusion ; un test l'impose (FR-029).
- **Alternatives considered** : OAuth App classique (rejetée : jetons longs, portée `repo` totale) ;
  jeton personnel (rejeté : clé permanente, D-007).

## R-04 — Session de la console

- **Decision** : session côté serveur. Un jeton aléatoire est posé en cookie `HttpOnly`, `Secure`,
  `SameSite=Lax` sur l'origine de la console ; seule son empreinte est stockée. La console relaie
  les appels vers le service par une **route serveur `/api/*`** (même origine, service non exposé
  publiquement).
- **Rationale** : pas de jeton lisible par le navigateur, révocation immédiate, pas de CORS ni de
  cookie inter-domaines avec les domaines Coolify par défaut (D-012).
- **Alternatives considered** : JWT dans le navigateur (rejeté : révocation difficile) ; routage par
  chemin dans Coolify (écarté : dépend du proxy, moins portable que le relais).

## R-05 — Internationalisation

- **Decision** : **Paraglide JS** côté console, catalogues `messages/fr.json` et `messages/en.json`,
  stratégie `cookie → preferredLanguage → baseLocale (fr)`. Le choix explicite est aussi enregistré
  sur la personne et replacé dans le cookie à la connexion. Formats par les API `Intl` avec la langue
  active. Le service ne renvoie jamais de phrase : seulement des **codes d'erreur stables**
  (`contracts/error-codes.md`).
- **Rationale** : FR-001 à FR-005 ; Paraglide est la solution recommandée par TanStack pour Start,
  compatible SSR, compilée (seuls les messages utilisés partent au navigateur).
- **Alternatives considered** : i18next (runtime plus lourd, clés non typées) ; Lingui (bonne
  option, moins intégrée au routeur).

## R-06 — Manifeste Pono

- **Decision** : fichier `.pono/project.json`, schéma versionné (`contracts/manifest.schema.json`).
  À l'import d'un dépôt sans ce fichier, Pono le **pré-remplit** à partir, dans l'ordre :
  1. d'un manifeste existant — `project.yaml` (atelier), `.fluxio/project.json` (Fluxio),
     `stack.hcl` (Livio) ;
  2. de la détection chez les fournisseurs connectés (site ou application liés au dépôt, projet de
     base référencé) ;
  puis l'ouvre en **pull request** sur la branche `pono/manifest`.
- **Rationale** : FR-015 à FR-018, D-003 ; inventaire réel : 7 projets en `project.yaml`, 2 en
  Fluxio, 1 en Livio, 2 sans manifeste.
- **Alternatives considered** : lire indéfiniment les trois formats (rejeté par la clarification Q1).

## R-07 — Fournisseurs de la phase 1 et écart à D-009

- **Decision** : fournisseur de code **GitHub** ; hébergement **Netlify et Coolify** ; base **Neon**.
  Supabase reste hors périmètre : les projets qui l'utilisent affichent « quota non suivi ».
- **Rationale** : inventaire réel du 2026-09-22 —
  - Netlify : lectio-reads, fluxio-runtime-test, vestioo… ;
  - Coolify : firmo, nettio, lectio (dev), fluxio (dev), pono ;
  - Neon : lectio-reads, fluxio-runtime-test, livio, nyatefe, parathe.
  Avec un seul hébergeur, SC-001 (cinq projets réels) n'est pas atteignable, et Pono lui-même tourne
  sur Coolify (D-012). L'adaptateur Coolify est **en lecture seule** et existe déjà dans KYA-Platform.
- **Écart** : D-009 prévoit un seul chemin technique. L'écart est porté dans *Complexity Tracking* du
  plan et validé par **D-014**.
- **Alternatives considered** : Netlify seul (SC-001 impossible) ; Coolify seul (perd le cas des
  paliers gratuits, cœur de la promesse « 0 € »).

## R-08 — Quotas

- **Decision** : un port `QuotaReader` par fournisseur.
  - **Neon** : lecture des métriques de consommation du projet (compute, stockage, transfert) et des
    limites de l'offre du compte quand l'API les expose.
  - **Netlify** : lecture de la consommation de crédits du compte si l'API l'expose.
  - **Coolify** : pas de quota (hébergement propre).
  Quand une métrique n'est pas exposée, la valeur est affichée « non disponible » — jamais estimée
  sans le dire (principe VII). La source de chaque limite est enregistrée (FR-024).
- **Exploration faite (T055, 2026-09-23)**, sur les comptes réels de l'auteur :
  - **Netlify** : `GET /accounts/{slug}/bandwidth` renvoie la consommation et l'allocation du compte
    (`used`, `included`, période) → mesure `hosting_bandwidth_bytes`, limite **offre du compte**.
    Aucun point d'API public de consommation de crédits n'a répondu (`/usage`, `/credits`) : les
    comptes à crédits n'ont pas de quota lu tant qu'il n'existe pas.
  - **Neon** : `GET /projects/{id}` renvoie la consommation de la période (`compute_time_seconds`,
    `data_transfer_bytes`, `synthetic_storage_size`) et la limite de stockage de l'offre
    (`branch_logical_size_limit_bytes`) → stockage en **offre du compte**. L'offre elle-même se lit
    sur l'organisation (`GET /organizations/{id}` → `plan`). Les limites de calcul et de transfert
    ne sont pas exposées : pour une offre gratuite, elles valent celles publiées sur
    neon.com/pricing (100 CU-heures et 5 Go par projet et par mois, lues le 2026-09-23), affichées
    **offre gratuite, estimée** ; pour une offre payante, « limite non fournie ».
  - **Coolify** : aucun quota (serveur propre), rien n'est inventé.
  - Lister les projets Neon exige l'identifiant d'organisation (`/users/me/organizations`).

## R-09 — Relevés et tâches de fond

- **Decision** : un conteneur `pono-worker` (même image que le service) exécute le planificateur :
  relevé d'état au plus toutes les 15 minutes par projet, vérification des adresses (délai 10 s, deux
  tentatives, `HEAD` puis `GET` si refusé), relevés de quotas, émission des alertes idempotentes
  (clé unique : ressource, seuil, période). Un relevé immédiat est déclenché à la demande.
- **Rationale** : FR-020 à FR-025 ; reprise du modèle d'exécuteur de KYA-Platform.
- **Alternatives considered** : webhooks des fournisseurs (utiles plus tard pour réduire la
  latence ; pas nécessaires pour tenir 15 minutes).

## R-10 — Courriel d'alerte

- **Decision** : port `Mailer` avec un adaptateur SMTP générique, configuré par variables
  d'environnement. Sans configuration SMTP, les alertes restent visibles dans l'atelier et la sonde
  de santé signale « courriel non configuré ».
- **Rationale** : FR-025 sans lier le produit à un fournisseur de courriel.
- **Alternatives considered** : SDK d'un fournisseur de courriel (rejeté : couplage inutile).

## R-11 — Base de Pono et déploiement

- **Decision** : un projet Neon `pono` (offre gratuite), branches `main` et `dev`. Sur Coolify :
  `pono-api`, `pono-worker` et `pono-web`, sur la branche `dev` pendant la phase. Les migrations
  s'exécutent au démarrage du service avec le rôle propriétaire, avant l'ouverture du port.
- **Rationale** : D-012, principe « 0 € », continuité avec la phase 0.

## R-12 — SDK TypeScript

- **Decision** : le service publie son OpenAPI ; `openapi-typescript` génère les types et
  `openapi-fetch` sert de client dans le paquet `packages/sdk`, régénéré à chaque changement de
  contrat. Un contrôle vérifie que le SDK est à jour.
- **Rationale** : types partagés sans deuxième source de vérité (D-010).
