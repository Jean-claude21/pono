# Data model — 004-dev-runtime

Migration `0007_dev_runtime`. Chaque table porte `organization_id`, a la RLS **activée et forcée
dans cette migration**, la politique `<table>_member` des phases précédentes, et des clés étrangères
composites `(organization_id, …)` : aucune ligne ne peut pointer une autre organisation.

## `runtimes` — un runtime par projet

| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id` | uuid | FK composite avec `project_id` et `hosting_connection_id` |
| `project_id` | uuid | **unique** : un runtime par projet |
| `hosting_connection_id` | uuid | la connexion d'hébergement qui porte le runtime |
| `state` | text | `awaiting_files`, `preparing`, `starting`, `ready`, `sleeping`, `stopped`, `failed`, `unreachable` |
| `reason` | text null | code stable de l'échec ou de l'attente (`runtime.production_database`, …) |
| `development_branch` | text | branche suivie et seule branche où Pono écrit (D-019) |
| `proposal_url` | text null | proposition des fichiers du runtime |
| `external_ref` | text null | référence de l'application chez l'hébergeur |
| `key_ref` | text null | référence de la clé privée chez l'hébergeur |
| `deploy_key_ref` | text null | référence de la clé de déploiement en lecture seule du dépôt |
| `url` | text null | adresse du runtime |
| `token_ciphertext` | bytea null | jeton partagé avec le portier, **chiffré** (Fernet) |
| `database_host` | text null | hôte attendu de la base de développement |
| `production_database_host` | text null | hôte de la production, jamais accepté |
| `saved_head` | text null | dernier commit connu de la branche de développement |
| `awake` | boolean | Vite tourne (faux en veille) |
| `errors` | jsonb | dernier relevé des erreurs, secrets masqués |
| `conflicts` | text[] | chemins en conflit déclarés par le portier ou la sauvegarde |
| `last_activity_at`, `last_status_at`, `requested_at`, `started_at`, `stopped_at` | timestamptz | |

Transitions : `awaiting_files` → (proposition fusionnée) `preparing` → `starting` → `ready` ⇄
`sleeping` ; tout état démarré → `stopped` (geste) ; → `failed` (hébergeur, base de production,
proposition fermée) ; → `unreachable` (portier muet) → `ready` quand il répond. `stopped` →
`starting` au redémarrage. **Démarrés** (limite de 3) : `awaiting_files`, `preparing`, `starting`,
`ready`, `sleeping`, `unreachable`.

## `runtime_writes` — les écritures en attente de sauvegarde

| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé (ordre d'écriture par uuid7) |
| `organization_id`, `runtime_id` | uuid | FK composite |
| `path` | text | chemin relatif validé par le domaine |
| `content` | bytea null | contenu ; null pour une suppression, **effacé après sauvegarde** |
| `deleted` | boolean | suppression |
| `actor_kind`, `actor`, `granted_by` | text | personne ou agent (003) |
| `state` | text | `pending`, `conflict`, `saved`, `superseded` |
| `save_id` | uuid null | la sauvegarde qui l'a emportée |
| `written_at` | timestamptz | |

## `runtime_saves` — les lots sauvegardés

| Colonne | Type | Règle |
|---|---|---|
| `id` | uuid | clé |
| `organization_id`, `runtime_id` | uuid | FK composite |
| `commit_sha` | text null | null quand tout le lot était en conflit |
| `paths` | text[] | fichiers du lot |
| `conflicts` | text[] | fichiers renvoyés en conflit |
| `actor_kind`, `actor`, `granted_by` | text | l'auteur du lot |
| `saved_at` | timestamptz | |

## Journal (`project_events`, append-only)

`runtime.requested`, `runtime.files_proposed`, `runtime.ready`, `runtime.stopped`, `runtime.failed`
(détail : code), `runtime.changes_saved` (détail : commit, nombre de fichiers),
`runtime.save_conflict` (détail : chemins). L'auteur est la personne ou l'agent, comme en 003 ;
Pono pour ce que le worker constate.

## Domaine (`domain/runtimes.py`)

- `RuntimeState`, `STARTED_STATES`, `MAX_STARTED_RUNTIMES = 3`, `RUNTIME_MEMORY = "1g"`,
  `SLEEP_AFTER = 15 min`, `SAVE_AFTER_QUIET = 60 s`, `MAX_WRITE_BYTES = 1 Mio`.
- `writable_path(path) -> str` : chemin normalisé ou `ValueError` (règles de R-10).
- `RuntimeTicket` : signer et vérifier `base64url(json{r,e,n}).hmac` (R-04), même format que le
  portier.
