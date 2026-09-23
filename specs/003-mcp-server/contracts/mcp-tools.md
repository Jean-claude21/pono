# Contrat des outils pour agents — 003-mcp-server

Serveur : `https://<console>/mcp` (Streamable HTTP, sans état, réponses JSON). Autorisation :
OAuth 2.1 (`/.well-known/oauth-protected-resource/mcp` → `/.well-known/oauth-authorization-server`),
enregistrement dynamique, PKCE. Étendues : `pono:read`, `pono:act`.

Chaque outil rend **le même document JSON** que la route de la console indiquée, et, en cas
d'erreur, **le même code stable** (contrats des phases 1 et 2) dans une erreur d'outil
`{"code": "<code>"}`.

| Outil | Étendue | Annotation | Même effet que |
|---|---|---|---|
| `list_projects(state?)` | `pono:read` | lecture seule | `GET /projects` |
| `get_project(project_id)` | `pono:read` | lecture seule | `GET /projects/{id}` + `consoleUrl` |
| `list_releases(project_id)` | `pono:read` | lecture seule | `GET /projects/{id}/releases` |
| `read_journal(project_id, before?)` | `pono:read` | lecture seule | `GET /projects/{id}/journal` |
| `list_repositories()` | `pono:read` | lecture seule | `GET /repositories` |
| `import_project(repository)` | `pono:act` | destructif | `POST /projects` |
| `refresh_project(project_id)` | `pono:act` | destructif | `POST /projects/{id}/refresh` |
| `evaluate_release(project_id, release_id)` | `pono:act` | destructif | `POST …/releases/{rid}/evaluation` |
| `protect_production(project_id)` | `pono:act` | destructif | `POST /projects/{id}/protection` |
| `request_rollback(project_id)` | `pono:act` | destructif | crée une demande ; la console la confirme |

**Absents par construction** : valider une mise en ligne, exécuter un retour arrière, révoquer ou
créer une connexion de fournisseur. Les instructions du serveur le disent et renvoient vers la
console.

Codes propres aux agents :

| Code | Sens |
|---|---|
| `agent.scope_insufficient` | outil d'action avec un accès en lecture seule |
| `rollback.request_pending` | une demande de retour arrière attend déjà une personne |
| `rollback.request_not_found` | demande inconnue ou d'une autre organisation |
| `rollback.request_closed` | demande déjà confirmée, écartée ou expirée |
| `agent.grant_not_found` | accès inconnu ou d'une autre organisation |
| `oauth.request_not_found` | demande de consentement inconnue ou expirée |
| `oauth.access_invalid` | étendue d'accord non reconnue |
