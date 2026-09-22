# AGENTS.md — Pono

**Le contexte du projet vit dans [`CLAUDE.md`](CLAUDE.md). Lis-le en premier et applique-le comme
s'il t'était adressé** — ce n'est pas un fichier réservé à Claude, c'est simplement celui que
Claude charge tout seul.

Ce fichier n'ajoute que ce que `CLAUDE.md` ne porte pas : les procédures Spec Kit.

## Les non-négociables, en clair

1. **Aucun nom de fournisseur dans le domaine.** GitHub, Neon, Netlify, Coolify, Claude vivent
   dans les adaptateurs, derrière un contrat.
2. **Le garde-fou est mécanique**, jamais une consigne donnée à un agent.
3. **Le RLS est écrit dans la migration créatrice**, jamais après coup.
4. **Aucune affirmation publique** sans ligne correspondante dans `docs/VERITE_ET_PREUVES.md`.
5. **Aucun secret** dans un fichier, un message ou un commit.
6. **Jamais de push direct sur `main`.**

## Les procédures Spec Kit

Pinné : Spec Kit `v0.16.0` (`5dce710ce099067c7d3f2ef47a37b9a1c300b327`), exécuté par `uvx` depuis
le dépôt, jamais depuis une installation globale.

| Procédure | Quand | Ce qu'elle produit |
|---|---|---|
| `speckit-constitution` | une fois, déjà fait | `.specify/memory/constitution.md` |
| `speckit-specify` | début de tranche | `specs/NNN-slug/spec.md` |
| `speckit-clarify` | si la spec a des zones floues | questions et réponses inscrites dans la spec |
| `speckit-plan` | après la spec | `plan.md` et les artefacts de conception |
| `speckit-tasks` | après le plan | `tasks.md`, ordonné par dépendances |
| `speckit-checklist` | avant d'implémenter | vérification de complétude des exigences |
| `speckit-analyze` | avant d'implémenter | cohérence entre spec, plan et tâches |
| `speckit-implement` | la boucle de code | le code, tâche par tâche |
| `speckit-converge` | quand le code a dérivé de la spec | les tâches restantes, ajoutées à `tasks.md` |

L'ordre du cycle, avec ses points de contrôle :

```text
constitution → specify → clarify → plan → tasks → analyze → implement → converge
```

Les scripts sont en PowerShell, dans `.specify/scripts/powershell/`.

## Les branches

```
main       le geste humain seul. Rien n'y entre sans validation.
dev        le terrain de l'agent.
NNN-slug   une branche par tranche, nommée par Spec Kit.
```
