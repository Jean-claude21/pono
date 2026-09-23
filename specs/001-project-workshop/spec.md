# Feature Specification: L'atelier qui tient les projets

**Feature Branch**: `001-project-workshop`

**Created**: 2026-09-22

**Status**: Draft

**Input**: User description: "Phase 1 de la roadmap de Pono : « L'atelier qui tient les projets ». Livrable unique : voir l'état réel de ses propres projets au même endroit, et reprendre l'un d'eux sans rien chercher. Socle d'internationalisation dès le départ ; modèle organisation, membre, rôle, projet, environnement, connexion, déploiement ; cloisonnement par organisation ; connexion d'un fournisseur de code par autorisation ; import d'un projet existant et lecture de son manifeste ; relevé des quotas avec alerte avant la pause ; écran d'atelier dans le design validé. Preuve de fin : cinq projets réels importés avec un état juste sans saisie manuelle, reprise chronométrée sous la minute."

## Clarifications

### Session 2026-09-22

- Q: Pour les seuils d'alerte, faut-il la limite réelle de l'offre de la personne ou celle de l'offre gratuite ? → A: La limite réelle quand le fournisseur l'expose, sinon celle de l'offre gratuite, avec la source affichée.
- Q: Qu'est-ce qui compte comme activité pour les états « actif » et « en veille » ? → A: Les commits sur n'importe quelle branche, et les déploiements.
- Q: Quand un projet a plusieurs previews ouvertes, faut-il les afficher toutes ? → A: La plus récente dans la ligne du projet ; toutes dans le détail du projet.
- Q: Au bout de combien de secondes un lien vérifié est-il en panne ? → A: 10 secondes, après une seconde tentative.

### Session 2026-09-23

- Q: Par quel canal la personne reçoit-elle une alerte de quota hors de l'atelier ? → A: Par Telegram, qu'elle relie elle-même depuis la console ; le courriel reste possible quand un serveur d'envoi est configuré.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Importer un projet et voir son état réel (Priority: P1)

Une personne qui construit avec un agent connecte son fournisseur de code, choisit l'un de ses dépôts,
et le projet apparaît dans son atelier avec son état réel : ses environnements, ses liens qui
marchent, son dernier déploiement. Elle n'a rien saisi à la main.

**Why this priority**: c'est le livrable unique de la phase. Sans lui, l'atelier est vide et aucune
autre histoire n'a de sens.

**Independent Test**: connecter un fournisseur de code, importer un dépôt réel qui a déjà été mis en
ligne, et vérifier que l'atelier affiche ses environnements, son dernier déploiement et au moins un
lien qui répond — sans aucun champ rempli par la personne.

**Acceptance Scenarios**:

1. **Given** une personne connectée sans aucune connexion de fournisseur, **When** elle autorise
   Pono à lire son fournisseur de code, **Then** elle voit la liste des dépôts auxquels elle a donné
   accès, et aucune clé permanente ne lui est demandée.
2. **Given** une connexion active, **When** elle importe un dépôt qui porte un manifeste de projet,
   **Then** le projet apparaît avec ses environnements, ses adresses et son dernier déploiement lus
   depuis ce manifeste et depuis les fournisseurs qu'il désigne.
3. **Given** un projet importé, **When** elle ouvre l'atelier, **Then** chaque lien affiché a été
   vérifié récemment, et un lien qui ne répond pas est présenté comme tel, jamais comme valide.
4. **Given** un projet importé, **When** un nouveau déploiement a lieu chez le fournisseur,
   **Then** l'atelier l'affiche au plus tard au relevé suivant, sans action de la personne.

---

### User Story 2 - Reprendre un projet sans rien chercher (Priority: P1)

Des semaines après son dernier passage, la personne ouvre l'atelier et retrouve en un coup d'œil ce
qui tourne, ce qui demande son attention, et où cliquer pour reprendre.

**Why this priority**: c'est la raison d'être du produit (mandat : reprise immédiate). L'import
seul ne prouve rien si la reprise reste lente.

**Independent Test**: avec plusieurs projets importés, chronométrer le temps entre l'ouverture de
l'atelier et l'ouverture du lien de production d'un projet choisi au hasard, accompagné de la date
et de l'auteur de son dernier déploiement.

**Acceptance Scenarios**:

1. **Given** plusieurs projets importés, **When** la personne ouvre l'atelier, **Then** elle voit,
   pour chaque projet, son état, ses environnements, son dernier déploiement et son quota du mois.
2. **Given** au moins un projet en difficulté, **When** l'atelier s'affiche, **Then** ce qui demande
   une décision apparaît avant la liste, sous la forme d'un bandeau de verdict.
3. **Given** l'atelier affiché, **When** la personne filtre par état, **Then** seuls les projets de
   cet état restent, avec leur nombre indiqué sur chaque filtre.

---

### User Story 3 - Être prévenu avant que ses quotas lâchent (Priority: P2)

La personne vit sur des paliers gratuits. Pono relève la consommation de ses fournisseurs
d'hébergement et de base, et la prévient avant que ses sites ne s'arrêtent.

**Why this priority**: c'est la promesse « ça tient » appliquée au terrain où la panne est la plus
fréquente, mais l'atelier apporte déjà sa valeur sans elle.

**Independent Test**: sur un projet dont la consommation dépasse le seuil d'alerte, vérifier qu'une
alerte est émise et visible, et qu'elle n'est pas émise une seconde fois pour le même seuil.

**Acceptance Scenarios**:

1. **Given** un projet dont un quota atteint 80 % de sa limite, **When** le relevé a lieu,
   **Then** le projet passe en état « attention » et la personne est prévenue.
2. **Given** un quota qui atteint 95 %, **When** le relevé a lieu, **Then** une seconde alerte, plus
   forte, est émise.
3. **Given** une alerte déjà émise pour un seuil, **When** le relevé suivant confirme le même seuil,
   **Then** aucune nouvelle alerte n'est émise pour ce seuil dans la même période de facturation.

---

### User Story 4 - Utiliser Pono dans sa langue (Priority: P2)

La personne utilise Pono en français ou en anglais. Tous les textes, les dates, les nombres et les
messages d'erreur suivent la langue choisie.

**Why this priority**: le produit est international dès le départ (D-013). La poser maintenant
évite de reprendre chaque écran plus tard.

**Independent Test**: basculer la langue sur la landing puis dans l'atelier, et vérifier qu'aucun
texte visible ne reste dans l'autre langue, dates et nombres compris.

**Acceptance Scenarios**:

1. **Given** une première visite, **When** la page s'affiche, **Then** la langue est celle du
   navigateur si elle est prise en charge, sinon le français.
2. **Given** une personne qui choisit une langue, **When** elle revient plus tard, **Then** son
   choix est conservé et prime sur celle du navigateur.
3. **Given** une erreur renvoyée par le service, **When** elle s'affiche, **Then** son message est
   dans la langue de la personne, et son code reste identique quelle que soit la langue.

---

### User Story 5 - Chacun son atelier, étanche (Priority: P2)

Les deux premiers utilisateurs ont chacun leur atelier. Aucun ne voit les projets, connexions ou
quotas de l'autre.

**Why this priority**: l'organisation est la frontière dure du produit. Elle doit tenir dès la
première donnée, avant toute ouverture à d'autres personnes.

**Independent Test**: avec deux personnes et deux ateliers, tenter d'accéder depuis l'une à un
projet de l'autre, par l'écran comme par une requête directe, et constater un refus.

**Acceptance Scenarios**:

1. **Given** deux personnes, chacune dans sa propre organisation, **When** l'une ouvre son atelier,
   **Then** elle ne voit que ses projets.
2. **Given** l'identifiant d'un projet d'une autre organisation, **When** une personne tente d'y
   accéder directement, **Then** l'accès est refusé sans confirmer que le projet existe.

---

### Edge Cases

- Un dépôt importé **sans manifeste Pono** : Pono en propose un, pré-rempli, par une proposition de
  modification sur le dépôt ; tant qu'elle n'est pas fusionnée, l'état est déduit des fournisseurs
  et le projet est marqué « manifeste proposé ».
- Une **proposition de manifeste refusée ou fermée** par la personne : le projet reste importé avec
  l'état déduit, marqué « manifeste absent », et Pono ne la repropose pas sans demande.
- Un manifeste qui désigne une ressource **introuvable** chez le fournisseur : le projet est
  importé, la ressource est marquée « introuvable », jamais inventée.
- Une connexion **révoquée** côté fournisseur : l'atelier le signale, conserve le dernier état connu
  en le datant, et cesse de le présenter comme à jour.
- Un fournisseur **indisponible** au moment du relevé : l'état précédent est conservé et marqué
  comme non rafraîchi, avec son horodatage.
- Le **même dépôt importé deux fois** dans une organisation : refusé, le projet existant est
  proposé à la place.
- Un lien de production qui **répond lentement** : au-delà de 10 secondes, deux fois de suite, il est
  en panne ; une première tentative lente seule ne suffit pas, pour absorber le réveil d'un service
  en veille.
- Une **langue non prise en charge** par le navigateur : le français s'applique.

## Requirements *(mandatory)*

### Functional Requirements

**Internationalisation**

- **FR-001**: Tout texte visible de la landing et de l'atelier MUST provenir d'un catalogue de
  traduction ; aucun texte visible n'est écrit directement dans un écran.
- **FR-002**: Le système MUST proposer le français (par défaut) et l'anglais.
- **FR-003**: Le système MUST déterminer la langue par le choix explicite de la personne, puis par
  la langue du navigateur, puis par défaut en français.
- **FR-004**: Dates, nombres, pourcentages et durées MUST être formatés selon la langue active.
- **FR-005**: Les erreurs renvoyées par le service MUST porter un code stable, indépendant de la
  langue ; leur message est traduit côté interface.

**Personnes et organisations**

- **FR-006**: Chaque personne MUST appartenir à au moins une organisation, et chaque projet à
  exactement une organisation.
- **FR-007**: Une personne MUST ne voir et n'agir que sur les données des organisations dont elle
  est membre ; ce cloisonnement MUST être garanti au niveau des données, pas seulement de
  l'interface.
- **FR-008**: Chaque membre MUST porter un rôle dans son organisation ; en phase 1 le seul rôle
  exercé est celui de propriétaire, le modèle devant accueillir les autres rôles sans refonte.
- **FR-009**: L'accès à Pono MUST être limité à une liste de personnes autorisées ; il n'y a pas
  d'inscription publique.

**Connexions aux fournisseurs**

- **FR-010**: La connexion à un fournisseur de code MUST passer par une autorisation que la personne
  accorde chez ce fournisseur ; aucune clé permanente ne lui est demandée.
- **FR-011**: Toute donnée d'accès conservée MUST être chiffrée au repos et n'apparaître dans aucun
  écran, journal ou message. Quand un fournisseur n'offre pas d'autorisation et impose une clé,
  chaque utilisation de cette clé MUST être tracée : connexion, action, date (D-007).
- **FR-012**: La personne MUST pouvoir révoquer une connexion depuis Pono, avec effet immédiat.
- **FR-013**: L'atelier MUST afficher l'état de chaque connexion : active, expirée ou révoquée.

**Import de projets**

- **FR-014**: La personne MUST pouvoir lister les dépôts accessibles par sa connexion et en importer
  un comme projet.
- **FR-015**: À l'import, le système MUST lire le manifeste de projet versionné dans le dépôt et en
  déduire les environnements et les ressources liées chez les fournisseurs.
- **FR-016**: Le système MUST pouvoir reconstruire l'état d'un projet à partir de son dépôt et de ses
  fournisseurs seuls (D-003).
- **FR-017**: Un dépôt déjà importé dans l'organisation MUST ne pas pouvoir l'être une seconde fois.
- **FR-018**: À l'import d'un dépôt sans manifeste Pono, le système MUST pré-remplir un manifeste à
  partir des formats déjà présents dans le dépôt (manifeste de l'atelier, de Fluxio ou de Livio) et
  des ressources liées détectées chez les fournisseurs, puis le **proposer comme modification sur le
  dépôt** (pull request). Il ne devient la source de vérité qu'une fois fusionné par la personne.
- **FR-029**: Le système MUST NOT écrire directement sur une branche d'un dépôt : toute écriture est
  une proposition de modification que la personne accepte ou refuse.
- **FR-030**: La connexion au fournisseur de code MUST ne demander que les permissions nécessaires :
  lire les dépôts choisis et y proposer des modifications. Quand le fournisseur n'offre pas de
  permission plus fine qu'une écriture, le garde-fou de FR-029 la borne (research R-03).

**État des projets**

- **FR-019**: Pour chaque projet, le système MUST afficher ses environnements, l'adresse de chacun,
  son dernier déploiement (date, auteur, résultat) et son quota du mois. Quand plusieurs previews
  sont ouvertes, la ligne du projet montre **la plus récente** ; le détail du projet les montre toutes.
- **FR-020**: Chaque adresse affichée MUST avoir été vérifiée lors du dernier relevé. Une adresse est
  **en panne** si elle ne répond pas en **10 secondes**, lors de deux tentatives successives ; elle est
  alors marquée comme telle.
- **FR-021**: Chaque projet MUST porter exactement un état parmi : **en bonne santé**, **actif**,
  **attention**, **en panne**, **en veille**, selon les règles suivantes, évaluées dans cet ordre :
  - **en panne** : la production ne répond pas, ou son dernier déploiement a échoué ;
  - **attention** : un quota a dépassé 80 %, ou une connexion nécessaire est expirée ou révoquée ;
  - **actif** : un déploiement est en cours, ou une activité a eu lieu dans les dernières 24 heures ;
  - **en veille** : aucune activité depuis 30 jours ;

  Une **activité** est un commit sur n'importe quelle branche du dépôt, ou un déploiement.
  - **en bonne santé** : dans tous les autres cas.
- **FR-022**: L'état MUST être relevé automatiquement à intervalle régulier, au plus toutes les
  15 minutes, et la personne MUST pouvoir demander un relevé immédiat.
- **FR-023**: Toute information affichée MUST indiquer l'heure de son dernier relevé ; une
  information non rafraîchie n'est jamais présentée comme actuelle.

**Quotas**

- **FR-024**: Le système MUST relever la consommation du fournisseur d'hébergement et du fournisseur
  de base du chemin unique (D-009), rapportée à la **limite réelle de l'offre de la personne** quand
  le fournisseur l'expose, sinon à la limite de l'offre gratuite. L'atelier MUST afficher la source
  de chaque limite : « offre du compte » ou « offre gratuite, estimée ».
- **FR-025**: Le système MUST relever les quotas au moins toutes les heures et à chaque relevé
  demandé, et prévenir la personne à 80 % puis à 95 % d'un quota, une seule fois par seuil et par
  période de facturation, dans l'atelier, et hors de l'atelier par une messagerie que la personne
  relie elle-même depuis la console (Telegram), ou par courriel quand un serveur d'envoi est configuré.

**Atelier**

- **FR-026**: L'atelier MUST suivre le système de design validé (D-011) : liste en lignes, pastilles
  d'état, jauges de quota, bandeau de verdict pour ce qui demande une décision.
- **FR-027**: L'atelier MUST permettre de filtrer les projets par état et afficher le nombre de
  projets de chaque état.
- **FR-028**: Tout ce qui se fait depuis l'atelier en phase 1 MUST rester faisable sans agent
  (D-005).

### Key Entities *(include if feature involves data)*

- **Organisation** : l'espace étanche qui possède les projets et les connexions. Frontière dure.
- **Personne** : quelqu'un qui accède à Pono ; porte une préférence de langue.
- **Membre** : l'appartenance d'une personne à une organisation, avec son rôle.
- **Rôle** : ce qu'un membre peut faire dans son organisation ; « propriétaire » en phase 1.
- **Connexion** : l'autorisation accordée par une organisation sur un fournisseur ; porte son état
  et, chiffrée, sa donnée d'accès.
- **Projet** : l'objet ancre. Un dépôt importé, rattaché à une organisation, avec son manifeste.
- **Manifeste** : la description du projet versionnée dans son dépôt ; son statut est présent,
  proposé ou absent.
- **Environnement** : une instance d'un projet — production, preview, développement — avec son
  adresse et le résultat de sa dernière vérification.
- **Déploiement** : une mise en ligne d'un environnement, avec sa date, son auteur, son commit et son
  résultat.
- **Relevé de quota** : la consommation mesurée d'une ressource à un instant, rapportée à sa limite.
- **Alerte** : un seuil franchi sur un quota, émise une fois par seuil et par période.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Cinq projets réels sont importés et affichent un état juste, sans qu'aucun champ ne
  soit rempli à la main ; accepter une proposition de manifeste compte comme une validation, pas
  comme une saisie.
- **SC-002**: Les deux premiers utilisateurs reprennent un projet choisi au hasard — lien de
  production ouvert, dernier déploiement identifié — en moins d'une minute après l'ouverture de
  l'atelier.
- **SC-003**: Importer un projet prend moins de deux minutes entre le choix du dépôt et l'affichage
  de son état.
- **SC-004**: Un quota qui franchit 80 % déclenche une alerte reçue avant que la ressource
  n'atteigne sa limite, dans 100 % des cas testés.
- **SC-005**: Dans l'une ou l'autre langue, 100 % des textes visibles de la landing et de l'atelier
  sont traduits ; aucun écran ne mélange les deux langues.
- **SC-006**: Aucune donnée d'une organisation n'est accessible depuis une autre, ni par l'écran ni
  par une requête directe, sur l'ensemble des tests de cloisonnement.
- **SC-007**: Lors d'une vérification ponctuelle, l'état affiché de chaque projet correspond à la
  réalité observée chez les fournisseurs, à l'heure de relevé indiquée près.

## Assumptions

- Les premiers utilisateurs sont l'auteur et une personne proche ; chacun a sa propre
  organisation. L'invitation d'un tiers dans une organisation relève de la phase 5.
- La connexion à Pono se fait par l'identité du fournisseur de code, que la personne doit de toute
  façon connecter ; l'accès est réservé aux adresses autorisées.
- Le chemin technique unique (D-009) fixe un fournisseur de code, un fournisseur d'hébergement et un
  fournisseur de base ; les autres fournisseurs sont hors périmètre.
- Quand un fournisseur n'expose pas la limite de l'offre du compte, les limites de l'offre gratuite
  en vigueur servent d'estimation, révisable, et présentée comme telle (FR-024).
- Le courriel d'alerte est envoyé à l'adresse de la personne connue par son fournisseur de code,
  ou à celle qu'elle indique dans la console.
- La messagerie d'alerte se relie par un lien à usage unique, valable 15 minutes, ouvert depuis la
  console ; Pono ne reçoit que l'identifiant de la conversation, jamais de message d'une autre
  personne. Délier la messagerie arrête les alertes par ce canal.
- Les décisions d'architecture déjà tranchées (D-002, D-003, D-007, D-010, D-012) s'appliquent au
  plan ; cette spécification ne les répète pas.
- Hors périmètre de la phase : runtime de développement, serveur pour agents, plugin, garde-fous de
  mise en ligne, canevas métier, inscription publique, invitation de membres.
