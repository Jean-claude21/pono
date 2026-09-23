# Data model — 002-guarded-release

Migration unique : `0005_guarded_release`. Chaque table créée l'est avec `ENABLE` et
`FORCE ROW LEVEL SECURITY` et sa politique d'organisation **dans cette migration** (constitution VI).
Clés étrangères composées `(organization_id, …)` comme en phase 1 : aucune ligne ne peut pointer
vers une ressource d'une autre organisation.

## Colonnes ajoutées

### `projects`
| Colonne | Type | Règle |
|---|---|---|
| `protection_status` | text | `protected`, `unprotected`, `unavailable_on_plan`, `unknown` (défaut) |
| `protection_checked_at` | timestamptz | nullable ; heure du dernier relevé de la protection |

## Tables créées

### `releases` — Tentative de mise en ligne · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `project_id` | uuid | → `projects`, clé composée |
| `change_number` | integer | numéro de la proposition chez le fournisseur de code |
| `change_url` | text | adresse de la proposition |
| `title` | text | titre de la proposition |
| `author` | text | identifiant de l'auteur chez le fournisseur de code |
| `head_sha` | text | commit de tête actuel |
| `head_branch` | text | branche de la proposition |
| `head_seen_at` | timestamptz | première lecture de ce commit de tête (délai de la preview) |
| `reported_check` | text | nullable ; dernier état de la vérification publié chez le fournisseur de code |
| `verdict` | text | `evaluating`, `refused`, `awaiting_approval`, `approved` |
| `state` | text | `open`, `merged`, `closed` |
| `opened_at` | timestamptz | |
| `evaluated_at` | timestamptz | nullable |
| `closed_at` | timestamptz | nullable |

Unicité : (`project_id`, `change_number`). Une nouvelle version (`head_sha`) remet le verdict à
`evaluating` et annule la validation (FR-010).

### `release_checks` — Résultat de garde-fou · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `release_id` | uuid | → `releases`, clé composée |
| `head_sha` | text | version évaluée |
| `guard` | text | `secrets`, `migrations`, `preview` |
| `status` | text | `pending`, `passed`, `failed` |
| `reason` | text | nullable ; code stable (voir contrats) |
| `findings` | jsonb | liste de constats : fichier, ligne, opération ou motif — **jamais de valeur** |
| `checked_at` | timestamptz | |

Unicité : (`release_id`, `head_sha`, `guard`).

### `release_approvals` — Validation · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `release_id` | uuid | → `releases`, clé composée |
| `head_sha` | text | la version exacte validée |
| `person_id` | uuid | → `people` ; membre de l'organisation |
| `approved_at` | timestamptz | |

Unicité : (`release_id`, `head_sha`). Aucune modification ni suppression par `pono_app`.

### `rollbacks` — Retour arrière · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `project_id` | uuid | → `projects`, clé composée |
| `environment_id` | uuid | → `environments` (production), clé composée |
| `from_ref` | text | déploiement actuel chez l'hébergeur |
| `to_ref` | text | déploiement visé |
| `to_commit` | text | nullable ; commit visé |
| `requested_by` | uuid | → `people` |
| `status` | text | `queued`, `succeeded`, `failed` |
| `requested_at` | timestamptz | |
| `finished_at` | timestamptz | nullable |

### `project_events` — Journal de preuves · RLS · **ajout seul**
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé (uuid7 : l'ordre suit le temps) |
| `organization_id` | uuid | |
| `project_id` | uuid | → `projects`, clé composée |
| `occurred_at` | timestamptz | |
| `kind` | text | code stable (liste ci-dessous) |
| `actor_kind` | text | `person`, `agent`, `pono` |
| `actor` | text | nullable ; identifiant de la personne ou de l'auteur chez le fournisseur de code |
| `release_id` | uuid | nullable |
| `head_sha` | text | nullable |
| `detail` | jsonb | codes et identifiants seulement |

Droits : `pono_app` a `SELECT` et `INSERT` seulement. Un déclencheur `BEFORE UPDATE OR DELETE`
lève une erreur pour tout rôle (SC-007). Politique RLS : lecture et insertion dans les organisations
du contexte.

Types d'événement : `release.opened`, `release.evaluated`, `release.refused`,
`release.awaiting_approval`, `release.approved`, `release.approval_invalidated`, `release.merged`,
`release.merged_without_approval`, `release.closed`, `release.destruction_declared`,
`protection.applied`, `protection.missing`, `protection.restored`, `protection.unavailable`,
`rollback.requested`, `rollback.succeeded`, `rollback.failed`.

## Transitions du verdict

```
            nouvelle version
   ┌───────────────────────────────────────────┐
   ▼                                           │
evaluating ──un garde-fou échoue──▶ refused ────┤
   │                                           │
   └─tous réussis─▶ awaiting_approval ─validation─▶ approved
                                               (sur ce head_sha seulement)
```

La vérification `pono/release` chez le fournisseur de code n'est « réussie » qu'en `approved`.

## Manifeste versionné — section ajoutée (facultative)

```json
{
  "release": {
    "migrations": ["drizzle"],
    "exampleFiles": [".env.example"],
    "declaredDestructions": [{ "file": "drizzle/0007_drop_legacy.sql", "operation": "drop_column" }]
  }
}
```

Le modèle strict du manifeste (`domain/manifest.py`) et `manifest.schema.json` gagnent cette
section ; un manifeste sans elle reste valide.
