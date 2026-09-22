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

**Base posée.** Prochaine tranche : l'atelier qui tient les projets existants — importer un projet,
afficher son état réel, ses environnements et ses déploiements.

**Le livrable unique de la tranche :** voir l'état réel de ses propres projets au même endroit.

## Les quatre prérequis durs

1. **Le mandat et les principes avant toute fonctionnalité.** Une fonctionnalité qui ne sert pas le
   mandat n'entre pas.
2. **Le modèle de domaine avant la première migration.** L'objet ancre est le **projet** ; la
   frontière dure est l'**organisation**, et par défaut rien ne la traverse.
3. **Le RLS dans la migration créatrice**, jamais dans une migration suivante.
4. **Le registre de vérité avant toute affirmation publique.** Aucun chiffre non mesuré.

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
