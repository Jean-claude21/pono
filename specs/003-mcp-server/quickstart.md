# Quickstart — vérifier le serveur d'outils pour agents

## Automatique

```bash
uv run pytest apps/api
pnpm --filter @pono/web test
pnpm --filter @pono/web test:e2e
```

Couvrent : le parcours OAuth complet de bout en bout (enregistrement, autorisation, consentement,
échange, renouvellement, révocation) ; la parité outil par outil avec les routes de la console ;
l'absence d'outil de validation et d'exécution d'un retour arrière ; le refus d'un outil d'action en
lecture seule ; le cloisonnement par organisation ; aucune empreinte réversible en base ; la page
de consentement, la liste des agents et la demande de retour arrière dans la console.

## Avec de vrais clients (preuve de fin, SC-001)

1. **Claude Code** : `/plugin marketplace add Jean-claude21/pono`, puis `/plugin install pono`.
   Au premier appel, accepter dans la console (« lecture et actions »).
2. **Application Claude** : Réglages → Connecteurs → Ajouter un connecteur personnalisé →
   `https://pono-staging.13.140.178.49.sslip.io/mcp`.
3. **Codex** : `codex mcp add pono --url https://pono-staging.13.140.178.49.sslip.io/mcp` puis
   `codex mcp login pono`.
4. Pour chaque client : demander l'état des projets, le détail de lectio-reads, ses mises en ligne,
   son journal ; comparer avec la console (mêmes faits).
5. Demander une réévaluation de lectio-reads#3 depuis un agent : même verdict, journal au nom du
   client.
6. Demander à un agent de valider une mise en ligne : aucun outil ne le permet.
7. Demander un retour arrière depuis un agent : la console montre la demande ; l'écarter.
8. Couper l'accès d'un agent dans la console : son appel suivant est refusé.
9. Consigner les résultats dans `docs/VERITE_ET_PREUVES.md`.
