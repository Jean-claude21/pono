# Registre de vérité et preuves

> Toute affirmation publique — page web, page de vente, argumentaire, message dans un agent — doit
> pouvoir se rattacher à une ligne de ce fichier. **La page publique ne dit jamais plus que lui.**

Classement : `fait vérifié` · `observation` · `témoignage` · `hypothèse` · `projection` ·
`promesse contractuelle`.

## Faits vérifiés

| Fait | Preuve | Date |
|---|---|---|
| Un runtime de développement persistant applique une modification sans reconstruire l'image | Fluxio, phase 1, projet réel | 2026-09 |
| Le chemin complet jusqu'à la production fonctionne : preview, promotion, production en ligne | Fluxio, phase 2 | 2026-09 |
| Le verrou de production tient : fusion refusée, auto-approbation refusée, `--admin` refusé | Fluxio, phase 4, répétition complète | 2026-09 |
| Les migrations destructrices sont détectables avant la mise en ligne | Fluxio, `plan.mjs` | 2026-09 |
| Un serveur MCP peut porter son propre serveur d'autorisation OAuth avec enregistrement dynamique de client, accepté par Claude | KYA-Platform, en production | 2026-09 |
| Offre gratuite Neon : 100 projets, 10 branches par projet, 0,5 Go et 100 CU-heures par projet | documentation Neon | 2026-09-22 |
| Offre gratuite Netlify : 300 crédits par mois, soit ~15 Go de trafic **ou ~20 déploiements**, puis mise en pause des sites | documentation Netlify et analyses publiques | 2026-09-22 |
| Pono importe cinq projets réels — lectio-reads, fluxio-runtime-test, livio, firmo, nettio — sans aucun champ saisi, et l'état affiché correspond à celui constaté à la main chez GitHub, Netlify, Coolify et Neon (SC-001) | import sur le service lancé en local contre les vrais fournisseurs ; vérification manuelle de chaque lien et de chaque déploiement | 2026-09-23 |
| Un import dure entre 21 et 46 s (lectio-reads 45,5 s ; fluxio-runtime-test 42,6 s ; livio 21,3 s ; firmo 42,1 s ; nettio 43,0 s), sous l'objectif de 2 min (SC-003) | chronométrage de l'appel d'import, service local à Lomé, fournisseurs réels | 2026-09-23 |
| Une adresse qui ne répond pas est signalée comme telle : les applications Coolify sous `vttlife.com`, domaine expiré, sont marquées « ne répond pas » | relevé réel, confirmé par `curl` (aucune réponse en 10 s) | 2026-09-23 |
| Deux organisations restent étanches au niveau des données : 404 identique pour une ressource étrangère ou absente, aucune ligne étrangère en SQL direct sur toutes les tables (SC-006) | `apps/api/tests/security/test_isolation.py`, en CI | 2026-09-23 |
| Offre gratuite Neon : 5 Go de transfert par projet et par mois ; la limite de stockage de l'offre est lisible par l'API, pas celles de calcul et de transfert | neon.com/pricing ; exploration de l'API (research R-08) | 2026-09-23 |
| La console de Pono est servie en HTTPS sur l'adresse du serveur, sans domaine acheté : certificat Let's Encrypt pour `pono-staging.13.140.178.49.sslip.io`, `http` redirigé, cookies `Secure` (T085) | `openssl s_client` et navigateur, contexte sécurisé | 2026-09-23 |
| La liaison Telegram marche de bout en bout en production : lien à usage unique, « Démarrer », confirmation, message reçu par l'auteur ; le jeton du bot apparaît `[redacted]` dans les journaux (T094, partiel) | journaux de `pono-api` (`getMe`, `getUpdates`, `sendMessage` 200, `/me/chat-link/confirm` 204) ; base : conversation reliée | 2026-09-23 |
| La connexion GitHub lit l'adresse privée de la personne une fois la permission « Email addresses » accordée (T081) | base de production : adresse connue après reconnexion | 2026-09-23 |
| Une proposition contenant une migration destructrice est refusée par Pono et sa fusion est bloquée par le fournisseur de code, sur un projet réel (002 SC-001) : lectio-reads#3 ajoute `ALTER TABLE "books" DROP COLUMN "notes"` ; verdict « refusé », garde-fou des migrations en échec sur ce fichier ; vérification `pono/release` publiée en échec par l'app `pono-atelier` ; après « Protéger la production » (geste de l'auteur, journalisé), `main` exige cette vérification liée à l'app (id 5040478), y compris pour les administrateurs, et l'état de fusion est `blocked` ; une tentative de fusion est refusée par GitHub (« the base branch policy prohibits the merge ») | API GitHub (`check-runs`, `branches/main/protection`, `pulls/3`) ; journal du projet dans la console | 2026-09-23 |
| Pono évalue les vraies propositions ouvertes et publie sa vérification chez le fournisseur de code : deux propositions de fluxio-runtime-test passent les trois garde-fous (preview Netlify du commit de tête vérifiée) et attendent la validation d'une personne | API GitHub (`check-runs`, app `pono-atelier`) ; base de production | 2026-09-23 |
| Un agent n'obtient un accès qu'après le consentement d'une personne connectée et autorisée, donné dans la console ; il choisit lecture seule ou lecture et actions ; l'accès coupé dans la console refuse l'appel suivant (003 FR-002 à FR-005) | `apps/api/tests/integration/test_agent_oauth.py`, en CI | 2026-09-26 |
| Les jetons des agents, leurs codes et les poignées de consentement ne sont gardés que sous forme d'empreinte ; les sessions aussi (`sessions.token_hash`) (003 SC-005) | `apps/api/tests/integration/test_agent_oauth.py`, `apps/api/tests/security/test_agent_isolation.py`, en CI ; migration `0001_identity` | 2026-09-26 |
| Les accès des agents restent dans leur organisation : une autre organisation ne voit ni ne coupe un accès, et aucune ligne étrangère en SQL direct (003 FR-017) | `apps/api/tests/security/test_agent_isolation.py`, en CI | 2026-09-26 |
| Aucun outil pour agent ne valide une mise en ligne ni n'exécute un retour arrière ; chaque action d'un agent est inscrite au journal avec son nom et la personne qui a donné l'accès (003 SC-002, FR-012) | `apps/api/tests/integration/test_agent_tools.py`, en CI | 2026-09-26 |
| Les clés de fournisseurs sont gardées chiffrées — aucun octet stocké ne contient une clé en clair — et effacées quand la connexion est coupée | `apps/api/tests/integration/test_connections.py`, en CI | 2026-09-26 |
| La valeur d'un secret trouvé dans un changement n'est jamais conservée : le verdict le signale sans le garder | `apps/api/tests/integration/test_releases.py` (`test_a_secret_is_refused_without_its_value_ever_being_kept`), en CI | 2026-09-26 |
| Le journal de preuves ne se réécrit pas, ni par le service ni par le propriétaire de la base (002 SC-007) | `apps/api/tests/security/test_journal.py`, en CI | 2026-09-26 |
| La base de production de Pono est chez Neon, région Francfort (Union européenne) | console Neon, projet `lively-salad-56581629` (D-015) | 2026-09-26 |
| Claude Code se relie au serveur d'outils de Pono en production par le parcours complet — enregistrement du client, consentement de l'auteur dans la console, jeton — et lit l'atelier réel : trois projets, leurs états, liens, quotas et les cinq verdicts, puis les journaux de preuves de fluxio-runtime-test et lectio-reads (003 US1, US2) | appels `list_projects` et `read_journal` depuis une session Claude Code de l'auteur ; métadonnées publiques `/.well-known/oauth-*` | 2026-09-26 |
| Un accès en lecture seule ne peut pas agir, en production : depuis l'application Claude, « rafraîchis lectio-reads » est refusé par Pono avec `agent.scope_insufficient`, et l'agent l'explique à la personne (003 FR-009) | conversation de l'auteur dans l'application Claude | 2026-09-26 |
| Un agent agit avec les droits de la console et le journal le nomme, en production : depuis l'application Claude avec l'accès « Lecture et actions », « rafraîchis lectio-reads » relance le relevé (lu à 16:34:55 UTC) et le journal inscrit `project.refresh_requested` par « Claude » (agent), accès donné par Jean-claude21 (003 US3, FR-012) | journal de lectio-reads, lu depuis l'agent ; réponse de l'agent | 2026-09-26 |
| L'application Claude range les outils de Pono selon leurs annotations : les 5 outils de lecture en autorisation automatique, les 5 outils d'action dans « Outils d'écriture/suppression », avec approbation demandée à chaque appel (003 US3, scénario 4) | réglages du connecteur Pono dans l'application Claude de l'auteur | 2026-09-26 |
| L'auteur valide une vraie mise en ligne dans la console : proposition n° 3 de fluxio-runtime-test, garde-fous passés, journal `release.approved` par Jean-claude21 (002 T038 étape 3) | journal du projet, lu depuis l'agent | 2026-09-23 |

## Observations

| Observation | Source |
|---|---|
| Une vingtaine de projets personnels vivent dans des comptes et dossiers séparés, sans vue commune | inventaire `projects_labs` |
| Les URL de développement publiques sont sondées par des robots en quelques minutes | journaux Fluxio |
| Le cycle complet commit → push → pull → HMR mesure environ 25 s, dominé par le trajet GitHub | mesures Fluxio |
| Une pull request de manifeste ouverte par Pono déclenche une preview Netlify sur les sites qui construisent les pull requests : elle consomme de l'offre du compte | fluxio-runtime-test, preview n° 3 |
| Un compte Netlify ancien reste sur l'offre à bande passante (100 Go par mois), pas sur les crédits | compte de l'auteur, API `/accounts/{slug}/bandwidth` |

## Hypothèses — à prouver avant d'en parler

| Hypothèse | Comment on la tranchera |
|---|---|
| Écrire directement dans le conteneur ramène le cycle à 1–2 s | mesure sur un projet réel |
| Voir l'état de tous ses projets fait passer la reprise sous la minute (SC-002) | chronométrage sur les deux premiers utilisateurs, depuis la console en ligne — **pas encore fait** |
| Quelqu'un d'extérieur paiera pour « ça tient » | premières conversations de vente |

## Interdit d'affirmer aujourd'hui

- « Compatible avec n'importe quel fournisseur » — faux tant qu'un seul chemin existe.
- « Plus rapide que Replit » — non mesuré.
- « Vos secrets sont en sécurité » — à prouver, pas à proclamer.
- Tout chiffre de performance non mesuré sur un projet réel.
- Tout témoignage, logo client ou nombre d'utilisateurs qui n'existe pas.

## Promesses contractuelles

| Promesse | Ce qui la garantit |
|---|---|
| Le code reste sur le dépôt de l'utilisateur | aucune copie propriétaire, export permanent |
| Aucun crédit d'intelligence artificielle facturé | modèle de prix fixe |
| Partir reste possible à tout moment | fonction de sortie, testée périodiquement |
| Aucune donnée n'est vendue ni cédée | modèle de prix fixe ; aucun destinataire hors des fournisseurs nommés dans la politique de confidentialité |
| Tout ce que Pono garde d'une organisation est supprimé sur demande écrite | suppression faite à la main par l'auteur, en attendant une fonction de sortie |
