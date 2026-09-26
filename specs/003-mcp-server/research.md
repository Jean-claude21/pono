# Research — 003-mcp-server

Décisions techniques de la phase 3. Référence de code : KYA-Platform
(`G:/Code/kya/digitalisation/kya-platform`, lu sans modification), dont le serveur MCP et le
courtier OAuth sont en production et acceptés par Claude (`docs/VERITE_ET_PREUVES.md`).

## R-01 — Le serveur d'outils : SDK MCP officiel, Streamable HTTP sans état

- **Decision** : bibliothèque `mcp` (SDK Python officiel, série 2, comme KYA-Platform 2.1.1) ;
  `MCPServer` servi en Streamable HTTP, **sans état et en réponses JSON**
  (`stateless_http=True`, `json_response=True`), monté dans l'application FastAPI existante sous
  `/mcp`, avec une route canonique `/mcp` sans redirection (repris de `CanonicalMcpEndpoint`).
  Protection contre le rebinding DNS : hôtes et origines autorisés tirés de `PONO_PUBLIC_URL` et de
  l'hôte interne du service.
- **Rationale** : sans état, chaque requête porte son jeton ; aucune session serveur à garder, et le
  relais de la console n'a pas à maintenir de flux long. Même pile que le service (D-010).
- **Alternatives considered** : SSE à état (rejeté : sessions à maintenir derrière un relais) ;
  serveur MCP séparé en TypeScript (rejeté : deuxième pile pour la même logique).

## R-02 — Le serveur d'autorisation : le courtier OAuth 2.1 de KYA-Platform, adapté à la RLS de Pono

- **Decision** : porter `OAuthBroker` (`infrastructure/database/oauth_broker.py` de KYA) qui
  implémente le fournisseur d'autorisation du SDK : enregistrement dynamique de client (RFC 7591),
  autorisation avec PKCE, échange de code, renouvellement avec rotation, révocation ; routes du SDK
  (`/register`, `/authorize`, `/token`, `/revoke`, `/.well-known/oauth-authorization-server`)
  montées à la racine du service, métadonnées de ressource protégée sous
  `/.well-known/oauth-protected-resource/mcp`. Jetons opaques, **seule leur empreinte SHA-256 est
  stockée** ; secret client chiffré (Fernet, la clé de chiffrement existante). Durées : accès
  1 heure, renouvellement 30 jours avec rotation, demande de consentement 10 minutes, code
  5 minutes.
- **Adaptation à Pono** : KYA lit ses tables par l'ORM, sans RLS. Chez Pono, les étapes faites avant
  que quiconque soit connu (enregistrement, autorisation, échange de code, lecture d'un jeton)
  passent par des fonctions `SECURITY DEFINER` qui ne rendent que ce qu'il faut, comme la session
  de la phase 1 (`pono_resolve_session`) ; les accordés, eux, sont écrits et lus sous RLS avec
  l'organisation de la personne.
- **Rationale** : FR-002 à FR-005, SC-005 ; code éprouvé, accepté par Claude.
- **Alternatives considered** : fournisseur d'identité externe (rejeté : un fournisseur de plus,
  et la connexion Pono passe déjà par le fournisseur de code).

## R-03 — Le consentement : dans la console, avec la session de la personne

- **Decision** : `/authorize` redirige vers `https://<console>/oauth/consent?request=<poignée>`. La
  page (route de la console) exige la session habituelle (sinon « Se connecter », puis retour sur la
  même poignée), montre le client, l'étendue et l'organisation, et laisse choisir « lecture seule »
  (`pono:read`) ou « lecture et actions » (`pono:read pono:act`). Elle appelle
  `GET /api/v1/oauth/consent` et `POST /api/v1/oauth/consent/{approve|deny}` qui rendent l'adresse
  de retour du client.
- **Rationale** : FR-002, FR-003 ; le consentement est un geste humain dans la console (D-005).

## R-04 — Les outils : les mêmes cas d'usage que la console, les mêmes réponses

- **Decision** : chaque outil appelle **la même fonction applicative** que la route de la console et
  rend **le même document JSON** (mêmes schémas pydantic) ; une erreur de la console devient une
  erreur d'outil portant **le même code stable**. Outils :
  - lecture (`readOnlyHint`) : `list_projects`, `get_project`, `list_releases`, `read_journal`,
    `list_repositories` ;
  - action (`destructiveHint`, étendue `pono:act`) : `import_project`, `refresh_project`,
    `evaluate_release`, `protect_production`, `request_rollback`.
  Aucun outil ne valide une mise en ligne ; les instructions du serveur disent que la validation se
  fait dans la console, et `get_project` rend l'adresse de la console du projet.
- **Rationale** : FR-006 à FR-010, SC-001, SC-002. La parité est garantie par construction, puis
  vérifiée par un test qui compare, outil par outil, la réponse de l'outil à celle de la route.

## R-05 — Le retour arrière demandé par un agent (clarification FR-011)

- **Decision** : `request_rollback` crée une **demande de retour arrière** (table
  `rollback_requests`), sans toucher l'hébergeur. La console l'affiche sur le projet et dans le
  bandeau de verdict (`rollback.requested`) ; « Confirmer » exécute le retour arrière de la phase 2
  (même code), « Écarter » la clôt. Une demande non traitée expire au bout de 24 heures (tâche du
  worker). Chaque étape est journalisée.
- **Rationale** : ce qui touche la production reste un geste humain (principe IV, clarification).

## R-06 — L'auteur des actions : personne ou agent, au journal

- **Decision** : les cas d'usage reçoivent un **auteur** : personne (login) ou agent (nom du client,
  et la personne qui a donné l'accès dans le détail). Les actions sans trace en phase 2 (import,
  relevé demandé, réévaluation demandée) sont désormais journalisées aussi quand elles viennent de
  la console, pour que les deux chemins laissent la même trace.
- **Rationale** : FR-012 ; parité console/agent jusqu'au journal.

## R-07 — Le relais de la console

- **Decision** : la console relaie vers le service, comme `/api/*` : `/mcp`, `/register`,
  `/authorize`, `/token`, `/revoke`, `/.well-known/oauth-authorization-server` et
  `/.well-known/oauth-protected-resource/mcp`. L'émetteur et la ressource sont l'adresse publique
  (`PONO_PUBLIC_URL`). Le relais transmet l'hôte public dans `X-Forwarded-Host` ; le service
  l'accepte pour la protection contre le rebinding.
- **Rationale** : FR-001 (adresse de la console), un seul domaine, aucun service exposé de plus.

## R-08 — Le savoir-faire servi par le serveur (D-006)

- **Decision** : instructions et descriptions d'outils écrites dans le service, en anglais (aucun
  client ne transmet de langue à l'initialisation ; FR-013 le prévoit). Version du serveur annoncée
  (`3.0.0`) ; la négociation de version du protocole est celle du SDK (version courante et
  précédente acceptées) ; un client trop ancien reçoit l'erreur standard du protocole.
- **Rationale** : FR-013, FR-014 ; aucune règle métier dans le plugin.

## R-09 — Le plugin et Codex

- **Decision** : un plugin Claude Code dans `plugins/pono/` (`.claude-plugin/plugin.json`,
  `.mcp.json` qui pointe vers l'adresse publique `/mcp` en HTTP, deux commandes d'entrée :
  « état de mes projets » et « pourquoi cette mise en ligne est refusée »), et un catalogue
  `.claude-plugin/marketplace.json` à la racine du dépôt. Dans l'application Claude, l'adresse
  s'ajoute comme connecteur personnalisé. Codex : `codex mcp add pono --url <adresse>/mcp` puis
  `codex mcp login pono`. Aucune règle métier dans le plugin.
- **Rationale** : FR-015, D-006.

## R-10 — La politique de confidentialité

- **Decision** : page publique de la console `/privacy`, en français et en anglais (catalogues), qui
  ne décrit que ce qui est vrai aux phases 1 à 3 : identité du fournisseur de code (login, adresse),
  langue, conversation d'alerte, connexions (clés chiffrées, usages tracés), état des projets,
  journal, accès des agents ; hébergement en France (serveur de l'auteur) et base à Francfort ;
  aucune revente, aucun entraînement de modèle ; retrait sur demande. Chaque affirmation se rattache
  à une ligne du registre de vérité.
- **Rationale** : FR-016, SC-006, constitution VII.
