# Protocole du portier — 004-dev-runtime

Le portier (`.pono/runtime/gate.mjs`) écoute le port 3000 du conteneur. Tout ce qui n'est pas sous
`/__pono/` est servi par Vite, derrière le cookie `pono_runtime`.

## Variables (posées par Pono chez l'hébergeur)

| Variable | Rôle |
|---|---|
| `PONO_RUNTIME_ID` | identifiant du runtime (vérifié dans le ticket) |
| `PONO_RUNTIME_TOKEN` | secret partagé : `Bearer` du service, clé HMAC des tickets et du cookie |
| `PONO_CONSOLE_URL` | où envoyer un visiteur sans cookie |
| `PONO_PROJECT_ID` | projet, pour le lien d'ouverture |
| `PONO_REPOSITORY`, `PONO_BRANCH` | dépôt et branche suivie |
| `PONO_DEPLOY_KEY_B64` | clé de déploiement **en lecture seule**, base64 sur une ligne |
| `PONO_SLEEP_AFTER_SECONDS` | 900 |
| `DATABASE_URL` | base de **développement** |

## Pour le service (`Authorization: Bearer <PONO_RUNTIME_TOKEN>`)

| Route | Corps | Réponse |
|---|---|---|
| `GET /__pono/status` | — | `{awake, lastActivityAt, head, conflicts[], errors[], databaseHost, version}` |
| `PUT /__pono/files` | `{path, content?: base64, delete?: true}` | `204` ; `422 {code:"runtime.path_refused"}` ; `413` au-delà de 1 Mio |

## Pour le navigateur

| Route | Règle |
|---|---|
| `GET /__pono/auth?ticket=…&return=/…` | ticket valide (HMAC, < 2 min, usage unique, bon runtime) → cookie et redirection vers `return` (chemin local seulement) ; sinon `403` |
| `POST /__pono/report` | cookie exigé ; `{message, stack?, file?, line?}` ; `204` |
| `GET /__pono/reporter.js` | cookie exigé ; le script injecté dans les pages HTML |
| tout autre chemin | cookie valide → Vite (HTTP et WebSocket) ; sinon `302` vers `PONO_CONSOLE_URL/runtime/open?project=…&return=…` (WebSocket : `401`) |

## Formats

- **Ticket** : `base64url(JSON {"r": runtimeId, "e": expiration en secondes, "n": nonce})` + `.` +
  `base64url(HMAC-SHA256(token, partie1))`.
- **Cookie** : `<expiration>.<base64url(HMAC-SHA256(token, "session:" + expiration))>`, 12 h.
- **Erreur** : `{source: "compile"|"browser", message, file?, line?, stack?, count, firstAt, lastAt,
  resolved}`, secrets masqués.
