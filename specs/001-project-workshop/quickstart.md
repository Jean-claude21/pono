# Quickstart — valider la phase 1

Scénarios de bout en bout qui prouvent la spec. Les détails vivent dans
[data-model.md](data-model.md) et [contracts/](contracts/) ; ce guide ne les répète pas.

## Prérequis

- Node 22 et pnpm 11 ; Python 3.14 et `uv`.
- Une base Postgres de développement (branche `dev` du projet Neon `pono`), et ses deux rôles
  `pono_owner` et `pono_app` (R-02).
- La GitHub App de Pono, installée sur au moins cinq dépôts réels (R-03).
- Des connexions Netlify, Coolify et Neon autorisées (R-07).
- Variables d'environnement : voir `apps/api/.env.example` ; aucune valeur dans le dépôt.

## Lancer

```bash
uv sync
uv run --package pono-api alembic upgrade head
uv run --package pono-api pono-api
uv run --package pono-api pono-worker
pnpm install
pnpm --filter @pono/web dev
```

## Scénarios

| # | Scénario | Résultat attendu | Exigences |
|---|---|---|---|
| 1 | Se connecter avec un identifiant **non autorisé** | refus, code `auth.not_allowed`, traduit | FR-009 |
| 2 | Se connecter avec un identifiant autorisé | une organisation personnelle est créée ; l'atelier est vide | FR-006, FR-008 |
| 3 | Lister les dépôts accessibles | seuls les dépôts de l'installation apparaissent | FR-014 |
| 4 | Importer **lectio-reads** (manifeste Fluxio) | pull request `pono/manifest` ouverte ; projet « manifeste proposé » ; environnements, adresses et dernier déploiement affichés | FR-015, FR-018 |
| 5 | Fusionner cette pull request sur GitHub | au relevé suivant, le projet passe en « manifeste présent » | FR-016 |
| 6 | Réimporter le même dépôt | refus `project.already_imported` | FR-017 |
| 7 | Vérifier l'adaptateur de code | aucune écriture hors des branches `pono/*`, aucune fusion (test automatisé) | FR-029 |
| 8 | Couper la production d'un projet de test | après deux essais de 10 s : état « en panne », verdict en tête d'atelier | FR-020, FR-021 |
| 9 | Pousser un commit sur une branche de travail | l'état passe « actif » au relevé suivant | FR-021 |
| 10 | Forcer un relevé de quota au-dessus de 80 % puis de 95 % | une alerte par seuil, dans l'atelier et par courriel ; aucune en double | FR-024, FR-025 |
| 11 | Basculer la langue en anglais, puis recharger | tous les textes, dates et nombres en anglais ; choix conservé | FR-001 à FR-004 |
| 12 | Depuis une seconde personne, appeler `/projects/{id}` d'un projet de la première | `404 project.not_found` ; la requête SQL directe avec le rôle `pono_app` ne retourne aucune ligne | FR-007, SC-006 |
| 13 | Révoquer la connexion de code | statut « révoquée » ; les données restent datées, jamais présentées comme à jour | FR-012, FR-013, FR-023 |

## Preuve de fin de phase

- **SC-001** : cinq projets réels importés — lectio-reads, fluxio-runtime-test, livio, firmo et
  nettio — avec un état juste et aucun champ saisi.
- **SC-002** : chronométrage de la reprise par les deux premiers utilisateurs, consigné dans
  `docs/VERITE_ET_PREUVES.md`.
- **SC-003** : durée de chaque import, consignée de la même façon.
