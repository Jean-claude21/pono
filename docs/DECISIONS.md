# Journal des décisions

> Une décision par entrée : ce qui a été tranché, pourquoi, ce que ça coûte, et ce qui la
> renverserait. On n'efface jamais une entrée ; on en ajoute une qui la remplace.

---

## D-001 — Public visé : celui qui construit déjà avec un agent

**Tranché.** Le bénéficiaire est celui qui produit déjà de vraies applications avec Claude, Codex
ou ChatGPT. Le non-codeur arrive plus tard, en invité puis par les canevas.

**Pourquoi.** Sa douleur est observable, récurrente et non résolue ; il paie déjà pour les
morceaux. Le public non-codeur est tenu par Replit et Lovable, avec des moyens sans commune mesure.

**Ce que ça coûte.** On renonce au volume à court terme.

**Ce qui la renverserait.** Trois mois sans qu'aucune personne extérieure de ce profil ne s'en
serve.

---

## D-002 — Architecture en adaptateurs, aucun fournisseur dans le cœur

**Tranché.** Code, base, hébergement, runtime, agent et paiement sont des adaptateurs derrière des
contrats. Le domaine ne nomme aucun fournisseur.

**Pourquoi.** La promesse « démarre à 0 € » dépend de paliers gratuits qui changent — Netlify est
passé à un modèle de crédits en 2025. La portabilité est l'assurance-vie de la promesse.

**Ce que ça coûte.** Une couche d'indirection dès le premier jour.

---

## D-003 — La vérité de l'état vit dans le dépôt

**Tranché.** Un manifeste versionné dans le dépôt de l'utilisateur décrit le projet et ses
ressources. Pono doit pouvoir reconstruire son état à partir du dépôt et des fournisseurs.

**Pourquoi.** C'est ce qui rend le non-enfermement techniquement vrai, et pas seulement promis.

**Ce que ça coûte.** Une réconciliation à écrire, et une détection de dérive.

---

## D-004 — Le garde-fou de production est mécanique

**Tranché.** La protection est appliquée par le système et par le fournisseur de code, jamais par
une consigne donnée à l'agent.

**Pourquoi.** Prouvé sur un projet réel : une règle conversationnelle ne tient pas. Conséquence
directe : la protection de branche impose un dépôt public ou une offre GitHub payante, et ce choix
doit être posé **avant** la création du dépôt de l'utilisateur.

---

## D-005 — Claude n'est jamais obligatoire

**Tranché.** Tout ce qui se fait depuis un agent doit pouvoir se faire depuis la console web.

**Pourquoi.** Nommer Claude dans l'accroche est bon pour l'acquisition ; lui livrer la survie du
produit ne l'est pas. Une décision d'Anthropic ou d'OpenAI ne doit jamais couper le produit en deux.

---

## D-006 — Le savoir-faire est servi par le serveur MCP, pas figé dans le plugin

**Tranché.** Instructions, descriptions d'outils et canevas sont renvoyés par le serveur. Le plugin
ne porte que la connexion et quelques points d'entrée.

**Pourquoi.** Les améliorations profitent à tous sans réinstallation, et la compatibilité se gère
côté serveur : version actuelle et précédente acceptées, rupture seulement en version majeure.

**Ce que ça coûte.** Discipline sur la taille du contexte renvoyé, et gouvernance de ce que le
serveur dicte.

---

## D-007 — Accès aux fournisseurs par autorisation, jamais par clé permanente

**Tranché.** Les connexions passent par les mécanismes d'autorisation des fournisseurs (application
GitHub, programmes partenaires). À défaut, la clé est chiffrée et son usage est tracé.

**Pourquoi.** Détenir des clés de pleine puissance pour des tiers est le risque numéro un du
produit.

---

## D-008 — Prix fixe, aucun crédit d'intelligence artificielle

**Tranché.** Pono ne facture jamais à l'effort de l'agent. Seul le runtime hébergé est payé à
l'usage, et il reste optionnel.

**Pourquoi.** C'est cohérent avec le mandat : nous ne vendons pas d'intelligence. Et c'est la
réponse directe aux factures imprévisibles du marché.

---

## D-009 — Un seul chemin technique en V1

**Tranché.** Un seul chemin complet et éprouvé, avant tout ajout de fournisseur ou de canevas.

**Pourquoi.** Capacité limitée. La profondeur avant la largeur.

---

## Les trois signaux qui invalideraient le positionnement

Écrits à froid, pour ne pas être négociés à chaud.

1. **Un concurrent majeur ouvre le « ramène ton infrastructure ».** → La défense devient la
   profondeur des garde-fous et la gouvernance, plus la propriété.
2. **Anthropic ou OpenAI livrent leur propre suivi de projets.** → La défense devient la
   neutralité : plusieurs agents, plusieurs fournisseurs, un seul endroit.
3. **Personne ne paie pour « ça tient ».** → La douleur réelle était ailleurs. Retour à
   l'observation, sans insister.
