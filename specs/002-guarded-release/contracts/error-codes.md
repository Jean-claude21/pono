# Codes d'erreur, de garde-fou et de verdict — 002-guarded-release

Même règle qu'en phase 1 : le service ne renvoie jamais de phrase. La console traduit chaque code
par une clé de catalogue (`error_<code>`, `guard_<code>`, `verdict_<code>`, `event_<code>`), points
remplacés par des tirets bas.

## Erreurs

| Code | HTTP | Sens |
|---|---|---|
| `release.not_found` | 404 | tentative inconnue **ou** d'une autre organisation |
| `release.not_ready` | 409 | un garde-fou n'est pas réussi : rien à valider |
| `release.version_changed` | 409 | le changement a reçu une nouvelle version depuis l'affichage : relire avant de valider |
| `release.closed` | 409 | la proposition est fusionnée ou fermée |
| `protection.permission_missing` | 422 | l'app Pono n'a pas le droit d'administration sur ce dépôt : l'accorder dans ses réglages |
| `protection.unavailable_on_plan` | 422 | l'offre du fournisseur de code ne permet pas de protéger une branche de ce dépôt |
| `protection.no_production_branch` | 422 | le manifeste ne déclare pas de branche de production |
| `rollback.no_previous` | 409 | aucun déploiement de production réussi avant l'actuel |
| `rollback.in_progress` | 409 | un retour arrière est déjà en cours |
| `rollback.unsupported` | 422 | l'hébergeur de ce projet ne permet pas le retour arrière par Pono |

## Motifs de garde-fou (`reason` et `findings[].code`)

| Code | Garde-fou | Sens |
|---|---|---|
| `secrets.found` | secrets | une valeur secrète est ajoutée ; `file`, `line`, `operation` = type de motif |
| `secrets.env_file` | secrets | un fichier `.env` est ajouté |
| `secrets.unreadable` | secrets | un fichier texte trop gros pour être lu |
| `migrations.destructive` | migrations | `operation` : `drop_table`, `drop_column`, `rename`, `alter_type`, `truncate`, `delete_all` |
| `migrations.unreadable` | migrations | instruction ou fichier que Pono ne sait pas analyser |
| `migrations.history_rewritten` | migrations | une migration déjà en production est modifiée |
| `migrations.destruction_not_isolated` | migrations | destruction déclarée, mais le changement contient autre chose |
| `preview.missing` | preview | l'hébergement ne produit pas de preview : activer les previews du projet |
| `preview.building` | preview | la preview du commit de tête est en construction |
| `preview.failed` | preview | la construction de la preview a échoué |
| `preview.down` | preview | la preview ne répond pas (deux essais de 10 s) |
| `preview.timeout` | preview | aucune preview prête après 30 minutes |
| `provider.unavailable` | tous | le fournisseur ne répond pas : le garde-fou reste bloquant |

## Codes de verdict (bandeau de l'atelier)

| Code | Déclencheur |
|---|---|
| `release.refused` | une tentative ouverte est refusée |
| `release.awaiting_approval` | une tentative attend la validation de la personne |
| `project.unprotected` | la branche de production n'est pas protégée |
| `project.protection_unavailable` | l'offre du fournisseur ne permet pas de la protéger |
| `release.merged_without_approval` | la production a reçu un changement non validé |
| `rollback.failed` | le dernier retour arrière a échoué |
