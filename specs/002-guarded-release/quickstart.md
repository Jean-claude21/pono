# Quickstart — vérifier la mise en ligne sous garde-fou

## Prérequis

- Phase 1 en ligne ; service, worker et console déployés depuis `dev` (`docs/EXPLOITATION.md`).
- L'app `pono-atelier` a les permissions de dépôt **Checks : écriture** et **Administration :
  écriture**, acceptées par l'auteur sur son installation.
- Tests locaux : Postgres avec les rôles de `apps/api/tests/bootstrap_roles.sql`,
  `PONO_TEST_OWNER_URL` et `PONO_TEST_APP_URL` posées.

## Automatique

```bash
uv run pytest apps/api
pnpm --filter @pono/web test
pnpm --filter @pono/web test:e2e
```

Couvrent : les garde-fous sur des changements d'exemple (unitaires), les transitions de verdict et
l'invalidation d'une validation (intégration), le journal en ajout seul (sécurité), le contrat
fusionné des phases 1 et 2, et les écrans de verdict, de validation, de protection, de retour
arrière et de journal (Playwright, service simulé).

## Sur un projet réel (preuve de fin)

1. **Protection** : ouvrir lectio-reads dans la console → « Protéger la production ». Vérifier chez
   le fournisseur de code que `main` exige une proposition et la vérification `pono/release`.
2. **Refus** : sur une branche, ajouter `drizzle/0003_drop_notes.sql` contenant
   `ALTER TABLE notes DROP COLUMN body;`, ouvrir une proposition vers `main`. Attendre au plus
   2 minutes après la preview : verdict « refusé », garde-fou des migrations en échec sur ce fichier,
   bouton de fusion bloqué chez le fournisseur de code, entrée `release.refused` au journal.
3. **Validation** : remplacer la migration par un ajout de colonne. Verdict « en attente de
   validation », fusion toujours bloquée ; valider dans la console ; la vérification passe au vert ;
   fusionner chez le fournisseur de code ; entrées `release.approved` puis `release.merged`.
4. **Invalidation** : sur une autre proposition validée, pousser un commit : la validation tombe
   (`release.approval_invalidated`), la fusion est de nouveau bloquée.
5. **Retour arrière** : « Revenir à la version précédente » sur lectio-reads ; la production sert le
   déploiement précédent, lien qui répond, entrées `rollback.requested` puis `rollback.succeeded`.
6. **Démonstration** (SC-008) : enregistrer les étapes 1 et 2 sans accélération, publier la vidéo,
   consigner le lien dans `docs/VERITE_ET_PREUVES.md`.
