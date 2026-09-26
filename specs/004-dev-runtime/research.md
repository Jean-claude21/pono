# Research — 004-dev-runtime

Chaque décision part de ce que Fluxio a mesuré sur un vrai projet
(`projects_labs/Fluxio/skills/fluxio-mcp/references/runtime-dev.md`) et de l'API publique de Coolify
(`openapi.json` de la branche `v4.x`, lue le 2026-09-26).

## R-01 — Le runtime : le conteneur de Fluxio, plus un portier

- **Decision** : une application Coolify par projet, `build_pack: dockerfile`, construite depuis la
  branche de développement avec `.pono/runtime/Dockerfile` (Node 22, pnpm épinglé, git et
  openssh-client, dépendances installées à la construction). Le processus principal est
  `.pono/runtime/gate.mjs`, le portier : il écoute le port 3000 et lance Vite sur `127.0.0.1:5173`
  par `.pono/runtime/dev.mjs`, qui appelle `createServer` de Vite avec `allowedHosts: true` et le HMR
  sur `wss:443` (les deux pièges de Fluxio), sans toucher `vite.config` du projet.
- **Rationale** : chemin éprouvé (Vite prêt en ~1,3 s, HMR sans reconstruction). Le portier regroupe
  tout ce qui doit vivre à côté de Vite : accès, écriture, suivi de branche, erreurs, veille.
- **Alternatives** : image générique publiée par Pono (installation des dépendances à chaque réveil,
  lente) ; nixpacks (pnpm 9 imposé, piège connu) ; proxy chez Pono (ne peut ni réveiller ni écrire).

## R-02 — Créer le runtime chez l'hébergeur

- **Decision** : `POST /security/keys` (clé privée ed25519 générée par Pono, jamais gardée par Pono),
  `POST /applications/private-deploy-key` (dépôt en SSH, branche de dev, `dockerfile_location`
  `/.pono/runtime/Dockerfile`, `ports_exposes: 3000`, `limits_memory: 1g`, domaine explicite,
  déploiement automatique coupé), `POST /applications/{uuid}/envs` pour les variables,
  `POST /applications/{uuid}/start`, `…/stop`, `DELETE /applications/{uuid}` ; `GET /applications/{uuid}`
  pour l'état. La clé publique devient une clé de déploiement **en lecture seule** du dépôt, posée par
  l'app Pono (droit d'administration déjà accordé, D-016). Serveur : celui de l'application de
  développement déjà connue du projet, sinon le seul serveur du compte, sinon refus
  `runtime.server_ambiguous`. Domaine : `https://<nom>-dev-<6 car.>.<domaine joker du serveur>`, ou
  `<ip>.sslip.io` sans domaine joker (comme la console de Pono).
- **Rationale** : tout existe dans l'API publique ; une clé par runtime se révoque sans rien toucher
  d'autre.
- **Alternatives** : app GitHub de Coolify (à installer à part par la personne) ; dépôt public
  seulement (exclut les dépôts privés).

## R-03 — Jamais la base de production

- **Decision** : la base branchée est la branche `development` du manifeste (`database.branches`) ;
  sans elle, refus `runtime.database_missing` ; si elle est celle de la production, refus
  `runtime.production_database`. À chaque relevé, le service compare l'hôte de base que le portier
  déclare utiliser (`DATABASE_URL`) à l'hôte attendu de développement et à celui de la production :
  s'il est celui de la production ou différent de l'attendu, le runtime est arrêté et passe en échec
  `runtime.production_database`. L'adresse de la base (avec son mot de passe) va de la base à
  l'hébergeur sans être gardée par Pono.
- **Rationale** : SC-003 vérifié par construction **et** par relevé, pas par consigne.

## R-04 — L'adresse fermée : ticket signé, cookie du portier

- **Decision** : sans cookie valide, le portier renvoie vers `/runtime/open` de la console. La console
  (session exigée, sinon connexion avec retour) demande au service un ticket : `base64url(json{r,e,n})`
  signé HMAC-SHA256 avec le jeton du runtime, valable 2 minutes, usage unique. Le portier le vérifie,
  pose son cookie `pono_runtime` (signé, `HttpOnly`, `Secure`, `SameSite=Lax`, 12 h) et redirige
  vers le chemin demandé. Une autre organisation reçoit l'introuvable du service. Les WebSocket du
  HMR exigent le même cookie.
- **Rationale** : aucun appel du portier vers Pono ; un robot ne reçoit qu'une redirection.
- **Alternatives** : authentification HTTP basique de Coolify (mot de passe partagé, pas de session) ;
  proxy par Pono (latence, plus de pièces).

## R-05 — Écrire directement dans le runtime

- **Decision** : le service appelle `PUT /__pono/files` du portier (jeton du runtime en `Bearer`)
  avec le chemin et le contenu (base64) ou une suppression. Le portier revalide le chemin, écrit de
  façon atomique (fichier temporaire, puis renommage), réveille Vite si besoin ; le HMR de Vite fait
  le reste. Le service n'enregistre l'écriture en attente qu'une fois le portier d'accord.
- **Rationale** : c'est l'écriture directe mesurée à 4–5 s par Fluxio, sans le trajet Git de 25 s.

## R-06 — Suivre la branche sans écraser une écriture en attente

- **Decision** : toutes les 5 s, le portier récupère la tête distante R. Pour chaque fichier qui
  diffère entre sa tête locale L et R : si le fichier local vaut celui de L, il prend celui de R ; s'il
  vaut déjà celui de R, rien ; sinon c'est un conflit, gardé et déclaré. Puis `git reset --mixed R`.
  Les commits de Pono reviennent ainsi sans rien bousculer ; une modification poussée d'ailleurs
  arrive à chaud. Un fichier de verrouillage changé réinstalle les dépendances puis relance Vite.
- **Rationale** : Fluxio faisait `reset --hard`, qui écraserait une écriture pas encore sauvegardée.

## R-07 — Les erreurs

- **Decision** : `dev.mjs` observe les messages d'erreur que Vite envoie au navigateur et ses
  erreurs journalisées, et les transmet au portier (IPC) ; une mise à jour réussie efface les erreurs
  de compilation. Le portier injecte dans les pages HTML un petit script qui remonte `error` et
  `unhandledrejection` du navigateur (cookie exigé). Il garde les 50 dernières, dédoublonnées
  (message, fichier, ligne), masque les formes de secrets, et les rend par `GET /__pono/status`.
  Le service les relit à la demande (agent, console) et garde le dernier relevé.
- **Rationale** : aucune base de plus dans le conteneur ; SC-005 par lecture directe.

## R-08 — Veille et réveil

- **Decision** : la veille arrête Vite, pas le conteneur : après 15 minutes sans requête HTTP ni
  écriture, le portier termine Vite ; à la requête suivante d'un membre, il le relance et sert une
  page d'attente qui se recharge seule ; une écriture le relance aussi. Le conteneur arrêté reste le
  geste « Arrêter ».
- **Rationale** : Vite est ce qui pèse (mémoire, surveillance des fichiers) ; le portier seul pèse
  quelques dizaines de mégaoctets. Un conteneur éteint ne pourrait pas répondre pour se réveiller
  sans une pièce de plus chez l'hébergeur (principe I).

## R-09 — Sauvegarder par lots sur la branche de développement

- **Decision** : chaque écriture acceptée est gardée par Pono (table `runtime_writes`) jusqu'à sa
  sauvegarde. Le worker sauvegarde les écritures d'un runtime après 60 s sans nouvelle écriture,
  avant un arrêt, ou sur demande : un commit par auteur, par l'API Git (arbre sur la tête connue,
  commit, avance de la référence **sans forcer**). Si la branche a bougé et touché les mêmes fichiers,
  ces écritures passent en conflit, visibles ; les autres partent. Une nouvelle écriture d'un fichier
  en conflit lève le conflit. Le contenu est effacé une fois sauvegardé. L'adaptateur refuse toute
  écriture hors de la branche de développement nommée, et toujours la branche par défaut.
- **Rationale** : D-019 ; SC-004 même si le conteneur redémarre.

## R-10 — Les limites

- **Decision** : au plus 3 runtimes « démarrés » (en préparation, en démarrage, prêts ou en veille)
  par organisation, refus `runtime.limit_reached` au-delà ; 1 Gio par runtime (limite posée chez
  l'hébergeur ; un dépassement arrête le conteneur, relevé comme `runtime.stopped_by_host`) ; veille
  à 15 min, passée au portier par variable. Fichier écrit : 1 Mio au plus. Chemins refusés : absolus,
  `..`, `.git/`, `.pono/runtime/`, `.env` et `.env.*` (sauf `.env.example`), `node_modules/`.
- **Rationale** : clarification de l'US6 ; appliqué par le service, pas conseillé.
