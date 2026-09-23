# Data Model — 001-project-workshop

Identifiants : UUID v7. Horodatages : `timestamptz`, UTC. Noms de tables et de colonnes en anglais
(D-013). Toute table marquée **RLS** reçoit sa politique dans sa migration créatrice, avec
`FORCE ROW LEVEL SECURITY` (R-02).

## Identité

### `people` — Personne · RLS (sur soi)
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `code_host_user_id` | text | unique ; identité chez le fournisseur de code |
| `login` | text | doit figurer dans la liste autorisée (FR-009) |
| `email` | text | destinataire des alertes |
| `locale` | text | `fr` ou `en`, nullable (FR-003) |
| `created_at` | timestamptz | |

Politique : `id = current_setting('pono.person_id')::uuid`.

### `sessions` — Session · accès par fonction `SECURITY DEFINER` uniquement
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `person_id` | uuid → `people` | |
| `token_hash` | bytea | empreinte SHA-256 ; le jeton n'est jamais stocké |
| `expires_at` | timestamptz | |
| `revoked_at` | timestamptz | nullable |

### `organizations` — Organisation · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `name` | text | |
| `created_at` | timestamptz | |

Politique : `id = ANY (current_setting('pono.organization_ids')::uuid[])`.

### `memberships` — Membre · RLS
| Colonne | Type | Règle |
|---|---|---|
| `organization_id` | uuid → `organizations` | clé composée |
| `person_id` | uuid → `people` | clé composée |
| `role` | text | enum `owner` en phase 1 ; extensible sans refonte (FR-008) |

À la première connexion d'une personne autorisée, une organisation personnelle et son adhésion
`owner` sont créées dans la même transaction.

## Connexions

### `connections` — Connexion · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `kind` | text | `code_host`, `hosting`, `database` |
| `provider` | text | identifiant opaque d'adaptateur (`github`, `netlify`, `coolify`, `neon`) |
| `external_ref` | text | installation ou compte chez le fournisseur |
| `secret_ciphertext` | bytea | chiffré au repos (FR-011), nullable |
| `status` | text | `active`, `expired`, `revoked` (FR-013) |
| `status_checked_at` | timestamptz | |

Unicité : (`organization_id`, `provider`, `external_ref`).

## Projets

### `projects` — Projet · RLS · objet ancre
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `code_connection_id` | uuid → `connections` | |
| `repository` | text | `propriétaire/nom` chez le fournisseur de code |
| `default_branch` | text | |
| `manifest_status` | text | `present`, `proposed`, `absent` |
| `manifest_proposal_url` | text | nullable |
| `state` | text | `healthy`, `active`, `warning`, `failing`, `idle` (FR-021) |
| `state_reason` | text | code de la règle qui a fixé l'état |
| `last_activity_at` | timestamptz | dernier commit (toute branche) ou déploiement |
| `refreshed_at` | timestamptz | heure du dernier relevé (FR-023) |

Unicité : (`organization_id`, `repository`) — FR-017.

**Évaluation de l'état** (dans cet ordre, première règle vraie) :

1. `failing` — la production ne répond pas (deux essais de 10 s) ou son dernier déploiement a échoué ;
2. `warning` — un quota > 80 % ou une connexion nécessaire `expired` / `revoked` ;
3. `active` — un déploiement en cours ou `last_activity_at` < 24 h ;
4. `idle` — `last_activity_at` > 30 jours ;
5. `healthy` — sinon.

### `environments` — Environnement · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `project_id` | uuid → `projects` | |
| `kind` | text | `production`, `preview`, `development` |
| `hosting_connection_id` | uuid → `connections` | nullable |
| `external_ref` | text | site ou application chez l'hébergeur |
| `url` | text | nullable |
| `link_status` | text | `up`, `down`, `unknown`, `missing` |
| `link_checked_at` | timestamptz | |
| `opened_at` | timestamptz | pour les previews : la plus récente est montrée dans la ligne |

### `deployments` — Déploiement · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `environment_id` | uuid → `environments` | |
| `external_ref` | text | unique par environnement |
| `status` | text | `building`, `succeeded`, `failed`, `cancelled` |
| `commit_sha` | text | |
| `author` | text | |
| `started_at` / `finished_at` | timestamptz | |

## Quotas

### `quota_readings` — Relevé de quota · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `project_id` | uuid → `projects` | nullable si le quota est au niveau du compte |
| `connection_id` | uuid → `connections` | |
| `metric` | text | `hosting_credits`, `db_compute_hours`, `db_storage_bytes`, `db_transfer_bytes` |
| `used` / `limit` | numeric | `limit` nullable si non disponible |
| `limit_source` | text | `account_plan` ou `free_tier_estimate` (FR-024) |
| `period_start` / `period_end` | date | période de facturation |
| `read_at` | timestamptz | |

### `alerts` — Alerte · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `connection_id` | uuid | |
| `metric` | text | |
| `threshold` | smallint | `80` ou `95` |
| `period_start` | date | |
| `emailed_at` | timestamptz | nullable |

Unicité : (`organization_id`, `connection_id`, `metric`, `threshold`, `period_start`) — une seule
alerte par seuil et par période (FR-025).
