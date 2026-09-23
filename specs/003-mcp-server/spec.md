# Feature Specification: Le serveur MCP et le plugin

**Feature Branch**: `003-mcp-server`

**Created**: 2026-09-23

**Status**: Draft

**Input**: User description: "Phase 3 de la roadmap de Pono : « Le serveur MCP et le plugin ». Livrable unique : piloter ses projets depuis Claude et depuis Codex, avec les mêmes droits que dans la console, sans qu'aucune capacité ne soit réservée à un agent (D-005). Serveur MCP distant sur l'adresse de la console ; serveur d'autorisation OAuth propre avec enregistrement dynamique de client et consentement humain dans la console ; outils qui correspondent aux capacités de la console des phases 1 et 2, annotés lecture seule ou destructif ; la validation d'une mise en ligne reste un geste humain ; instructions servies par le serveur (D-006) ; agents connectés visibles et révocables dans la console, chaque action tracée ; plugin léger pour Claude, même connexion depuis Codex ; politique de confidentialité publiée. Preuve de fin : une même action donne le même résultat depuis la console, depuis Claude et depuis Codex ; aucun chemin réservé à un agent ; soumission au répertoire de connecteurs décidée par un humain."

## Clarifications

### Session 2026-09-23

- Q: L'agent peut-il déclencher un retour arrière de la production ? → A: Non. Il peut seulement le demander ; la demande apparaît dans la console et une personne la confirme ou l'écarte. Ce qui touche la production reste un geste humain, comme la validation.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Relier son agent à son atelier, en donnant son accord (Priority: P1)

Depuis Claude ou Codex, la personne ajoute Pono comme serveur d'outils. L'agent s'enregistre seul,
puis la personne est envoyée dans la console : elle s'y connecte comme d'habitude, voit quel agent
demande l'accès et à quoi, et accepte ou refuse. Aucune clé à copier, aucun jeton à coller.

**Why this priority**: sans connexion, aucun autre parcours n'existe. C'est aussi là que se joue la
sécurité : l'agent n'obtient que ce que la personne a accepté, dans son organisation.

**Independent Test**: depuis un client d'agent neuf, ajouter l'adresse du serveur, suivre le
parcours jusqu'au consentement dans la console, accepter, puis vérifier que l'agent voit la liste
des outils et que la console montre ce nouvel agent.

**Acceptance Scenarios**:

1. **Given** un client d'agent qui ne connaît pas Pono, **When** la personne ajoute l'adresse du
   serveur, **Then** le client découvre seul comment s'autoriser et s'enregistre, sans qu'aucune
   clé ne soit saisie.
2. **Given** un client enregistré, **When** l'autorisation commence, **Then** la personne arrive
   dans la console, se connecte si besoin avec son fournisseur de code, et voit le nom du client,
   l'étendue demandée et son organisation avant de décider.
3. **Given** la page de consentement, **When** la personne refuse, **Then** le client ne reçoit
   aucun accès et le refus est tracé.
4. **Given** la page de consentement, **When** la personne accepte en lecture seule, **Then** le
   client ne peut appeler que les outils de lecture.
5. **Given** une personne non autorisée à utiliser Pono, **When** elle tente de consentir, **Then**
   elle est refusée comme à la connexion de la console.

---

### User Story 2 - Lire l'état réel de ses projets depuis l'agent (Priority: P1)

Dans sa conversation avec l'agent, la personne demande où en sont ses projets, ce qui bloque une
mise en ligne, ou ce qui s'est passé hier sur un projet. L'agent répond avec exactement les mêmes
faits que la console, datés de la même façon.

**Why this priority**: c'est la raison d'être de la phase : reprendre un projet sans quitter l'agent,
sur la vérité de Pono et pas sur la mémoire de l'agent.

**Independent Test**: pour un même projet, comparer ce que rendent la console et l'outil de
l'agent (état, raison, dernier déploiement, environnements, mises en ligne et garde-fous, journal) :
les faits doivent être identiques.

**Acceptance Scenarios**:

1. **Given** un agent autorisé, **When** il demande l'atelier, **Then** il reçoit les mêmes projets,
   états, verdicts et heures de relevé que la console.
2. **Given** un projet, **When** l'agent demande son détail, ses mises en ligne ou son journal,
   **Then** il reçoit les mêmes faits que la console, et aucune valeur secrète.
3. **Given** un projet d'une autre organisation, **When** l'agent le demande, **Then** il reçoit
   « introuvable », jamais « interdit ».

---

### User Story 3 - Agir depuis l'agent avec les droits de la console, sauf valider (Priority: P1)

L'agent importe un projet, demande un relevé, demande une réévaluation après avoir corrigé un
changement refusé, pose la protection de la production, ou demande un retour arrière. Chaque action
a le même effet que dans la console et apparaît au journal avec le nom de l'agent. Valider une mise
en ligne reste impossible depuis l'agent : c'est le geste humain que garantit la phase 2.

**Why this priority**: « les mêmes droits que dans la console » est la promesse de la phase ; la
limite de la validation est ce qui garde le garde-fou mécanique.

**Independent Test**: faire la même action depuis la console et depuis l'agent sur deux projets
équivalents ; vérifier que les résultats sont identiques, que le journal nomme l'agent, et
qu'aucun outil ne permet de valider une mise en ligne.

**Acceptance Scenarios**:

1. **Given** un agent autorisé en lecture et action, **When** il importe un dépôt, **Then** le projet
   apparaît comme s'il avait été importé depuis la console.
2. **Given** une mise en ligne refusée, **When** l'agent demande une réévaluation, **Then** elle est
   réévaluée comme depuis la console, et le journal nomme l'agent.
3. **Given** une mise en ligne en attente de validation, **When** l'agent cherche à la valider,
   **Then** aucun outil ne le permet et la réponse l'invite à demander à la personne de valider
   dans la console.
4. **Given** un outil qui modifie quelque chose, **When** le client d'agent le présente, **Then** il
   est annoté comme destructif ; un outil de lecture est annoté lecture seule.
5. **Given** un agent qui demande un retour arrière, **When** la demande arrive, **Then** la
   production ne change pas ; la console montre la demande, et seule une personne peut la confirmer
   ou l'écarter (FR-011).

---

### User Story 4 - Voir et couper l'accès des agents (Priority: P2)

Dans la console, la personne voit la liste des agents reliés à son atelier : nom du client, étendue
accordée, date de consentement, dernière utilisation. Elle coupe l'accès de l'un d'eux d'un clic ;
l'agent perd l'accès immédiatement.

**Why this priority**: un accès qu'on ne peut pas voir ni retirer n'est pas maîtrisé. C'est aussi la
condition pour que la console reste le chemin complet (D-005).

**Independent Test**: relier deux agents, en révoquer un depuis la console, vérifier que ses appels
suivants sont refusés et que l'autre fonctionne encore.

**Acceptance Scenarios**:

1. **Given** deux agents reliés, **When** la personne ouvre la page des connexions, **Then** elle
   voit les deux, avec leur étendue et leur dernière utilisation.
2. **Given** un agent relié, **When** la personne coupe son accès, **Then** son prochain appel est
   refusé et doit repasser par le consentement.

---

### User Story 5 - Un plugin léger, un savoir-faire servi par le serveur (Priority: P2)

La personne installe le plugin Pono dans Claude : il relie le serveur et ajoute quelques points
d'entrée (par exemple « où en sont mes projets », « pourquoi cette mise en ligne est refusée »).
Les instructions de l'agent et la description des outils viennent du serveur ; une amélioration
côté serveur profite à tous sans réinstaller. Depuis Codex, la même adresse suffit.

**Why this priority**: c'est l'accès le plus simple pour la cible (D-006) ; il vient après la
connexion et les outils, qui marchent sans lui.

**Independent Test**: installer le plugin dans un client neuf, vérifier qu'il se relie au serveur
et que ses points d'entrée appellent les outils ; changer une description côté serveur et vérifier
qu'elle est vue sans réinstaller.

**Acceptance Scenarios**:

1. **Given** le plugin installé, **When** la personne l'active, **Then** le client se relie au
   serveur par le parcours de la User Story 1.
2. **Given** une nouvelle version des instructions côté serveur, **When** un client de la version
   précédente se connecte, **Then** il est encore servi ; un client plus ancien reçoit un message
   qui l'invite à se mettre à jour.

---

### User Story 6 - Une politique de confidentialité vraie, publiée (Priority: P3)

Avant de relier un agent, la personne peut lire, en français ou en anglais, ce que Pono lit, garde,
trace et ne fait jamais, et comment tout retirer.

**Why this priority**: exigée par les répertoires de connecteurs et due à la personne ; elle ne
bloque pas l'usage par l'auteur.

**Independent Test**: ouvrir la page publique, vérifier qu'elle décrit exactement les données
lues et gardées par Pono, sans affirmation non prouvée.

**Acceptance Scenarios**:

1. **Given** un visiteur non connecté, **When** il ouvre la politique, **Then** il la lit dans sa
   langue, sans connexion.
2. **Given** la politique, **When** on la compare au registre de vérité, **Then** chaque affirmation
   s'y rattache.

---

### Edge Cases

- **Jeton expiré** : l'agent le renouvelle sans nouvelle intervention tant que l'accès n'est pas
  révoqué ; après révocation, le renouvellement échoue.
- **Client inconnu ou adresse de retour non enregistrée** : l'autorisation est refusée avant tout
  consentement.
- **Personne non connectée à la console au moment du consentement** : elle passe par la connexion
  habituelle, puis revient au consentement sans perdre la demande.
- **Demande de consentement abandonnée** : elle expire au bout de 10 minutes.
- **Outil d'action appelé avec une étendue en lecture seule** : refusé, avec un code stable.
- **Même action demandée deux fois par l'agent** (par exemple deux retours arrière) : les mêmes
  règles que dans la console s'appliquent (`rollback.in_progress`).
- **Fournisseur indisponible** : l'outil rend le même code d'erreur stable que la console
  (`provider.unavailable`), jamais une réponse inventée.
- **Plusieurs organisations** (phase 5) : hors périmètre ; l'accès porte sur l'organisation de la
  personne au moment du consentement.

## Requirements *(mandatory)*

### Functional Requirements

**Connexion et consentement**

- **FR-001**: Le système MUST exposer un serveur d'outils pour agents à une adresse publique stable
  de la console, découvrable par les clients sans configuration manuelle d'autorisation.
- **FR-002**: Le système MUST permettre à un client d'agent de s'enregistrer seul, puis d'obtenir un
  accès uniquement après le consentement explicite d'une personne autorisée, donné dans la console
  avec sa session.
- **FR-003**: Le consentement MUST montrer le nom du client, l'étendue demandée et l'organisation, et
  laisser la personne choisir « lecture seule » ou « lecture et actions ».
- **FR-004**: Les accès MUST être de courte durée et renouvelables tant qu'ils ne sont pas révoqués ;
  aucun jeton ni code n'est conservé en clair.
- **FR-005**: La personne MUST pouvoir voir les agents reliés (client, étendue, date d'accord,
  dernière utilisation) et couper l'accès de chacun ; l'effet est immédiat.

**Outils**

- **FR-006**: Le système MUST offrir des outils de lecture : atelier, détail d'un projet, mises en
  ligne d'un projet avec leurs garde-fous, journal de preuves.
- **FR-007**: Le système MUST offrir des outils d'action : importer un projet, demander un relevé,
  demander une réévaluation d'une mise en ligne, poser la protection de la production, et le retour
  arrière selon FR-011.
- **FR-008**: Chaque outil MUST rendre les mêmes faits et les mêmes codes d'erreur stables que la
  route équivalente de la console ; aucun outil ne fait ce que la console ne fait pas (D-005).
- **FR-009**: Chaque outil MUST être annoté lecture seule ou destructif ; un outil d'action n'est
  proposé qu'à un accès « lecture et actions ».
- **FR-010**: Aucun outil MUST NOT permettre de valider une mise en ligne ; la réponse à une
  tentative indique que la validation se fait dans la console.
- **FR-011**: L'agent MUST pouvoir seulement **demander** un retour arrière. La demande apparaît
  dans la console, sur le projet et dans le bandeau de verdict ; une personne la confirme (le retour
  arrière de la phase 2 s'exécute alors) ou l'écarte. Une demande non traitée expire au bout de
  24 heures. Demande, confirmation, refus et expiration sont inscrits au journal.
- **FR-012**: Toute action faite par un agent MUST être inscrite au journal de preuves du projet,
  auteur « agent » avec le nom du client et la personne qui a donné l'accès.

**Savoir-faire servi par le serveur**

- **FR-013**: Les instructions de l'agent et les descriptions des outils MUST être servies par le
  serveur, dans la langue de la personne quand le client la transmet, sinon en anglais.
- **FR-014**: Le serveur MUST annoncer sa version ; il accepte la version actuelle et la précédente,
  et répond à une plus ancienne par un message stable invitant à se mettre à jour.
- **FR-015**: Un plugin pour Claude MUST ne porter que la connexion au serveur et quelques points
  d'entrée ; la même connexion MUST fonctionner depuis Codex sans plugin.

**Confidentialité et cloisonnement**

- **FR-016**: Une politique de confidentialité MUST être publiée, publique, en français et en
  anglais, chaque affirmation rattachée au registre de vérité.
- **FR-017**: Les données des clients, consentements et accès MUST être cloisonnées par
  organisation (RLS dans la migration créatrice) ; un accès ne traverse jamais l'organisation.
- **FR-018**: Aucun nom de fournisseur (dont celui des agents) MUST NOT apparaître dans le domaine
  (D-002) ; tout texte visible passe par les catalogues (D-013).

### Key Entities

- **Client d'agent** : un logiciel d'agent enregistré auprès de Pono (nom, adresses de retour).
  Il n'appartient à personne tant qu'aucun consentement n'est donné.
- **Consentement** : l'accord d'une personne à un client, pour une organisation et une étendue
  (lecture seule, lecture et actions) ; révocable.
- **Accès** : les jetons de courte durée et de renouvellement issus d'un consentement ; conservés
  sous forme non réversible.
- **Demande de retour arrière** : une demande d'agent en attente, confirmée ou écartée par une
  personne dans la console, ou expirée.
- **Appel d'outil tracé** : une entrée du journal de preuves, auteur agent, avec le client et la
  personne.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Pour chaque outil, le résultat depuis Claude, depuis Codex et depuis la console est
  identique sur un même projet réel (mêmes faits, mêmes codes), vérifié outil par outil.
- **SC-002**: Aucune capacité n'est accessible par un agent sans l'être aussi par la console ; la
  validation d'une mise en ligne et l'exécution d'un retour arrière restent impossibles depuis un
  agent.
- **SC-003**: Relier un nouvel agent prend moins de 2 minutes, de l'ajout de l'adresse au premier
  outil qui répond, sans saisir de clé.
- **SC-004**: Un accès coupé dans la console est refusé dès l'appel suivant.
- **SC-005**: Aucune valeur de jeton ni de code n'est lisible en base ou dans les journaux.
- **SC-006**: La politique de confidentialité est publiée et chaque affirmation se rattache au
  registre de vérité.
- **SC-007**: La soumission au répertoire de connecteurs est décidée par l'auteur, pas par l'agent.

## Assumptions

- Premiers utilisateurs : l'auteur et une personne proche ; clients visés : Claude (application et
  Claude Code, avec le plugin) et Codex.
- La connexion à Pono reste celle du fournisseur de code (phase 1) ; le consentement réutilise la
  session de la console.
- Étendues : « lecture seule » et « lecture et actions » ; la personne choisit au consentement.
- Durées : accès d'une heure, renouvellement jusqu'à 30 jours sans usage, puis nouveau consentement.
- Le serveur d'outils est servi à l'adresse publique de la console (`pono-staging…`, HTTPS depuis
  la phase 1).
- La politique de confidentialité ne décrit que ce que Pono fait réellement aux phases 1 à 3.
- Hors périmètre : runtime de développement (phase 4), rôles et invités, plusieurs organisations par
  personne (phase 5), canevas, soumission effective au répertoire de connecteurs.
