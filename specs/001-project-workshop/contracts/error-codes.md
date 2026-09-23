# Codes d'erreur et de verdict — 001-project-workshop

Le service ne renvoie **jamais** de phrase (FR-005). Il renvoie un code stable ; la console le
traduit par une clé de catalogue `error_<code>` dans `messages/fr.json` et `messages/en.json`, où les
points deviennent des tirets bas.

| Code | HTTP | Sens |
|---|---|---|
| `auth.not_allowed` | 403 | la personne n'est pas dans la liste autorisée (FR-009) |
| `auth.session_required` | 401 | aucune session valide |
| `auth.state_mismatch` | 403 | échec de la vérification anti-rejeu à la connexion |
| `connection.duplicate` | 409 | cette connexion existe déjà dans l'organisation |
| `connection.authorization_invalid` | 422 | l'autorisation fournie est refusée par le fournisseur |
| `connection.not_found` | 404 | inconnue **ou** appartenant à une autre organisation |
| `project.already_imported` | 409 | le dépôt est déjà un projet de l'organisation (FR-017) |
| `project.repository_unreachable` | 422 | le dépôt n'est pas accessible par la connexion |
| `project.not_found` | 404 | inconnu **ou** appartenant à une autre organisation (US5, scénario 2) |
| `locale.unsupported` | 422 | langue hors `fr` / `en` |
| `provider.unavailable` | 503 | le fournisseur ne répond pas ; l'état précédent est conservé |

**Règle de cloisonnement** : une ressource d'une autre organisation répond **404**, jamais 403, pour
ne pas confirmer son existence.

## Codes de verdict (bandeau de l'atelier)

| Code | Déclencheur |
|---|---|
| `project.production_down` | la production ne répond pas (deux essais de 10 s) |
| `project.deployment_failed` | le dernier déploiement de production a échoué |
| `project.quota_warning` | un quota dépasse 80 % |
| `project.quota_critical` | un quota dépasse 95 % |
| `connection.expired` | une connexion nécessaire a expiré ou a été révoquée |
| `project.manifest_proposed` | une proposition de manifeste attend d'être fusionnée |
