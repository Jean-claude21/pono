# Outils ajoutés pour agents — 004-dev-runtime

Même règles qu'en 003 : chaque outil rend le même document JSON que la route de la console indiquée
et, en erreur, le même code stable. Les outils d'action exigent `pono:act`, sont annotés destructifs
et journalisés au nom de l'agent.

| Outil | Étendue | Annotation | Même effet que |
|---|---|---|---|
| `get_runtime(project_id)` | `pono:read` | lecture seule | `GET /projects/{id}/runtime` |
| `read_runtime_errors(project_id)` | `pono:read` | lecture seule | `GET /projects/{id}/runtime/errors` |
| `start_runtime(project_id)` | `pono:act` | destructif | `POST /projects/{id}/runtime` |
| `stop_runtime(project_id)` | `pono:act` | destructif | `DELETE /projects/{id}/runtime` |
| `write_file(project_id, path, content)` | `pono:act` | destructif | `PUT /projects/{id}/runtime/files` |
| `delete_file(project_id, path)` | `pono:act` | destructif | `DELETE /projects/{id}/runtime/files` |
| `save_changes(project_id)` | `pono:act` | destructif | `POST /projects/{id}/runtime/save` |

`content` est du texte UTF-8 (le code source) ; la console accepte aussi un fichier déposé.
Aucun outil ne lit les variables du runtime ni la clé de sa base ; ouvrir l'adresse du runtime reste
un geste du navigateur d'un membre (`/runtime/open`).
