# Quickstart — prouver le runtime de développement

## Prérequis

- Service, worker et console de `dev` déployés (`docs/EXPLOITATION.md`).
- Un projet importé sur le chemin éprouvé (TanStack Start sur Vite, pnpm) dont le manifeste nomme
  une base de développement : **fluxio-runtime-test**.
- La connexion Coolify de la personne, avec un jeton qui peut créer des applications.

## Local (sans fournisseur)

```bash
uv run pytest apps/api/tests/unit/test_runtime_domain.py apps/api/tests/integration/test_runtimes.py apps/api/tests/integration/test_runtime_writes.py
node --test apps/api/tests/gate/
pnpm --filter @pono/web test:e2e
```

## En ligne — les étapes de la preuve

1. **Demander le runtime** : console → fluxio-runtime-test → Runtime → « Démarrer ». L'état passe à
   « fichiers proposés » ; fusionner la proposition sur `dev`. Attendre « prêt » (SC-007 : < 10 min).
2. **Adresse fermée** : ouvrir l'adresse dans un navigateur neuf et avec `curl` → redirection vers
   Pono, aucun contenu de l'application (SC-002). Puis « Ouvrir » depuis la console → l'application.
3. **Base de développement** : la console affiche la base branchée ; vérifier son hôte contre la
   branche de dev chez Neon (SC-003).
4. **Écrire et chronométrer** : depuis l'agent, `write_file` d'un texte visible, vingt fois ; noter
   pour chacune le temps entre la réponse de l'outil et le changement à l'écran (SC-001). Publier les
   vingt mesures telles quelles dans `docs/VERITE_ET_PREUVES.md`.
5. **Sauvegarde** : attendre une minute ; la branche `dev` porte un commit par lot, attribué à
   l'agent (SC-004). Le journal inscrit `runtime.changes_saved`.
6. **Erreurs** : écrire une erreur de syntaxe, puis `read_runtime_errors` → message, fichier, ligne
   en moins de 10 s (SC-005) ; corriger → l'erreur n'est plus en cours.
7. **Veille** : laisser 15 minutes ; l'état passe à « en veille » ; rouvrir et chronométrer jusqu'à
   l'application servie (SC-006 : < 30 s).
8. **Limites** : démarrer un quatrième runtime → refus `runtime.limit_reached`.
9. **Console sans agent** : écrire un fichier par le formulaire du projet ; même effet, même journal.
