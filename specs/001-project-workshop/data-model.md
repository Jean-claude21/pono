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
| `chat_id` | text | nullable ; conversation de messagerie reliée par la personne (D-015) |
| `chat_link_digest` | bytea | nullable ; empreinte SHA-256 du code de liaison en cours |
| `chat_link_expires_at` | timestamptz | nullable ; fin de validité du code (15 minutes) |
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
| `endpoint` | text | adresse d'un fournisseur auto-hébergé (Coolify), nullable |
| `secret_ciphertext` | bytea | chiffré au repos (FR-011), nullable |
| `status` | text | `active`, `expired`, `revoked` (FR-013) |
| `status_checked_at` | timestamptz | |

Unicité : (`organization_id`, `provider`, `external_ref`). Une connexion révoquée peut être
réautorisée : même ligne, nouvelle clé. La connexion au fournisseur de code ne porte aucune clé :
Pono lie l'installation de son app sur le compte de la personne et en tire des jetons courts.

**Clés composées** : toute référence entre lignes d'organisation inclut `organization_id`
(`(organization_id, id)` est unique sur chaque table référencée). Une vérification de clé étrangère
ignore la RLS ; c'est ce qui empêche une ligne de pointer vers celle d'une autre organisation.

### `connection_events` — Trace d'usage · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `connection_id` | uuid → `connections` | |
| `action` | text | opération effectuée chez le fournisseur (lecture de déploiements, relevé de quota…) |
| `occurred_at` | timestamptz | |

Écrite à chaque utilisation d'une clé permanente (FR-011, D-007) ; jamais la clé elle-même.

## Projets

### `projects` — Projet · RLS · objet ancre
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `code_connection_id` | uuid → `connections` | |
| `repository` | text | `propriétaire/nom` chez le fournisseur de code |
| `name` | text | nom du manifeste |
| `default_branch` | text | |
| `manifest` | jsonb | dernier manifeste lu (ou pré-rempli), rejoué à chaque relevé |
| `manifest_status` | text | `present`, `proposed`, `absent` |
| `manifest_proposal_url` | text | nullable |
| `database_status` | text | `found`, `missing`, `unknown` : la base nommée existe-t-elle ; nullable |
| `state` | text | `healthy`, `active`, `warning`, `failing`, `idle` (FR-021) |
| `state_reason` | text | code de la règle qui a fixé l'état |
| `last_activity_at` | timestamptz | dernier commit (toute branche) ou déploiement |
| `refreshed_at` | timestamptz | heure du dernier relevé **complet** (FR-023) |
| `stale` | boolean | le dernier relevé a échoué chez un fournisseur : l'état affiché date de `refreshed_at` |

Unicité : (`organization_id`, `lower(repository)`) — FR-017.

**Correspondance des états** — spec (français) ↔ code (anglais) :

| Spec | Code |
|---|---|
| en bonne santé | `healthy` |
| actif | `active` |
| attention | `warning` |
| en panne | `failing` |
| en veille | `idle` |

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
| `branch` | text | nullable |
| `hosting_provider` | text | identifiant d'adaptateur, nullable |
| `hosting_connection_id` | uuid → `connections` | nullable |
| `external_ref` | text | site ou application chez l'hébergeur |
| `url` | text | nullable |
| `resource_status` | text | `found`, `missing`, `unknown` : jamais inventée |
| `link_status` | text | `up`, `down`, `unknown`, `missing` |
| `link_checked_at` | timestamptz | |
| `opened_at` | timestamptz | pour les previews : la plus récente est montrée dans la ligne |

Unicité : (`project_id`, `kind`, `external_ref`). Une preview dont la demande de modification est
fermée ou fusionnée quitte le projet au relevé suivant.

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
| `metric` | text | `hosting_bandwidth_bytes`, `db_compute_seconds`, `db_storage_bytes`, `db_transfer_bytes` |
| `used` / `limit` | numeric | `limit` nullable si non disponible |
| `limit_source` | text | `account_plan` ou `free_tier_estimate` (FR-024) |
| `period_start` / `period_end` | date | période de facturation |
| `read_at` | timestamptz | |

Unicité : (`connection_id`, `project_id`, `metric`, `period_start`) — le dernier relevé de la
période remplace le précédent.

### `alerts` — Alerte · RLS
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `project_id` | uuid | nullable pour un quota de compte |
| `connection_id` | uuid | |
| `metric` | text | |
| `threshold` | smallint | `80` ou `95` |
| `ratio` | numeric | consommation / limite au moment de l'alerte |
| `period_start` | date | |
| `raised_at` | timestamptz | |
| `emailed_at` | timestamptz | nullable : reste vide si le courriel n'a pas pu partir |
| `chat_sent_at` | timestamptz | nullable : reste vide si la messagerie n'a pas pu partir |

Unicité : (`organization_id`, `connection_id`, `project_id`, `metric`, `threshold`, `period_start`)
— une seule alerte par seuil et par période (FR-025), garantie par la base.

Destinataires : `pono_alert_recipients(organization_id)` (`SECURITY DEFINER`) renvoie le courriel,
la conversation de messagerie et la langue des membres (migration `0004_chat_alerts`), **uniquement** pour l'organisation dont le contexte RLS est posé.

## Accès du planificateur

`pono_worker_organizations()` (`SECURITY DEFINER`) renvoie les identifiants des organisations, et
rien d'autre. Le planificateur travaille ensuite dans chacune sous sa propre RLS, comme une requête.
