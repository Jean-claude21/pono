# Data model — 003-mcp-server

Migration unique : `0006_agent_access`. RLS activée et forcée dans cette migration pour chaque table
créée (constitution VI).

## Tables sans organisation — accès par fonctions `SECURITY DEFINER` uniquement

Comme `sessions` en phase 1 : aucune politique ne donne de ligne à `pono_app` ; seules des fonctions
dédiées, possédées par un rôle qui contourne la RLS, lisent et écrivent, et ne rendent que ce qu'il
faut.

### `agent_clients` — Client d'agent enregistré
| Colonne | Type | Règle |
|---|---|---|
| `client_id` | text | clé ; généré par le serveur |
| `metadata` | jsonb | métadonnées RFC 7591 (nom, adresses de retour, étendue) sans secret |
| `secret_ciphertext` | bytea | nullable ; secret client chiffré |
| `created_at` | timestamptz | |

### `agent_requests` — Demande d'autorisation, puis code
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `request_digest` | bytea | unique ; empreinte de la poignée de consentement |
| `client_id` | text | → `agent_clients` |
| `redirect_uri` | text | |
| `redirect_uri_explicit` | boolean | |
| `code_challenge` | text | PKCE |
| `scopes` | text[] | étendue demandée |
| `state` | text | nullable |
| `resource` | text | adresse canonique du serveur d'outils |
| `code_digest` | bytea | nullable ; empreinte du code émis |
| `person_id` | uuid | nullable ; qui a consenti |
| `organization_id` | uuid | nullable ; pour quelle organisation |
| `granted_scopes` | text[] | nullable ; l'étendue accordée |
| `approved_at`, `denied_at`, `consumed_at` | timestamptz | nullable |
| `expires_at` | timestamptz | 10 min pour la demande, 5 min pour le code |

Fonctions : `pono_agent_register`, `pono_agent_client`, `pono_agent_open_request`,
`pono_agent_request` (lecture de la demande par la page de consentement), `pono_agent_decide`
(accord ou refus, par la personne connectée, pour son organisation), `pono_agent_redeem_code`.

## Tables d'organisation — RLS par organisation

### `agent_grants` — Consentement
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `person_id` | uuid | → `people` |
| `client_id` | text | → `agent_clients` |
| `client_name` | text | copié du client au moment de l'accord |
| `scopes` | text[] | `pono:read` et éventuellement `pono:act` |
| `granted_at` | timestamptz | |
| `last_used_at` | timestamptz | nullable |
| `revoked_at` | timestamptz | nullable |

### `agent_tokens` — Accès
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `grant_id` | uuid | → `agent_grants`, clé composée |
| `token_digest` | bytea | unique ; empreinte SHA-256, **jamais le jeton** |
| `kind` | text | `access` ou `refresh` |
| `expires_at` | timestamptz | 1 h (accès), 30 j (renouvellement) |
| `revoked_at` | timestamptz | nullable |

Lecture d'un jeton présenté : `pono_agent_token(digest)` (`SECURITY DEFINER`) rend la personne,
l'organisation, le client, l'étendue et l'accord, seulement si le jeton, l'accord et le client sont
valides.

### `rollback_requests` — Demande de retour arrière par un agent
| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | |
| `project_id` | uuid | → `projects`, clé composée |
| `grant_id` | uuid | → `agent_grants`, clé composée ; l'agent qui demande |
| `status` | text | `pending`, `confirmed`, `dismissed`, `expired` |
| `requested_at` | timestamptz | |
| `decided_at` | timestamptz | nullable |
| `decided_by` | uuid | nullable → `people` |
| `rollback_id` | uuid | nullable → `rollbacks` quand confirmé |

Une seule demande `pending` par projet (index unique partiel).

## Journal (`project_events`, phase 2) — types ajoutés

`project.imported`, `project.refresh_requested`, `release.evaluation_requested`,
`rollback.requested_by_agent`, `rollback.request_confirmed`, `rollback.request_dismissed`,
`rollback.request_expired`. Auteur `agent` : `actor` = nom du client, `detail.grantedBy` = login de
la personne qui a donné l'accès.
