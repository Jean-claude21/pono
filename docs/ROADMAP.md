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
| **KYA-Platform** | **Le schéma** du courtier OAuth pour connecteurs MCP avec enregistrement dynamique de client, le découpage domaine / application / infrastructure, le modèle de rôles | 3, 6 |
| **vtt-template** | Spec Kit épinglé, la constitution, le registre de skills, les gates scriptées | toutes |

> **Attention, distinction importante.** De KYA-Platform on reprend **la conception**, pas le code :
> elle est en Python, Pono est en TypeScript (voir D-010). Le coût de réécriture est réel, il est
> assumé, et il porte surtout sur le courtier OAuth de la phase 3.

## Complete Product Scope

Le produit est complet quand, pour un utilisateur qui n'a que son agent et ses comptes gratuits :

1. Il connecte ses fournisseurs par autorisation, sans jamais confier de clé permanente.
2. Il importe ou crée un projet, et son état est juste sans qu'il le saisisse.
3. Il voit tous ses projets, leurs environnements, leurs déploiements et leurs quotas au même endroit.
4. Il code depuis son agent, et voit l'écran changer en quelques secondes.
5. Il met en ligne, et le système **refuse** tant qu'un humain n'a pas validé.
6. Il invite quelqu'un, avec des droits qui tiennent.
7. Il peut partir : tout est sur ses comptes, l'export est un geste.

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

## Phase 0 — Le socle visuel et le langage du produit

### Objective
Un système de design éprouvé sur les cas réels du produit — états, quotas, refus — avant d'écrire
le moindre écran définitif.

### Scope
- Les jetons de la **charte validée** : fonds `#282828` et `#242424`, ligne `#494949`, texte
  `#dedede`, accent vert `#1ca18c`, focus orange `#f99d32`, jaune `#e8e748`, café `#875028`.
  Segoe UI, base 14 px, panneau de 262 px, cartes à rayon 5, puces de 43 px.
- Les composants : carte de projet, carte en vedette, pastille d'état, barre de quota, puces
  filtrantes, dialogue de mise en ligne, notification.
- La validation se fait dans `design/` en HTML, CSS et JS, sans framework.

### Deliverables
- `design/index.html`, `design/style.css`, `design/app.js`.
- Les jetons portés ensuite dans le `@theme` de Tailwind, source unique.

### Dependencies
- Le mandat et le positionnement approuvés.

### Verification
- `[agent]` La page est rendue et **regardée** avant d'être proposée : capture à 1440 px, plus les
  états du dialogue. Une maquette non regardée n'est pas livrée.
- `[agent]` Aucune valeur de couleur, de taille ou d'espacement hors de la charte.
- `[bloquant]` La direction visuelle est approuvée par un humain.

---

## Phase 1 — L'atelier qui tient les projets

### Objective
Voir l'état réel de ses propres projets au même endroit, et reprendre l'un d'eux sans rien chercher.

### Scope
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

## Phase 2 — La mise en ligne sous garde-fou

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
  client (schéma repris de KYA-Platform, réécrit en TypeScript).
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
