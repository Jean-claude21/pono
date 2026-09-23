# Codes d'erreur et de verdict — 003-mcp-server

Même règle que les phases 1 et 2 : des codes stables, traduits par la console (`error_<code>`,
`verdict_<code>`), rendus à l'identique par les outils pour agents (`mcp-tools.md`).

## Erreurs

| Code | HTTP | Sens |
|---|---|---|
| `oauth.request_not_found` | 404 | demande de consentement inconnue, déjà traitée ou expirée (10 minutes) |
| `oauth.access_invalid` | 422 | étendue d'accord non reconnue, ou plus large que celle demandée |
| `agent.grant_not_found` | 404 | accès d'agent inconnu **ou** d'une autre organisation |
| `agent.scope_insufficient` | 403 | outil d'action appelé avec un accès en lecture seule |
| `rollback.request_pending` | 409 | une demande de retour arrière attend déjà une personne sur ce projet |
| `rollback.request_not_found` | 404 | demande inconnue **ou** d'une autre organisation |
| `rollback.request_closed` | 409 | demande déjà confirmée, écartée ou expirée |

## Codes de verdict (bandeau de l'atelier)

| Code | Déclencheur |
|---|---|
| `rollback.requested` | un agent demande un retour arrière : une personne doit le confirmer ou l'écarter |
