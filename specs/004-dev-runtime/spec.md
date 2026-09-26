# Feature Specification: Le runtime de développement

**Feature Branch**: `004-dev-runtime`

**Created**: 2026-09-26

**Status**: Draft

**Input**: User description: "Phase 4 de la roadmap de Pono (docs/ROADMAP.md) : « Le runtime de développement ». Ouverte par D-018. Livrable unique : écrire depuis son agent et voir l'écran de son application changer en quelques secondes, sans poste local. Base éprouvée : Fluxio (projects_labs/Fluxio, skills/fluxio-mcp/references/runtime-dev.md) — conteneur de développement persistant sur Coolify, Vite déjà lancé, synchronisation par git pull toutes les 5 s, HMR sans reconstruire l'image ; mesures réelles : Vite prêt en ~1,3 s, fichier écrit → HMR appliqué ~4-5 s en synchronisation directe, cycle commit → push → pull → HMR ~25 s dominé par le trajet GitHub, reconstruction complète ~2 min évitée. Périmètre : (1) un runtime de développement par projet importé, issu du conteneur Fluxio, sur le serveur Coolify de la personne (un seul chemin, D-009) ; (2) écriture directe des fichiers par le serveur de Pono depuis l'agent (outils MCP d'écriture, même droits que la console, D-005), avec sauvegarde Git par lots sur la branche de développement, jamais sur la branche de production ; (3) URL de dev protégée par authentification (elle est sondée par des robots en quelques minutes), veille après inactivité et réveil à la première requête ; (4) remontée des erreurs de compilation et du navigateur vers l'agent et dans la console ; (5) le runtime ne pointe jamais la base de production — seulement la branche de développement de la base ; (6) quotas et plafond de dépense arrêtés avant toute ouverture à un tiers (point bloquant de la roadmap, D-008 : seul le runtime hébergé est payé à l'usage). Preuve de fin : temps entre l'écriture et l'écran mesuré sur un projet réel et publié tel quel ; le runtime ne pointe jamais la base de production. Premiers utilisateurs : l'auteur et une personne proche. Tout le code en anglais (D-013), aucun nom de fournisseur dans le domaine (D-002), RLS dans la migration créatrice. Hors périmètre : rôles et invités (phase 5), second hébergeur de runtime, éditeur de code dans la console, canevas métier."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Démarrer le runtime de développement d'un projet (Priority: P1)

Sur un projet importé, la personne demande son runtime de développement, depuis la console ou depuis
son agent. Pono prépare le projet (les fichiers du runtime sont proposés dans le dépôt, sur la
branche de développement, comme le manifeste l'a été), crée le runtime sur le serveur de la
personne, le relie à la base de développement, et donne l'adresse du runtime. La personne l'ouvre et
voit son application tourner, avec ses vraies données de développement.

**Why this priority**: sans runtime, rien d'autre n'existe. C'est aussi le moment où se décident les
deux protections de la phase : la base de production n'est jamais branchée, et l'adresse n'est pas
ouverte au monde.

**Independent Test**: sur un projet réel importé qui n'a pas de runtime, le demander depuis la
console, attendre qu'il soit prêt, ouvrir l'adresse après s'être connecté, et voir l'application
servie ; vérifier que la base branchée est celle de développement.

**Acceptance Scenarios**:

1. **Given** un projet importé sans runtime et un serveur d'hébergement relié, **When** la personne
   demande le runtime, **Then** Pono propose les fichiers nécessaires sur la branche de
   développement, crée le runtime, et affiche son état jusqu'à « prêt », sans aucune saisie de
   paramètre technique.
2. **Given** un runtime prêt, **When** la personne ouvre son adresse, **Then** elle voit
   l'application servie par le serveur de développement, branché sur la base de développement.
3. **Given** un projet dont la seule base connue est celle de production, **When** la personne
   demande le runtime, **Then** Pono refuse de le démarrer et dit pourquoi, sans rien créer.
4. **Given** un projet dont la pile n'est pas celle du chemin éprouvé, **When** la personne demande
   le runtime, **Then** Pono le dit clairement et ne crée rien.
5. **Given** un runtime existant, **When** la personne l'arrête depuis la console ou depuis l'agent,
   **Then** il s'arrête, et le travail non encore sauvegardé est d'abord sauvegardé.

---

### User Story 2 - Écrire depuis l'agent et voir l'écran changer en quelques secondes (Priority: P1)

Dans sa conversation, la personne demande une modification. L'agent écrit les fichiers par Pono ;
le runtime les applique à chaud ; l'écran de l'application ouvert dans le navigateur change en
quelques secondes, sans reconstruction. Les modifications sont sauvegardées dans le dépôt, par lots,
sur la branche de développement.

**Why this priority**: c'est le livrable unique de la phase, et la raison de remplacer un
environnement de développement local ou hébergé ailleurs.

**Independent Test**: sur un projet réel avec son runtime prêt et son adresse ouverte, faire écrire
par l'agent une modification visible, chronométrer entre la fin de l'écriture et le changement à
l'écran, répéter vingt fois ; vérifier ensuite que chaque modification est dans le dépôt, sur la
branche de développement.

**Acceptance Scenarios**:

1. **Given** un runtime prêt et un agent en « Lecture et actions », **When** l'agent écrit un
   fichier, **Then** l'écran ouvert reflète la modification en quelques secondes, sans recharger la
   page ni reconstruire le runtime.
2. **Given** plusieurs écritures rapprochées, **When** l'agent cesse d'écrire, **Then** elles sont
   sauvegardées ensemble dans le dépôt, sur la branche de développement, en un seul lot daté et
   attribué à l'agent et à la personne qui a donné l'accès.
3. **Given** une écriture visant la branche de production, un fichier hors du dépôt, ou un chemin
   interdit (fichiers de secrets, dossier de l'historique du dépôt), **When** l'agent la tente,
   **Then** elle est refusée avec un code stable, et rien n'est écrit.
4. **Given** un agent en lecture seule, **When** il tente d'écrire, **Then** il est refusé comme pour
   toute autre action.
5. **Given** une modification poussée dans la branche de développement par un autre moyen (poste
   local, autre outil), **When** elle arrive, **Then** le runtime la suit, comme dans Fluxio.
6. **Given** la console, **When** la personne veut faire la même écriture sans agent, **Then** elle
   le peut [NEEDS CLARIFICATION: par quel chemin la console offre-t-elle l'écriture de fichiers, alors que l'éditeur de code dans la console est hors périmètre et que le principe VIII interdit une capacité réservée à l'agent ?]

---

### User Story 3 - Une adresse de développement fermée au monde (Priority: P1)

L'adresse du runtime n'est servie qu'aux personnes de l'organisation, connectées. Un robot qui la
sonde, ou quelqu'un à qui l'adresse a été transmise, ne voit rien de l'application.

**Why this priority**: l'adresse de Fluxio a été sondée par des robots en quelques minutes. Un
runtime ouvert expose le code en cours et les données de développement.

**Independent Test**: ouvrir l'adresse sans être connecté (navigateur neuf, outil en ligne de
commande) et vérifier qu'aucune page de l'application n'est servie ; se connecter comme membre et
vérifier qu'elle l'est ; se connecter comme personne d'une autre organisation et vérifier qu'elle
ne l'est pas.

**Acceptance Scenarios**:

1. **Given** un visiteur non connecté, **When** il ouvre l'adresse ou n'importe quel chemin dessous,
   **Then** il est envoyé vers la connexion de Pono et ne reçoit aucun contenu de l'application.
2. **Given** une personne connectée d'une autre organisation, **When** elle ouvre l'adresse, **Then**
   elle reçoit le même refus qu'un projet inconnu.
3. **Given** un membre connecté, **When** il ouvre l'adresse, **Then** l'application est servie, mise
   à jour à chaud comprise.

---

### User Story 4 - Veille après inactivité, réveil à la première requête (Priority: P2)

Un runtime inutilisé se met en veille : il ne consomme plus les ressources du serveur. Quand la
personne rouvre l'adresse, ou que son agent écrit, il se réveille seul ; une page d'attente dit ce
qui se passe.

**Why this priority**: le runtime tourne sur le serveur de la personne ; sans veille, chaque projet
repris un jour occupe la machine pour toujours. Il vient après les parcours principaux, qui
marchent sans lui.

**Independent Test**: laisser un runtime sans activité au-delà du délai de veille, vérifier qu'il ne
tourne plus ; rouvrir l'adresse et chronométrer jusqu'à l'application servie.

**Acceptance Scenarios**:

1. **Given** un runtime sans requête ni écriture pendant le délai de veille, **When** le délai
   passe, **Then** son travail est sauvegardé puis il est mis en veille, et la console l'affiche.
2. **Given** un runtime en veille, **When** un membre ouvre son adresse, **Then** une page d'attente
   s'affiche, puis l'application dès qu'elle est prête.
3. **Given** un runtime en veille, **When** l'agent écrit, **Then** le runtime se réveille et
   l'écriture est appliquée, sans perte.

---

### User Story 5 - Les erreurs remontent à l'agent et à la console (Priority: P2)

Une erreur de compilation ou une erreur dans le navigateur de la personne remonte telle quelle :
l'agent peut la lire pour corriger, la console l'affiche sur le projet. Plus besoin de recopier une
erreur depuis l'écran.

**Why this priority**: sans poste local, l'agent ne voit ni le terminal ni la console du navigateur ;
il écrit à l'aveugle. C'est ce qui rend la boucle réellement courte.

**Independent Test**: faire écrire une erreur de syntaxe, puis une erreur qui ne se produit que dans
le navigateur ; vérifier que chacune est lisible par l'agent et visible dans la console en quelques
secondes, avec le fichier et la ligne quand ils existent, puis qu'elle disparaît une fois corrigée.

**Acceptance Scenarios**:

1. **Given** une écriture qui casse la compilation, **When** l'agent lit les erreurs du runtime,
   **Then** il reçoit le message, le fichier et la ligne.
2. **Given** une erreur levée dans le navigateur d'un membre, **When** l'agent lit les erreurs,
   **Then** il la reçoit, avec son message et sa pile quand elle existe.
3. **Given** une erreur corrigée, **When** la compilation repasse, **Then** l'erreur n'est plus
   présentée comme en cours.
4. **Given** une erreur contenant ce qui ressemble à un secret, **When** elle est gardée ou montrée,
   **Then** la valeur est masquée.

---

### User Story 6 - Des limites claires, arrêtées avant d'ouvrir à un tiers (Priority: P3)

La personne sait ce que ses runtimes coûtent à son serveur : combien peuvent tourner en même temps,
avec quelles ressources, et après combien de temps ils se mettent en veille. Les limites sont
appliquées par Pono, pas conseillées.

**Why this priority**: point bloquant de la roadmap avant toute ouverture à un tiers ; les deux
premiers utilisateurs peuvent s'en passer quelques jours, pas un tiers.

**Independent Test**: dépasser volontairement chaque limite et vérifier que Pono refuse ou met en
veille, avec un message clair.

**Acceptance Scenarios**:

1. **Given** le nombre maximal de runtimes éveillés atteint, **When** la personne en réveille un de
   plus, **Then** Pono le dit et propose de mettre en veille le moins récemment utilisé.
2. **Given** les limites en vigueur, **When** la personne ouvre la console, **Then** elle les voit
   avec leur consommation. [NEEDS CLARIFICATION: quelles limites arrête-t-on pour cette phase (runtimes éveillés en même temps, mémoire par runtime, délai de veille), et un runtime hébergé par Pono — donc payé à l'usage — entre-t-il déjà dans cette phase ?]

---

### Edge Cases

- **Écritures pendant une sauvegarde** : une écriture arrivée pendant la sauvegarde d'un lot part
  dans le lot suivant ; aucune n'est perdue ni sauvegardée deux fois.
- **La branche de développement a bougé ailleurs** (poste local, autre outil) pendant que l'agent
  écrivait : la sauvegarde ne réécrit jamais l'historique. Si les mêmes fichiers ont changé des deux
  côtés, Pono s'arrête, garde les deux versions visibles et le dit à l'agent et à la console.
- **Dépendances modifiées** (fichier de verrouillage changé) : le runtime les réinstalle avant de
  servir, et l'état l'affiche.
- **Écriture très volumineuse ou fichier binaire** : refusée au-delà d'une taille fixée, avec un code
  stable.
- **Le serveur d'hébergement ne répond plus** : l'état du runtime passe à « injoignable », les
  écritures sont refusées avec un code stable, rien n'est considéré comme sauvegardé.
- **Le runtime ne démarre pas** (dépendance cassée, erreur au lancement) : l'état passe à « en
  échec », avec la dernière erreur lisible par l'agent et la console.
- **La connexion d'hébergement est coupée** : les runtimes de ce serveur sont marqués injoignables ;
  aucun secret n'y reste utilisable par Pono.
- **Projet retiré de Pono** : son runtime est arrêté et supprimé du serveur après sauvegarde.
- **Fichiers de secrets du projet** : jamais écrits ni lus par les outils d'écriture ; les variables
  du runtime ne sont jamais rendues à l'agent.

## Requirements *(mandatory)*

### Functional Requirements

**Le runtime**

- **FR-001**: Le système MUST permettre de demander, arrêter et consulter le runtime de
  développement d'un projet importé, depuis la console et depuis l'agent, avec le même résultat.
- **FR-002**: Le runtime MUST tourner sur le serveur d'hébergement que la personne a relié à Pono, un
  seul chemin (D-009) ; Pono ne l'héberge pas lui-même dans cette phase, sauf décision contraire à
  la clarification de l'US6.
- **FR-003**: Les fichiers nécessaires au runtime MUST arriver dans le dépôt de la personne par une
  proposition sur la branche de développement, jamais sur la branche de production ; le projet
  reste reprenable sans Pono (principe V).
- **FR-004**: Le système MUST refuser de démarrer un runtime branché sur la base de production, et
  vérifier à chaque démarrage que la base branchée est une base de développement distincte de celle
  de la production ; la console et l'agent MUST voir quelle base est branchée.
- **FR-005**: Le système MUST suivre l'état de chaque runtime — en préparation, prêt, en veille,
  arrêté, en échec, injoignable — et la date de sa dernière activité.
- **FR-006**: Le runtime MUST suivre aussi les modifications arrivées dans la branche de
  développement par d'autres moyens, comme le fait le conteneur de Fluxio.

**Écrire**

- **FR-007**: Le système MUST offrir à l'agent d'écrire et de supprimer des fichiers du projet dans
  son runtime ; ces outils sont des actions (accès « Lecture et actions »), annotés destructifs, et
  inscrits au journal par lot, avec l'agent et la personne qui a donné l'accès.
- **FR-008**: Une écriture MUST être appliquée par le runtime sans reconstruction ; l'écran ouvert
  reflète la modification à chaud.
- **FR-009**: Les écritures MUST être sauvegardées dans le dépôt, par lots, sur la branche de
  développement uniquement : après un court silence d'écriture, avant toute mise en veille ou arrêt,
  et sur demande. [NEEDS CLARIFICATION: qui écrit dans le dépôt — l'app Pono, qui gagnerait le droit d'écrire le contenu du dépôt (amendement de D-016), ou le runtime lui-même, avec une clé propre au dépôt ?]
- **FR-010**: Le système MUST refuser, avec un code stable, toute écriture visant la branche de
  production, un chemin hors du projet, l'historique du dépôt, un fichier de secrets, ou dépassant
  la taille fixée.
- **FR-011**: La sauvegarde MUST ne jamais réécrire l'historique de la branche ; un conflit avec une
  modification arrivée d'ailleurs est signalé, jamais écrasé.
- **FR-012**: La console MUST offrir un chemin complet équivalent à l'écriture depuis l'agent
  (principe VIII), dans la forme tranchée par la clarification de l'US2.

**Accès à l'adresse**

- **FR-013**: L'adresse du runtime MUST n'être servie qu'aux membres connectés de l'organisation du
  projet ; toute autre requête reçoit la connexion de Pono ou un refus, sans contenu de
  l'application.
- **FR-014**: La mise à jour à chaud MUST fonctionner derrière cette protection.

**Veille et réveil**

- **FR-015**: Un runtime sans requête ni écriture pendant le délai de veille MUST être sauvegardé puis
  mis en veille ; il MUST se réveiller à la première requête d'un membre ou à la première écriture,
  avec une page d'attente pour le navigateur.

**Erreurs**

- **FR-016**: Le système MUST recueillir les erreurs de compilation du runtime et les erreurs du
  navigateur des membres qui l'ouvrent, avec message, fichier, ligne et pile quand ils existent, et
  les rendre lisibles par l'agent et visibles dans la console ; une erreur corrigée cesse d'être
  présentée comme en cours.
- **FR-017**: Toute valeur ressemblant à un secret MUST être masquée dans les erreurs gardées ou
  montrées (mêmes formes que le garde-fou des secrets de la phase 2).

**Limites**

- **FR-018**: Le système MUST appliquer les limites arrêtées à la clarification de l'US6 et les
  montrer à la personne avec leur consommation.

**Transverses**

- **FR-019**: Les données des runtimes, lots, erreurs et accès MUST être cloisonnées par organisation
  (RLS dans la migration créatrice) ; aucun nom de fournisseur dans le domaine (D-002) ; tout texte
  visible passe par les catalogues, français et anglais (D-013).
- **FR-020**: Aucun secret du runtime (clés, adresse de base) MUST NOT être rendu à l'agent ni à la
  console, ni écrit dans un journal ; les clés gardées par Pono sont chiffrées et chaque usage tracé
  (D-007).

### Key Entities *(include if feature involves data)*

- **Runtime** : le serveur de développement d'un projet sur le serveur d'hébergement de la personne.
  Attributs : projet, état, adresse, base branchée (développement, jamais production), dernière
  activité, limites appliquées. Un seul runtime par projet.
- **Lot de modifications** : un ensemble d'écritures sauvegardé ensemble dans le dépôt. Attributs :
  fichiers touchés, auteur (personne ou agent, et la personne qui a donné l'accès), version
  produite dans la branche de développement, état (en attente, sauvegardé, en conflit).
- **Erreur du runtime** : une erreur de compilation ou du navigateur. Attributs : origine, message
  (secrets masqués), fichier, ligne, pile, première et dernière occurrence, nombre, en cours ou
  résolue.
- **Limites** : ce qu'une organisation peut faire tourner sur son serveur (runtimes éveillés,
  ressources par runtime, délai de veille).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sur un projet réel, le temps entre la fin d'une écriture de l'agent et le changement à
  l'écran est mesuré sur au moins vingt écritures et publié tel quel ; objectif : médiane sous
  5 secondes, 95 % sous 10 secondes (Fluxio : 4 à 5 s en écriture directe).
- **SC-002**: Aucune requête d'un visiteur non connecté ou d'une autre organisation ne reçoit de
  contenu de l'application, vérifié par test et sur les journaux d'accès d'un runtime réel exposé
  24 heures.
- **SC-003**: Aucun runtime ne démarre branché sur la base de production : 100 % de refus dans les
  tests, et vérifié sur le projet réel de la preuve.
- **SC-004**: Aucune écriture confirmée à l'agent n'est perdue : chacune est dans la branche de
  développement au plus tard 2 minutes après la dernière écriture, et toujours avant une veille ou
  un arrêt.
- **SC-005**: Une erreur de compilation ou du navigateur est lisible par l'agent moins de 10 secondes
  après être survenue.
- **SC-006**: Un runtime en veille sert de nouveau l'application en moins de 30 secondes après la
  première requête d'un membre, mesuré sur le projet réel.
- **SC-007**: Le premier runtime d'un projet importé est prêt sans aucune étape manuelle autre que
  l'acceptation de la proposition de fichiers, en moins de 10 minutes.

## Assumptions

- **Le chemin éprouvé** est celui de Fluxio : projet à serveur de développement à chaud (pile
  TanStack Start sur Vite, gestionnaire pnpm), serveur d'hébergement Coolify relié à Pono. Les
  autres piles sont refusées avec un message clair (D-009).
- **La base de développement** existe déjà, comme dans les projets de Fluxio (branche de
  développement de la base) ; si elle manque, Pono le dit et ne la crée pas dans cette phase.
- **La branche de développement** du projet est celle que suit l'environnement de développement
  déjà lu par Pono (en général `dev`).
- **La sauvegarde par lots** se fait après environ une minute sans écriture ; le seuil est une valeur
  réglable, pas un contrat.
- **Une taille maximale par fichier écrit** (de l'ordre du mégaoctet) suffit au code source ; les
  médias lourds passent par le dépôt directement.
- **Les premiers utilisateurs** sont l'auteur et une personne proche, chacun sur un serveur relié à
  Pono ; aucun tiers n'est ouvert avant la décision de l'US6.
- **Les outils d'écriture** suivent les règles de la phase 3 : consentement, accès « Lecture et
  actions », annotation destructive, journal au nom de l'agent.
