# Pono — Constitution

> Dérivée du socle de l'atelier et du mandat de Pono. Elle gouverne le cycle SDD
> (specify → plan → tasks → implement) : tout agent — Claude, Codex, ChatGPT — s'y conforme.
> Les principes de livraison priment sur toute élégance technique.
>
> Source de vérité du produit : `docs/MANDAT.md`, `docs/PRINCIPES.md`, `docs/DECISIONS.md`.

## Core Principles

### I. Simple et Fonctionnel — NON NÉGOCIABLE

On livre la version la plus simple qui aide réellement quelqu'un. Rien ne passe à l'étape suivante
tant que la version actuelle n'est pas livrée, simple et fonctionnelle. La complexité ajoutée sans
utilisateur qui la réclame est refusée. *Une chose livrée vaut plus qu'un chef-d'œuvre qui
n'existe pas.*

### II. Obéir à l'étape en cours

On construit l'étape présente, pas toutes les étapes d'un coup. Une fonctionnalité non nécessaire
pour aider quelqu'un **aujourd'hui** va au backlog, jamais dans l'implémentation courante. Pas de
V3 planifiée avant la V1 livrée.

### III. Aucun fournisseur dans le cœur — NON NÉGOCIABLE

Le domaine ne nomme jamais GitHub, Neon, Netlify, Coolify, Claude ni aucun autre fournisseur. Ils
vivent derrière des contrats, dans les adaptateurs. Un fournisseur qui change ses règles ne doit
jamais casser la promesse. *(D-002)*

### IV. Le garde-fou est mécanique, jamais conversationnel

Une règle qu'un agent peut contourner en argumentant n'est pas une règle. Une protection est
appliquée par le système ou par le fournisseur, jamais demandée poliment à l'agent. *(D-004)*

### V. La vérité vit dans le dépôt de l'utilisateur

L'état d'un projet doit rester reconstructible depuis son dépôt et ses fournisseurs. Si Pono
disparaît, le projet continue de tourner et reste reprenable sans nous. *(D-003)*

### VI. La sécurité vit dans la base

La vérité de « qui peut quoi » est portée par la base, en RLS, écrit **dans la migration
créatrice** de chaque table. Les surfaces font confiance à la base, jamais l'inverse. La frontière
dure est l'organisation, et par défaut rien ne la traverse.

### VII. Rien ne s'affirme sans preuve

Toute affirmation publique se rattache à une ligne de `docs/VERITE_ET_PREUVES.md`. Aucun chiffre
non mesuré sur un projet réel, aucun témoignage inventé.

### VIII. Aucun chemin réservé à un agent

Ce qui se fait depuis Claude ou Codex doit pouvoir se faire depuis la console web. Le produit ne
dépend jamais de la politique d'un fournisseur d'intelligence artificielle. *(D-005)*

## Additional Constraints — propres à Pono

- **Un seul chemin technique en V1.** Aucun second fournisseur ni canevas métier avant que le
  premier chemin soit éprouvé de bout en bout. *(D-009)*
- **Jamais de secret en dur.** Aucune clé commitée, aucune clé exposée au client, aucun secret
  dans un message ou un journal. Accès aux fournisseurs par autorisation, pas par clé
  permanente. *(D-007)*
- **Aucun crédit d'intelligence artificielle facturé.** Le modèle est à prix fixe ; seul le
  runtime hébergé est payé à l'usage. *(D-008)*
- **`main` ne reçoit que du validé** : travail sur branche de phase, fusion après revue humaine.
- **Toute migration de production est un geste choisi**, jamais automatique. Une migration
  destructrice est nommée en clair avant d'être proposée.

## Development Workflow — Quality Gates

Avant chaque tâche d'implémentation, l'agent applique **les 5 questions** :

1. Quelle est la **SEULE** chose à livrer ? (pas 3, pas 5 — UNE)
2. Quelle est la version la plus simple qui aide réellement quelqu'un ?
3. Est-ce ajouté pour l'utilisateur, ou pour impressionner ?
4. Si on livrait dans 3 heures, qu'est-ce qu'on garderait ?
5. La personne qui attend sera-t-elle aidée par ce qui est livré aujourd'hui ?

**Règle des 3 heures** : toute tâche dépassant trois heures sans livrable visible est signalée
comme sur-complexification probable.

**Les quatre prérequis durs** : le mandat avant la fonctionnalité · le modèle de domaine avant la
première migration · le RLS dans la migration créatrice · le registre de vérité avant toute
affirmation publique.

## Governance

Cette constitution prime sur toute autre pratique. Toute complexité doit être justifiée par un
utilisateur réel, jamais par une élégance technique ni par une intuition. Les amendements sont
documentés et datés dans `docs/DECISIONS.md`.

**Version**: 1.0.0 | **Ratified**: 2026-09-22 | **Last Amended**: 2026-09-22
