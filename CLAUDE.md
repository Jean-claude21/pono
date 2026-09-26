# Pono — contexte du projet

> Le **seul** endroit où vit le contexte. `AGENTS.md` y renvoie, il ne le duplique pas.
> Des pointeurs, pas du savoir.

## Ordre de lecture, avant toute action

1. `docs/MANDAT.md` — pour qui, quel bien, à quel prix moral.
2. `docs/PRINCIPES.md` — les invariants. Une décision qui les contredit est refusée.
3. `docs/POSITIONNEMENT.md` — l'angle, le message, le marché.
4. `docs/DECISIONS.md` — ce qui est déjà tranché. **Ne pas retrancher ce qui l'est.**
5. `docs/VERITE_ET_PREUVES.md` — avant d'écrire la moindre affirmation publique.
6. `.specify/memory/constitution.md` — la constitution qui gouverne le cycle.

## Le produit, en une phrase

Le poste de contrôle des projets construits par agent : l'état réel de chaque projet, des
garde-fous mécaniques avant la production, et rien qui appartienne à Pono.

## Phase en cours

**Phase 0 fermée** : design v2 validé, paquet `@pono/design`, console déployée sur Coolify.

**Phase 1 fusionnée dans `main`** (`specs/001-project-workshop`) : service FastAPI, worker et
console en ligne sur Coolify (`docs/EXPLOITATION.md`). Reste à la fermer : le chronométrage de la
reprise par les deux premiers utilisateurs (SC-002).

**Phase 2 fusionnée** (`specs/002-guarded-release`) : la mise en ligne sous garde-fou (D-016),
prouvée sur lectio-reads. Restent la validation et le retour arrière réels, et la démonstration
enregistrée.

**Phase 3 fusionnée dans `main`** (`specs/003-mcp-server`) : le serveur d'outils pour agents, son
serveur d'autorisation, le consentement, le plugin, la politique de confidentialité ; prouvée avec
Claude Code et l'application Claude. Restent Codex et le temps de connexion d'un agent (D-018).

**Phase 4 en cours** (`specs/004-dev-runtime`, branche `004-dev-runtime`, ouverte tôt : D-018,
D-019) : le runtime de développement sur le serveur de la personne, derrière un portier versionné
dans son dépôt. Implémentée et testée ; reste la preuve sur fluxio-runtime-test (T033).

**Tests locaux** : `PONO_TEST_OWNER_URL` / `PONO_TEST_APP_URL` vers un Postgres portant les deux
rôles de `apps/api/tests/bootstrap_roles.sql` ; la branche Neon `test` marche aussi, en plus lent.

## Le système visuel

`packages/design/style.css` est la **source unique**. La console l'importe, les maquettes de
`design/` aussi. Toute évolution visuelle se fait là, puis se **rend et se regarde** avant d'être
proposée (D-011).

## Les quatre prérequis durs

1. **Le mandat et les principes avant toute fonctionnalité.** Une fonctionnalité qui ne sert pas le
   mandat n'entre pas.
2. **Le modèle de domaine avant la première migration.** L'objet ancre est le **projet** ; la
   frontière dure est l'**organisation**, et par défaut rien ne la traverse.
3. **Le RLS dans la migration créatrice**, jamais dans une migration suivante.
4. **Le registre de vérité avant toute affirmation publique.** Aucun chiffre non mesuré.

## La langue du code et du produit

- **Le code est en anglais** : identifiants, variables, classes, jetons, commentaires, noms de
  fichiers, messages de commit. Seule la documentation de `docs/` est en français (D-013).
- **Aucune chaîne visible en dur** dans un composant : tout passe par les catalogues d'i18n,
  français par défaut et anglais (D-013).

## Gestes interdits à l'agent

- Écrire un nom de fournisseur (GitHub, Neon, Netlify, Coolify, Claude…) dans le domaine. Ils
  vivent dans les adaptateurs, derrière un contrat.
- Pousser directement sur `main`, ou contourner une protection de branche.
- Écrire un secret dans un fichier, un message ou un commit.
- Rendre une capacité accessible uniquement depuis un agent : la console web reste un chemin
  complet.
- Affirmer une performance non mesurée sur un projet réel.
- Ajouter un second fournisseur ou un canevas métier tant que le chemin unique n'est pas éprouvé.
- Planifier la V3 avant que la V1 ne soit livrée.

## Les branches

```
main       le geste humain seul. Rien n'y entre sans validation.
dev        le terrain de l'agent.
NNN-slug   une branche par phase, nommée par Spec Kit.
```

## Outillage

- Node 22 · pnpm 11 · TypeScript
- TanStack Start · Vite · Tailwind 4
- Spec Kit : `v0.16.0` (`5dce710ce099067c7d3f2ef47a37b9a1c300b327`), exécuté par `uvx`, jamais
  depuis une installation globale.

## Les cinq questions, avant chaque tranche

1. Quelle est la **seule** chose à livrer ?
2. Quelle est la version la plus simple qui aide réellement quelqu'un ?
3. Est-ce pour l'utilisateur, ou pour nous ?
4. Si on livrait dans trois heures, que garderait-on ?
5. La personne qui attend sera-t-elle aidée par ce qu'on livre aujourd'hui ?
