# Codes d'erreur et de verdict — 004-dev-runtime

Même règle que les phases précédentes : des codes stables, traduits par la console (`error_<code>`,
`verdict_<code>`), rendus à l'identique par les outils pour agents.

## Erreurs

| Code | HTTP | Sens |
|---|---|---|
| `runtime.not_found` | 404 | le projet n'a pas de runtime |
| `runtime.stack_unsupported` | 422 | la pile du projet n'est pas celle du chemin éprouvé (serveur de développement à chaud, pnpm) |
| `runtime.development_branch_missing` | 422 | le manifeste ne nomme pas de branche de développement distincte de la production |
| `runtime.database_missing` | 422 | le manifeste ne nomme pas de base de développement |
| `runtime.production_database` | 422 | la base de développement est celle de la production : refusé |
| `runtime.hosting_missing` | 422 | aucune connexion d'hébergement capable de porter un runtime |
| `runtime.server_ambiguous` | 422 | plusieurs serveurs possibles chez l'hébergeur, aucun désigné par le projet |
| `runtime.limit_reached` | 409 | 3 runtimes déjà démarrés dans l'organisation |
| `runtime.already_started` | 409 | le runtime est déjà démarré |
| `runtime.not_ready` | 409 | le runtime n'est pas prêt à recevoir une écriture ou une ouverture |
| `runtime.unreachable` | 503 | le runtime ne répond pas ; rien n'est écrit |
| `runtime.path_refused` | 422 | chemin hors du projet ou protégé |
| `runtime.file_too_large` | 422 | fichier au-delà de 1 Mio |
| `runtime.files_refused` | 409 | la proposition des fichiers du runtime a été fermée sans fusion |
| `service.runtime_unconfigured` | 503 | le service n’a pas sa clé de chiffrement : aucun runtime ne peut être créé |
| `runtime.stopped_by_host` | 409 | l'hébergeur a arrêté le runtime (mémoire dépassée, échec au lancement) |

## Codes de verdict (bandeau de l'atelier)

| Code | Déclencheur |
|---|---|
| `runtime.save_conflict` | des écritures n'ont pas pu être sauvegardées : la branche a changé les mêmes fichiers |
| `runtime.failed` | le runtime est en échec (la raison est sur le projet) |
