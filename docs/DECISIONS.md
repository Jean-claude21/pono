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

## D-010 — Le serveur en FastAPI, la console en TanStack Start

**Validé le 2026-09-22.** Remplace la première version de cette décision, qui
proposait tout en TypeScript sur un argument faux.

**Tranché ainsi.** Le poste de contrôle — API de la console, serveur MCP, serveur d'autorisation
OAuth, tâches de fond, orchestrateur — est un service FastAPI. La console est en TanStack Start. Un
SDK TypeScript est généré depuis l'OpenAPI du service.

**Pourquoi.**

1. **Le serveur doit tourner en continu, quel que soit le langage.** Le serveur MCP tient des flux
   longs, les tâches de fond ont besoin d'un planificateur, l'orchestrateur pilote des conteneurs.
   Aucun ne tient dans une fonction serverless. L'argument « l'hébergement gratuit exécute du
   JavaScript » ne s'appliquait donc pas au serveur.
2. **C'est l'architecture maîtrisée et prouvée** sur KYA-Platform et sur Firmo : monolithe
   modulaire domaine / application / infrastructure, mypy strict, ruff, pytest à 90 %.
3. **Le code de KYA-Platform est réutilisable**, son auteur étant celui de Pono : le courtier OAuth
   avec enregistrement dynamique de client, l'autorisation, le port de secrets, les workers,
   l'observabilité.
4. L'analyse des migrations SQL dispose en Python d'un parseur mûr (sqlglot).

**Ce que ça coûte.** Deux chaînes d'outils (pnpm et uv) — déjà pratiquées. Les types ne sont pas
partagés nativement entre web et serveur : le SDK généré depuis l'OpenAPI y répond.

---

## D-011 — Le système visuel suit la discipline de la famille Firmo

**Validé le 2026-09-22.** Remplace la première version, qui reprenait la
charte de KYA-Energy Group — une marque qui n'est pas celle de Pono.

**Tranché ainsi.** Pono hérite de la **discipline** de Firmo, pas de sa couleur :

- base achromatique : encre et toile chaude en clair, graphite et ivoire en sombre ;
- typographie Inter Tight pour le texte, JetBrains Mono pour les chiffres et les étiquettes ;
- filets horizontaux seuls, chiffres en chasse fixe alignés à droite ;
- le **bandeau de verdict** — répondre avant de détailler — qui porte le refus de mise en ligne ;
- **aucune couleur de marque** : la couleur ne dit que l'état d'un projet.

**Deux ambiances, un système.** La page publique en clair, dans la famille de Firmo. La console en
sombre, parce que c'est une salle de contrôle.

**Règle de travail qui en découle.** Toute proposition visuelle est **rendue et regardée** avant
d'être présentée. Une maquette jamais affichée n'est pas une proposition.

---

## D-012 — Pono tourne sur le serveur de son auteur

**Tranché.** La console et le serveur de Pono sont déployés sur l'instance Coolify de l'auteur.
L'hébergement serverless — Netlify aujourd'hui — n'est qu'un **adaptateur proposé aux utilisateurs**
pour leurs propres applications.

**Pourquoi.** Pono a besoin d'un serveur permanent (D-010), et l'infrastructure existe déjà.

---

## D-013 — Le code est en anglais, le produit est international

**Validé le 2026-09-22.**

**Tranché.**

1. **Tout le code est en anglais** : identifiants, variables, fonctions, classes CSS, jetons,
   commentaires, noms de fichiers, messages de commit. La documentation humaine de `docs/` reste
   en français.
2. **L'internationalisation est posée dès la phase 1**, avant le premier écran produit :
   - aucune chaîne visible écrite en dur dans un composant — tout passe par des catalogues ;
   - deux langues dès le départ : **français** par défaut, **anglais** ;
   - la langue se choisit par l'utilisateur, sinon par le navigateur ;
   - dates, nombres et montants formatés selon la langue, jamais à la main ;
   - le serveur renvoie des **codes d'erreur stables**, traduits côté interface.

**Pourquoi.** Le produit vise un public international (D-001). Rattraper l'i18n après coup veut dire
reprendre chaque écran ; la poser dès la première tranche ne coûte presque rien.

**Ce que ça implique aujourd'hui.** Les textes de la landing sont encore en français dans le code :
la phase 1 les déplace dans les catalogues.

---

## D-014 — Deux hébergeurs dès la phase 1 : Netlify et Coolify

**Validé le 2026-09-23.** Amende D-009 pour l'hébergement seulement.

**Tranché ainsi.** Le chemin de la phase 1 comprend un fournisseur de code (GitHub), **deux
hébergeurs** (Netlify et Coolify) et un fournisseur de base (Neon). Supabase reste dehors.

**Pourquoi.** Inventaire du 2026-09-22 : les projets réels de l'auteur sont répartis entre Netlify
(lectio-reads, fluxio-runtime-test, vestio…) et Coolify (firmo, nettio, pono). Avec un seul
hébergeur, la preuve de fin de la phase 1 — cinq projets réels — est inatteignable. L'adaptateur
Coolify est en lecture seule et existe déjà dans KYA-Platform.

**Ce que ça coûte.** Un adaptateur de plus à maintenir, sans quota à relever côté Coolify.

---

## D-015 — Les alertes passent par Telegram ; Pono reste en Europe

**Validé le 2026-09-23** par l'auteur (« Configure telegram », « Choisis la meilleure option »).

**Tranché ainsi.**
1. **Canal d'alerte.** Hors de l'atelier, une alerte de quota part par Telegram, que la personne
   relie elle-même depuis la console. Le courriel reste possible dès qu'un serveur d'envoi existe ;
   il n'est plus bloquant pour fermer la phase 1. Telegram vit dans un adaptateur, derrière le port
   `ChatMessenger` : aucun nom de fournisseur dans le domaine (D-002).
2. **Région.** La base de Pono reste à Francfort (`aws-eu-central-1`), à côté du serveur Coolify
   (Contabo, France). Le déplacement vers les États-Unis, demandé pour que toutes les
   fonctionnalités de Neon marchent, n'est plus nécessaire : depuis le 18 septembre 2026, Neon ouvre
   ses fonctions, son stockage objet et sa passerelle IA à Francfort comme à Virginie et à l'Ohio.

**Pourquoi.** Telegram arrive sur le téléphone sans compte d'envoi ni domaine vérifié, gratuitement.
Pour la région : la déplacer aux États-Unis ajouterait environ 90 ms à chaque requête (serveur en
France, base outre-Atlantique) sans rien débloquer.

**Ce que ça coûte.** Un adaptateur de messagerie à maintenir. Si un jour une fonctionnalité Neon
n'existe qu'aux États-Unis, la décision de région se rouvre, serveur compris.

---

## D-016 — Mise en ligne sous garde-fou : deux écritures chez les fournisseurs, aucun contournement

**Validé le 2026-09-23** par l'auteur (clarifications de `specs/002-guarded-release`).

**Tranché ainsi.**
1. Le blocage d'une mise en production est une vérification `pono/release` obligatoire sur la
   branche de production, **liée à l'app Pono** chez le fournisseur de code. Pono ne fusionne jamais.
2. Pono pose lui-même la protection de la branche de production, sur un clic de la personne. C'est
   sa seule écriture hors de ses branches de proposition ; l'app demande pour cela le droit
   d'administration du dépôt.
3. Les adaptateurs d'hébergement gagnent une seule écriture : le retour arrière de la production
   (restauration Netlify, retour arrière Coolify). Amende D-014 (« Coolify en lecture seule »).
4. Aucun garde-fou refusé ne se contourne depuis Pono. Une destruction voulue est déclarée dans le
   manifeste versionné et arrive seule dans son changement.
5. Sans preview, le garde-fou de la preview bloque.

**Pourquoi.** D-004 : un garde-fou qu'on peut contourner d'un clic finit contourné par un humain
pressé ou par un agent qui argumente. La déclaration dans le dépôt garde la décision écrite et
relue.

**Ce que ça coûte.** Deux permissions de plus pour l'app (administration, vérifications), à
accepter par chaque personne ; un projet sans preview doit l'activer avant sa prochaine mise en
production.

---

## D-017 — La phase 3 s'ouvre avant la fermeture formelle des phases 1 et 2

**Validé le 2026-09-23** par l'auteur (« Supposons que ça marche. Passons au suivant »).

**Tranché ainsi.** La phase 3 (serveur MCP et plugin) commence sans attendre les preuves encore
ouvertes : le chronométrage de la reprise (phase 1, T071), la validation, l'invalidation et le
retour arrière sur un projet réel, et la démonstration enregistrée (phase 2, T038 étapes 3 à 5,
T039). Amende la dépendance « Phases 1 et 2 fermées » de la ROADMAP pour cette phase seulement.

**Ce qui ne change pas.** Ces preuves restent des dettes visibles dans la ROADMAP et dans les
tâches. Rien n'est écrit dans `docs/VERITE_ET_PREUVES.md` tant qu'elles ne sont pas mesurées :
« supposons que ça marche » n'est pas une preuve.

**Ce que ça coûte.** Si une preuve échoue plus tard, la correction passe avant la suite de la
phase 3.

---

## D-018 — La phase 4 s'ouvre avant la fermeture formelle de la phase 3

**Validé le 2026-09-26** par l'auteur (« Si OK, passe à la phase suivante »), après la preuve en
production d'une action faite depuis l'application Claude et retrouvée au journal sous le nom de
l'agent.

**Tranché ainsi.** La phase 4 (runtime de développement) commence sans attendre les preuves encore
ouvertes de la phase 3 : la même action depuis Codex, le temps de connexion d'un nouvel agent
(SC-003), la décision de soumettre Pono au répertoire de connecteurs. Amende la dépendance
« Phase 3 fermée » de la ROADMAP pour cette phase seulement. Les dettes de D-017 restent dues.

**Ce qui ne change pas.** Ces preuves restent des dettes visibles dans la ROADMAP. La décision
bloquante de la phase 4 — quotas et plafond de dépense avant toute ouverture à un tiers — est
tranchée avant le premier conteneur, pas après.

**Ce que ça coûte.** Si une preuve de la phase 3 échoue plus tard, sa correction passe avant la
suite de la phase 4.

---

## Les trois signaux qui invalideraient le positionnement

Écrits à froid, pour ne pas être négociés à chaud.

1. **Un concurrent majeur ouvre le « ramène ton infrastructure ».** → La défense devient la
   profondeur des garde-fous et la gouvernance, plus la propriété.
2. **Anthropic ou OpenAI livrent leur propre suivi de projets.** → La défense devient la
   neutralité : plusieurs agents, plusieurs fournisseurs, un seul endroit.
3. **Personne ne paie pour « ça tient ».** → La douleur réelle était ailleurs. Retour à
   l'observation, sans insister.
