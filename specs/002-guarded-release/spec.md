# Feature Specification: La mise en ligne sous garde-fou

**Feature Branch**: `002-guarded-release`

**Created**: 2026-09-23

**Status**: Draft

**Input**: User description: "Phase 2 de la roadmap de Pono : « La mise en ligne sous garde-fou ». Livrable unique : une mise en production qui échoue tant qu'un humain n'a pas validé — mécaniquement, pas par consigne (D-004, principe 5). Garde-fous évalués avant chaque mise en production : aucun secret dans le changement, preview vérifiée, migrations additives uniquement ; un verdict par tentative dans le bandeau de verdict ; une validation humaine explicite dans la console, seule à débloquer la production ; un journal de preuves par projet, en ajout seul ; retour arrière du déploiement de production depuis la console ; protection de la branche de production imposée et vérifiée à l'import et à chaque relevé. Le fournisseur de code applique le blocage ; Pono ne fusionne jamais. Preuve de fin : une migration destructrice refusée et tracée ; démonstration enregistrée, non accélérée, publiée."

## Clarifications

### Session 2026-09-23

- Q: Quand l'hébergement ne produit pas de preview pour une proposition, que fait le garde-fou de la preview ? → A: Il bloque, avec un message qui explique comment activer les previews du projet.
- Q: Une personne peut-elle passer outre un garde-fou refusé ? → A: Jamais depuis Pono. Une suppression voulue se fait en deux temps, déclarée à l'avance dans le manifeste versionné, dans un changement séparé de celui qui cesse de l'utiliser.
- Q: Qui applique la protection de la branche de production ? → A: Pono, sur un clic de la personne dans la console ; l'app du fournisseur de code demande pour cela le droit d'administration du dépôt.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Une mise en ligne dangereuse est refusée, mécaniquement (Priority: P1)

Un agent prépare un changement vers la branche de production d'un projet importé. Le changement
supprime une colonne de la base. Avant toute mise en production, Pono évalue le changement, le
refuse, et le fournisseur de code empêche sa fusion : ni l'agent, ni un argument, ni une consigne
ne le fait passer.

**Why this priority**: c'est le livrable unique de la phase et la preuve de fin. Sans blocage
mécanique, le reste n'est qu'un tableau de bord.

**Independent Test**: sur un projet réel protégé, ouvrir une proposition de changement vers la
branche de production qui contient une migration destructrice ; vérifier que le verdict est
« refusé », que la fusion est impossible chez le fournisseur de code, et que le refus figure dans le
journal du projet.

**Acceptance Scenarios**:

1. **Given** un projet protégé et une proposition vers sa branche de production contenant une
   migration qui supprime ou renomme une table ou une colonne, **When** Pono l'évalue, **Then** le
   verdict est « refusé », le garde-fou des migrations nomme le fichier et l'opération en cause, et
   la fusion reste bloquée chez le fournisseur de code.
2. **Given** une proposition contenant un secret, **When** Pono l'évalue, **Then** le verdict est
   « refusé », le détail nomme le fichier et la ligne, et la valeur du secret n'est jamais affichée
   ni conservée.
3. **Given** une proposition dont la preview ne répond pas, **When** Pono l'évalue, **Then** le
   garde-fou de la preview est en échec et le verdict est « refusé ».
4. **Given** une proposition refusée, **When** un nouveau changement corrige le problème, **Then**
   Pono évalue à nouveau et le verdict reflète la dernière version du changement, jamais une
   version antérieure.

---

### User Story 2 - Rien n'entre en production sans une validation humaine (Priority: P1)

Tous les garde-fous passent. Le changement n'est pas encore mis en production pour autant : la
personne ouvre la console, voit le verdict et le détail de chaque garde-fou, et valide
explicitement. Alors seulement le fournisseur de code accepte la fusion, que la personne fait
elle-même.

**Why this priority**: « échoue tant qu'un humain n'a pas validé » est la promesse exacte de la
phase. Des garde-fous automatiques sans validation humaine laisseraient l'agent seul décideur.

**Independent Test**: avec une proposition dont tous les garde-fous passent, vérifier que la fusion
est bloquée tant que personne n'a validé dans la console, puis qu'elle est permise juste après la
validation, et que la validation est tracée avec son auteur et son heure.

**Acceptance Scenarios**:

1. **Given** une proposition dont tous les garde-fous passent, **When** personne ne l'a validée,
   **Then** son verdict est « en attente de validation » et la fusion reste bloquée.
2. **Given** ce verdict, **When** la personne valide dans la console, **Then** la fusion devient
   permise chez le fournisseur de code, et le journal enregistre qui a validé, quand, et pour quelle
   version exacte du changement.
3. **Given** une proposition validée, **When** un nouveau changement y est ajouté, **Then** la
   validation tombe, les garde-fous sont évalués à nouveau, et une nouvelle validation est exigée.
4. **Given** un agent qui dispose des accès de développement au dépôt, **When** il tente de faire
   passer la proposition en production sans validation humaine, **Then** il n'existe aucun chemin
   pour le faire depuis Pono, et le fournisseur de code refuse la fusion.
5. **Given** une proposition refusée par un garde-fou, **When** la personne ouvre la console,
   **Then** aucune action de validation ne lui est proposée pour ce verdict.

---

### User Story 3 - La branche de production est protégée, et on le sait (Priority: P1)

À l'import d'un projet, puis à chaque relevé, Pono vérifie que la branche de production ne peut
recevoir un changement que par une proposition, et que la vérification de Pono y est obligatoire.
Un projet non protégé est signalé dans l'atelier, et la personne peut le protéger depuis la console.

**Why this priority**: sans protection, les garde-fous se contournent par un envoi direct sur la
branche de production. Le blocage n'est mécanique que si la protection existe.

**Independent Test**: importer un projet sans protection, vérifier qu'il est signalé, appliquer la
protection depuis la console, et vérifier qu'un envoi direct sur la branche de production est
ensuite refusé par le fournisseur de code.

**Acceptance Scenarios**:

1. **Given** un projet dont la branche de production accepte les envois directs, **When** il est
   importé ou relevé, **Then** l'atelier le signale « non protégé » dans son bandeau de verdict.
2. **Given** ce projet, **When** la personne demande la protection depuis la console, **Then** la
   branche de production exige une proposition et la vérification de Pono, y compris pour les
   administrateurs du dépôt, et le journal l'enregistre.
3. **Given** un projet protégé, **When** la protection est retirée chez le fournisseur de code,
   **Then** le relevé suivant le signale « non protégé » et le journal l'enregistre.
4. **Given** un dépôt dont l'offre du fournisseur de code ne permet pas de protéger la branche,
   **When** Pono le relève, **Then** l'atelier dit que la protection est impossible sur cette offre,
   et ne présente jamais ce projet comme protégé.

---

### User Story 4 - Revenir à la version précédente en un geste (Priority: P2)

La production vient de recevoir un changement et quelque chose ne va pas. Depuis la console, la
personne ramène la production à la version précédente qui fonctionnait, sans passer par la ligne de
commande ni par le fournisseur d'hébergement.

**Why this priority**: un garde-fou ne détecte pas tout. Le retour arrière limite le coût d'une
erreur qui passe ; il vient après le blocage, qui est la promesse principale.

**Independent Test**: sur un projet réel, déclencher le retour arrière depuis la console, puis
vérifier que la production sert à nouveau la version précédente, que son lien répond, et que le
retour arrière figure dans le journal.

**Acceptance Scenarios**:

1. **Given** un projet dont la production a au moins un déploiement réussi avant le dernier,
   **When** la personne demande le retour arrière et confirme, **Then** la production redéploie la
   version précédente réussie, et le journal enregistre qui l'a demandé, quand, depuis quelle
   version et vers laquelle.
2. **Given** un projet sans déploiement réussi antérieur, **When** la personne ouvre le détail,
   **Then** le retour arrière n'est pas proposé et la raison est affichée.
3. **Given** un retour arrière demandé, **When** le redéploiement échoue chez le fournisseur,
   **Then** l'échec est affiché et tracé, et l'état de la production n'est jamais présenté comme
   rétabli.

---

### User Story 5 - Le journal de preuves de chaque projet (Priority: P2)

Pour chaque projet, la personne consulte un journal qui raconte ce qui s'est passé : chaque
tentative de mise en ligne, chaque verdict et son détail, chaque validation, chaque refus, chaque
retour arrière, chaque changement de protection. Personne ne peut le réécrire.

**Why this priority**: c'est la mémoire et la preuve. Elle rend le refus démontrable (preuve de fin)
et répond à « qui a mis ça en production, et sur quelle base ? ».

**Independent Test**: après une tentative refusée, une tentative validée et un retour arrière,
vérifier que les trois apparaissent dans l'ordre avec leur auteur et leur heure, et qu'aucune
entrée ne peut être modifiée ou supprimée, même par le service.

**Acceptance Scenarios**:

1. **Given** un projet avec de l'activité, **When** la personne ouvre son journal, **Then** elle voit
   les événements du plus récent au plus ancien, chacun avec son heure, son auteur (personne, agent
   ou Pono) et la version du changement concernée.
2. **Given** une entrée du journal, **When** quiconque tente de la modifier ou de la supprimer,
   **Then** la base le refuse.
3. **Given** deux organisations, **When** l'une consulte un journal, **Then** elle ne voit jamais un
   événement de l'autre.

---

### Edge Cases

- **Migration illisible** : un fichier de migration que Pono ne sait pas analyser fait échouer le
  garde-fou (on refuse ce qu'on ne comprend pas) ; le détail dit que le fichier n'a pas pu être lu.
- **Pas de migration** : un changement sans fichier de migration passe ce garde-fou.
- **Projet sans preview** : quand l'hébergement du projet ne produit pas de preview pour une
  proposition, le garde-fou de la preview est en échec et explique comment activer les previews
  (FR-006).
- **Destruction voulue** : supprimer une colonne devenue inutile passe par deux changements : le code
  cesse de l'utiliser, puis un changement séparé porte la suppression et sa déclaration dans le
  manifeste (FR-008).
- **Preview encore en construction** : le verdict reste « en cours d'évaluation » jusqu'à ce que la
  preview réponde ou échoue ; au-delà de 30 minutes sans preview, le garde-fou est en échec.
- **Faux positif de secret** : une valeur d'exemple manifestement fictive déclenche le garde-fou comme
  un vrai secret ; la personne la retire ou la déclare comme exemple dans le manifeste versionné,
  jamais depuis un clic qui contournerait le garde-fou.
- **Plusieurs propositions ouvertes** : chacune a son propre verdict et sa propre validation.
- **Fusion hors de Pono** : si la production reçoit un changement qui n'a pas été validé (protection
  retirée entre-temps), le journal l'enregistre comme « mise en production sans validation » et le
  projet passe en verdict d'alerte.
- **Fournisseur indisponible** : si le fournisseur de code ou d'hébergement ne répond pas, le
  verdict reste bloquant ; une panne de Pono ou d'un fournisseur ne débloque jamais une mise en
  production.
- **Validation par une autre personne** : seule une personne membre de l'organisation du projet peut
  valider ; l'invité et les rôles fins relèvent de la phase 5.
- **Retour arrière et base** : le retour arrière ramène le code, pas la base ; c'est parce que les
  migrations sont additives que l'ancienne version reste compatible avec la base actuelle.

## Requirements *(mandatory)*

### Functional Requirements

**Tentatives de mise en ligne**

- **FR-001**: Une **tentative de mise en ligne** MUST être créée pour chaque proposition de
  changement ouverte vers la branche de production d'un projet importé, et évaluée à nouveau à
  chaque nouvelle version de ce changement.
- **FR-002**: Chaque tentative MUST porter un verdict parmi : **en cours d'évaluation**,
  **refusé**, **en attente de validation**, **validé**. Seul « validé » permet la fusion.
- **FR-003**: Le verdict et le détail de chaque garde-fou MUST être affichés dans la console, dans
  le bandeau de verdict du design validé (D-011), au plus tard 2 minutes après que la preview du
  changement a répondu ou a échoué.

**Garde-fous**

- **FR-004**: Le garde-fou des **secrets** MUST refuser un changement qui ajoute une clé, un jeton,
  un mot de passe ou une clé privée reconnaissable ; le détail MUST nommer le fichier et la ligne,
  et MUST NOT afficher, journaliser ni conserver la valeur.
- **FR-005**: Le garde-fou des **migrations** MUST refuser un changement dont une migration de base
  supprime ou renomme une table ou une colonne, change le type d'une colonne, vide une table ou
  supprime des lignes sans condition ; une migration illisible MUST être refusée ; le détail MUST
  nommer le fichier et l'opération.
- **FR-006**: Le garde-fou de la **preview** MUST exiger que la preview du changement réponde
  (deux essais de 10 secondes, comme en phase 1). Quand l'hébergement ne produit pas de preview
  pour la proposition, le garde-fou MUST être en échec, avec un détail qui explique comment activer
  les previews du projet.
- **FR-007**: Les garde-fous MUST échouer fermés : un fournisseur qui ne répond pas, une analyse qui
  ne se termine pas ou une erreur de Pono laissent le verdict bloquant.
- **FR-008**: Un garde-fou en échec MUST rendre le verdict « refusé », sans aucun moyen de passer
  outre depuis Pono. Une opération destructrice voulue MUST être déclarée à l'avance dans le
  manifeste versionné (fichier et opération) et arriver dans un changement qui ne contient qu'elle
  et sa déclaration ; le garde-fou l'accepte alors, et le journal l'enregistre comme destruction
  déclarée.

**Validation humaine**

- **FR-009**: Une tentative dont tous les garde-fous passent MUST attendre une validation explicite
  d'une personne membre de l'organisation, faite dans la console avec sa session.
- **FR-010**: La validation MUST porter sur une version exacte du changement ; toute nouvelle version
  MUST annuler la validation et relancer les garde-fous.
- **FR-011**: Aucun chemin MUST NOT permettre à un agent seul de valider : la validation exige une
  session de personne ouverte par le fournisseur d'identité, et aucune interface pour agent n'existe
  en phase 2.
- **FR-012**: Le blocage MUST être appliqué par le fournisseur de code, par une vérification
  obligatoire sur la branche de production que seul Pono peut rendre favorable. Pono MUST NOT
  fusionner, ni pousser sur la branche de production (FR-029 de la phase 1).

**Protection de la branche de production**

- **FR-013**: À l'import et à chaque relevé, Pono MUST vérifier que la branche de production exige
  une proposition, exige la vérification de Pono, et s'applique aussi aux administrateurs.
- **FR-014**: Un projet dont la protection manque ou est incomplète MUST être signalé « non protégé »
  dans l'atelier et dans son détail ; un projet dont l'offre ne permet pas la protection MUST être
  signalé comme tel.
- **FR-015**: La personne MUST pouvoir faire appliquer la protection par Pono d'un clic dans la
  console. C'est la seule écriture de Pono hors de ses branches de proposition, et elle ne porte que
  sur la règle de protection de la branche de production ; l'app du fournisseur de code demande
  pour cela le droit d'administration du dépôt.

**Retour arrière**

- **FR-016**: La personne MUST pouvoir ramener la production à la dernière version précédente
  réussie depuis la console, après une confirmation explicite.
- **FR-017**: Le retour arrière MUST passer par le fournisseur d'hébergement du projet ; son
  résultat MUST être vérifié (lien de production qui répond) et affiché tel qu'il est.

**Journal de preuves**

- **FR-018**: Chaque projet MUST avoir un journal en **ajout seul** : tentatives, résultats de
  garde-fous, verdicts, validations, refus, retours arrière, changements de protection, mises en
  production sans validation. La base MUST refuser toute modification ou suppression d'une entrée.
- **FR-019**: Chaque entrée MUST indiquer son heure, son auteur (personne, agent désigné par le
  fournisseur de code, ou Pono) et la version du changement concernée.
- **FR-020**: Le journal MUST être cloisonné par organisation, comme tout le reste (RLS dans la
  migration créatrice).

**Transverse**

- **FR-021**: Toute capacité de la phase MUST être disponible dans la console web (D-005).
- **FR-022**: Tout texte visible MUST passer par les catalogues français et anglais (D-013) ; les
  verdicts et les codes de garde-fou sont des codes stables traduits par l'interface.
- **FR-023**: Aucun nom de fournisseur MUST NOT apparaître dans le domaine (D-002).
- **FR-024**: Chaque utilisation d'une clé permanente pour le retour arrière MUST être tracée, comme
  en phase 1 (FR-011).

### Key Entities *(include if feature involves data)*

- **Tentative de mise en ligne** : une proposition de changement vers la branche de production d'un
  projet, à une version donnée ; porte un verdict. Appartient à un projet, donc à une organisation.
- **Résultat de garde-fou** : le résultat d'un garde-fou (secrets, migrations, preview) pour une
  tentative : réussi, en échec, en cours ; avec un détail sans aucune valeur sensible.
- **Validation** : l'accord explicite d'une personne sur une tentative, à une version exacte.
- **Protection** : l'état de protection de la branche de production d'un projet : protégé, non
  protégé, impossible sur cette offre ; relevé à chaque passage.
- **Retour arrière** : une demande de redéploiement d'une version antérieure, avec son résultat.
- **Entrée de journal** : un fait daté, attribué, jamais modifié.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Sur les projets réels protégés, 100 % des propositions contenant une migration
  destructrice sont refusées, et aucune n'atteint la production.
- **SC-002**: Aucune proposition n'atteint la production sans une validation humaine enregistrée,
  vérifié sur toutes les mises en production des projets protégés pendant la phase.
- **SC-003**: Le verdict est visible dans la console au plus tard 2 minutes après que la preview a
  répondu ou échoué.
- **SC-004**: Un projet non protégé est signalé au plus tard au relevé suivant (15 minutes).
- **SC-005**: Un retour arrière rend la production à la version précédente, lien qui répond, en moins
  de 5 minutes après la confirmation, hors temps de construction propre au fournisseur.
- **SC-006**: Aucune valeur de secret n'apparaît dans un verdict, un journal ou un fichier de trace.
- **SC-007**: Une tentative de modification d'une entrée du journal est refusée par la base.
- **SC-008**: La démonstration d'un refus de migration destructrice est enregistrée, non accélérée,
  et publiée ; elle se fait sur un projet réel de l'auteur.

## Assumptions

- Les projets concernés sont ceux importés en phase 1 ; la branche de production est celle de
  l'environnement de production déclaré dans le manifeste versionné (D-003).
- Les emplacements des migrations sont lus dans le manifeste quand il les déclare, sinon déduits des
  conventions courantes (dossiers de migrations des outils usuels) ; un projet sans migration
  n'active pas ce garde-fou.
- Le dialecte des migrations analysées est celui de Postgres, la base du chemin unique (D-009).
- La protection de branche exige, chez le fournisseur de code, un dépôt public ou une offre payante
  (D-004) ; Pono le dit plutôt que de le masquer.
- La mise en production reste le geste de la personne chez le fournisseur de code (fusion) ; Pono
  débloque, il ne fusionne pas.
- Le retour arrière porte sur le code déployé, pas sur la base ; les migrations additives rendent la
  version précédente compatible avec la base actuelle.
- La reconnaissance des secrets couvre les formats de clés des fournisseurs courants, les clés
  privées et les affectations évidentes de mots de passe ; elle ne prétend pas tout voir.
- Premiers utilisateurs : l'auteur et une personne proche, sur lectio-reads, fluxio-runtime-test et
  nettio.
- Hors périmètre : serveur MCP et plugin (phase 3), runtime de développement (phase 4), rôles fins et
  invités (phase 5), canevas.
