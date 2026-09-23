# Roadmap — Pono

## Metadata

- **Status** : `candidate`
- **Version** : `2`
- **Last validated** : `2026-09-22`
- **Product boundary** : l'atelier qui tient des projets réels — importés, suivis, mis en ligne
  sous garde-fou, pilotables depuis un agent comme depuis la console.
- **Planning axis** : `DEPENDENCIES_AND_EVIDENCE_NOT_TIME`
- **Deployment policy** : `HUMAN_VALIDATION_BEFORE_DEPLOY`

## Goal

Cinq projets réels posés dans Pono, avec un état juste, une mise en ligne refusée tant qu'un humain
n'a pas validé, et un temps de reprise mesuré sous la minute.

## Ce sur quoi on s'appuie

Rien de tout cela n'est réécrit : ce sont des acquis, avec leur preuve.

| Appui | Ce qu'on en reprend | Phase concernée |
|---|---|---|
| **Fluxio** | Le runtime persistant (Dockerfile, agent de synchronisation), le verrou de production mécanique, la détection de migrations destructrices, les pièges déjà résolus | 4, 5 |
| **Livio** | La pile éprouvée (TanStack Start, Drizzle, base serverless, hébergement), le manifeste de projet, les garde-fous avant production, le retour arrière | 1, 2, 5 |
| **KYA-Platform** | **Le code** : le courtier OAuth pour connecteurs MCP avec enregistrement dynamique de client, l'autorisation, le port de secrets, les workers, l'observabilité, le découpage domaine / application / infrastructure | 1, 3, 5 |
| **Firmo** | La discipline visuelle de la famille (D-011), le bandeau de verdict, un service FastAPI éprouvé en production | 0, 2 |

> **Même auteur, même architecture.** Le code de KYA-Platform est repris tel quel quand il sert, puis
> adapté : ce qui est propre à KYA — unités, catalogue d'artefacts, gouvernance interne — reste dehors.

## Complete Product Scope

Le produit est complet quand, pour un utilisateur qui n'a que son agent et ses comptes gratuits :

1. Il connecte ses fournisseurs par autorisation, sans jamais confier de clé permanente.
2. Il importe ou crée un projet, et son état est juste sans qu'il le saisisse.
3. Il voit tous ses projets, leurs environnements, leurs déploiements et leurs quotas au même endroit.
4. Il code depuis son agent, et voit l'écran changer en quelques secondes.
5. Il met en ligne, et le système **refuse** tant qu'un humain n'a pas validé.
6. Il invite quelqu'un, avec des droits qui tiennent.
7. Il peut partir : tout est sur ses comptes, l'export est un geste.
8. Il utilise Pono en français ou en anglais.

## Advanced Options

- **Canevas métier** — condition : trois projets réels arrivés en production par le même chemin.
- **Infrastructure fournie** — condition : la demande existe, et le coût d'un runtime en veille est mesuré.
- **Second fournisseur de base ou d'hébergement** — condition : un utilisateur réel bloqué par le premier.
- **Analyses de l'application depuis l'agent** — condition : au moins un projet en production avec du trafic.
- **SSO d'entreprise, audit avancé** — condition : un client entreprise qui l'exige par écrit.

> Une option avancée n'est ni une phase datée ni un oubli. Elle reste hors de la condition de fin
> jusqu'à une décision explicite.

## Execution Strategy

- Les phases sont contiguës depuis 0 et se ferment sur leur point de contrôle.
- Elles expriment un ordre de **dépendances et de preuves**, jamais une durée ni une date.
- Chaque phase se traduit avant le code en matrice `surface → données → API → action → preuve → état`.
- Une interface sans données ni action réelle reste `interface codée`, jamais `terminée`.
- `[agent]` se vérifie automatiquement ; `[bloquant]` arrête sur une décision humaine.
- Le RLS est écrit dans la migration créatrice, jamais après coup.
- Aucune phase n'ajoute un second fournisseur tant que le premier chemin n'est pas prouvé (D-009).

## Product Surface Matrix

| Surface | Décision utilisateur | Données durables | API/service | Action réelle | Preuve attendue |
|---|---|---|---|---|---|
| Landing publique | demander un accès | demande d'accès | formulaire | envoi d'une demande | une demande reçue, avec la réponse à « quel projet » |
| Console · projets | lequel reprendre | projet, environnement, déploiement | lecture d'état | ouvrir un lien qui marche | cinq projets réels affichés justes |
| Console · quotas | agir avant la pause | relevé de quota | lecture fournisseur | alerte | une alerte reçue avant épuisement |
| Console · connexions | connecter, révoquer | connexion autorisée | autorisation | révocation effective | une connexion révoquée depuis la console |
| Console · mise en ligne | valider ou refuser | demande de déploiement, verdict | garde-fous | production déployée | un refus, puis une validation |
| Agent (MCP) | agir sans quitter sa conversation | mêmes données | serveur MCP | mêmes actions | une session Claude et une session Codex identiques |
| Runtime de dev | voir sa modification | espace de travail | agent de synchronisation | écran mis à jour | temps mesuré et publié |

---

## Phase 0 — Le socle visuel et le langage du produit · *fermée le 2026-09-22*

> **Preuve de fermeture.** Design v2 validé (D-011) ; paquet `@pono/design` consommé par la console et
> les maquettes ; landing reconstruite sur les jetons ; console déployée et saine sur Coolify, rendu
> vérifié sur l'adresse en ligne.

### Objective
Un système de design éprouvé sur les cas réels du produit — états, quotas, refus — avant d'écrire
le moindre écran définitif.

### Scope
- La discipline de la famille Firmo (D-011) : base achromatique, Inter Tight et JetBrains Mono,
  filets horizontaux seuls, chiffres en chasse fixe, aucune couleur de marque.
- Deux ambiances d'un même système : page publique claire, console sombre.
- Les composants : bandeau de verdict, tableau de projets, pastille d'état, jauge de quota,
  onglets filtrants, boutons, monogramme.
- La validation se fait dans `design/` en HTML, CSS et JS, sans framework.

### Deliverables
- `packages/design/style.css` — la source unique du système, en paquet `@pono/design`.
- `design/landing.html` et `design/admin.html` — les maquettes de référence.
- Les jetons exposés au `@theme` de Tailwind dans la console.

### Dependencies
- Le mandat et le positionnement approuvés.

### Verification
- `[agent]` La page est rendue et **regardée** avant d'être proposée : capture à 1440 px, plus les
  états du dialogue. Une maquette non regardée n'est pas livrée.
- `[agent]` Aucune valeur de couleur, de taille ou d'espacement hors de la charte.
- `[bloquant]` La direction visuelle est approuvée par un humain.

---

## Phase 1 — L'atelier qui tient les projets · *fusionnée dans `main` le 2026-09-23, fermeture en attente de la mesure*

> **Où on en est (2026-09-23, après-midi).** Spec Kit : specify → clarify → plan → tasks → analyze →
> implement → converge, puis une clarification (alertes par Telegram, D-015) → tasks (phase 10) →
> implement → converge (T095). 92 tâches sur 95 faites ; restent T071 (mesure), T094 (première vraie alerte) et T082 (SMTP, facultatif) (`specs/001-project-workshop/tasks.md`).
>
> **Preuves réunies.** Cinq projets réels importés sans saisie, état vérifié à la main chez chaque
> fournisseur ; imports de 21 à 46 s ; RLS forcée dans chaque migration créatrice et étanchéité de
> deux organisations prouvée en CI ; aucun nom de fournisseur dans le domaine ni dans
> l'application ; console, service et worker en ligne sur Coolify, **en HTTPS**
> (`pono-staging.13.140.178.49.sslip.io`) ; alertes Telegram reliées ; lectio-reads
> importé en ligne, manifeste fusionné ; 237 tests du service, 17 Vitest, 10 Playwright
> (`docs/VERITE_ET_PREUVES.md`).
>
> **Tranché le 2026-09-23 (D-015).** Les alertes partent par Telegram (le courriel n'est plus
> bloquant). Pono reste à Francfort : Neon y ouvre désormais toutes ses fonctionnalités.
>
> **Reste, pour fermer.**
> - `[bloquant]` Chronométrer la reprise avec les deux premiers utilisateurs (T071, SC-002). Premier
>   essai de l'auteur : environ 1 min, connexion GitHub comprise ; corrigé depuis (T095 : une session
>   valide ouvre l'atelier sans repasser par GitHub). À refaire.
> - `[fait]` Fusion `dev` → `main` (T074, #5) ; nettio importé en ligne.
> - `[attente]` La première vraie alerte Telegram, au premier quota au-delà de 80 % (T094) : bot
>   configuré et conversation de l'auteur reliée en production.
> - `[facultatif]` Un compte SMTP pour les alertes par courriel (T082).

### Objective
Voir l'état réel de ses propres projets au même endroit, et reprendre l'un d'eux sans rien chercher.

### Scope
- **Socle d'internationalisation** (D-013) : catalogues français et anglais, choix de la langue,
  formats localisés, codes d'erreur stables ; les textes de la landing y migrent.
- Modèle de domaine : organisation, membre, rôle, projet, environnement, connexion, déploiement.
  Ancre : le **projet**. Frontière dure : l'**organisation**.
- Première migration avec RLS, base serverless.
- Connexion d'un fournisseur de code par autorisation (D-007).
- Import d'un projet existant et lecture de son manifeste.
- Relevé des quotas d'hébergement et de base, avec seuil d'alerte.
- Écran d'atelier : liste des projets, états, liens, dernier déploiement.

### Deliverables
- Migrations, modèle, adaptateurs de lecture, écran d'atelier, relevé de quotas.

### Dependencies
- Phase 0 fermée. D-010 confirmée.

### Verification
- `[agent]` Cinq projets réels importés, état juste, aucun champ saisi à la main.
- `[agent]` RLS présent dans chaque migration créatrice ; aucun nom de fournisseur dans le domaine.
- `[bloquant]` Temps de reprise chronométré sous la minute, par les deux premiers utilisateurs.

---

## Phase 2 — La mise en ligne sous garde-fou · *en cours sur `002-guarded-release`*

> **Où on en est (2026-09-23, soir).** Spec Kit : specify → clarify (3 questions, options
> recommandées retenues) → plan → tasks → analyze → implement. 38 tâches sur
> 41 faites ; restent T037, T038, T039 (gestes de l'auteur et preuve réelle).
>
> **Ce qui marche, testé.** Trois garde-fous (secrets, migrations SQL, preview du commit de tête),
> un verdict par proposition, la validation dans la console sur une version exacte, la vérification
> `pono/release` liée à l'app chez GitHub, la protection posée d'un clic, le retour arrière Netlify
> et Coolify confirmé par l'hébergeur, le journal de preuves que même le propriétaire de la base ne
> peut pas réécrire. 337 tests du service (94,6 % de couverture), 17 Vitest, 15 Playwright.
>
> **Décision D-016.** Blocage par une vérification obligatoire liée à l'app Pono, protection posée
> par Pono sur un clic, retour arrière par l'API de l'hébergeur, aucun contournement d'un garde-fou
> refusé : une destruction voulue se déclare dans le manifeste.
>
> **Prouvé sur un projet réel (2026-09-23).** Permissions de l'app acceptées ; lectio-reads protégée
> depuis la console ; lectio-reads#3 (migration qui supprime une colonne) refusée par Pono et
> bloquée par GitHub, refus au journal (`docs/VERITE_ET_PREUVES.md`).
>
> **Reste, pour fermer.** `[auteur]` Valider une proposition réelle et, si tu le veux, un retour
> arrière réel (T038, étapes 3 à 5) ; `[bloquant]` enregistrer la démonstration (T039).

### Objective
Une mise en ligne qui échoue tant qu'un humain n'a pas validé — mécaniquement, pas par consigne.

### Scope
- Garde-fous : secrets absents, preview vérifiée, migrations additives.
- Verdict, journal de preuves par projet, retour arrière du déploiement.
- Protection de branche imposée et vérifiée à l'import d'un projet.

### Deliverables
- Moteur de garde-fous, écran de confirmation, journal de preuves.

### Dependencies
- Phase 1 fermée.

### Verification
- `[agent]` Une tentative de mise en ligne avec migration destructrice est refusée.
- `[agent]` Le refus est tracé dans le journal du projet.
- `[bloquant]` La démonstration est enregistrée, non accélérée, et publiée.

---

## Phase 3 — Le serveur MCP et le plugin

### Objective
Piloter ses projets depuis Claude et depuis Codex, avec exactement les mêmes droits que dans la
console.

### Scope
- Serveur MCP distant, son propre serveur d'autorisation OAuth avec enregistrement dynamique de
  client (code repris de KYA-Platform, service FastAPI).
- Outils annotés lecture seule ou destructif — condition d'entrée au répertoire de connecteurs.
- Plugin léger : connexion et points d'entrée ; le savoir-faire reste servi par le serveur (D-006).

### Deliverables
- Serveur MCP, plugin Claude, politique de confidentialité publiée.

### Dependencies
- Phases 1 et 2 fermées.

### Verification
- `[agent]` Une même action donne le même résultat depuis la console, depuis Claude et depuis Codex.
- `[agent]` Aucun chemin réservé à un agent (D-005).
- `[bloquant]` Soumission au répertoire de connecteurs décidée par un humain.

---

## Phase 4 — Le runtime de développement

### Objective
Écrire depuis son agent et voir l'écran changer en quelques secondes, sans poste local.

### Scope
- Conteneur par projet issu de Fluxio, écriture directe par le serveur, sauvegarde Git par lots.
- URL de dev protégée par authentification, veille et réveil à la première requête.
- Remontée des erreurs de compilation et du navigateur vers l'agent.

### Deliverables
- Agent de synchronisation, orchestrateur de runtime, proxy avec réveil.

### Dependencies
- Phase 3 fermée.

### Verification
- `[agent]` Temps entre l'écriture et l'écran mesuré sur un projet réel, et publié tel quel.
- `[agent]` Le runtime ne pointe jamais la base de production.
- `[bloquant]` Quotas et plafond de dépense arrêtés avant toute ouverture à un tiers.

---

## Phase 5 — Les rôles, l'invité et la sortie

### Objective
Une deuxième personne travaille sur un projet avec ses droits, et n'importe qui peut partir en
cinq minutes.

### Scope
- Rôles par organisation et par projet, invité limité à un projet.
- Arrêt d'urgence et périmètre d'action de l'agent.
- Export complet et détection de dérive entre l'état affiché et l'état réel.

### Deliverables
- Modèle de droits appliqué, écran d'invitation, fonction de sortie, réconciliation.

### Dependencies
- Phase 4 fermée.

### Verification
- `[agent]` Un invité ne voit qu'un projet ; une action interdite est refusée par la base.
- `[agent]` La sortie produit un projet qui tourne sans Pono — test rejoué périodiquement.
- `[bloquant]` Validation par la deuxième personne, en usage réel.

---

## La boucle, après chaque phase

Livrer → observer l'usage réel → mesurer l'indicateur unique → comprendre l'écart → corriger le
produit, le principe ou l'exécution.

**L'indicateur unique :** le temps entre « je veux ce projet » et « je vois mon premier lien qui
marche ». Une phase sans mesure n'est pas terminée, elle est seulement écrite.

## Backlog — plus tard, ou jamais

Marketplace de canevas ouvert · application mobile · édition à plusieurs en temps réel ·
facturation à l'usage fine · pilotage d'autres types de projets que le web.
