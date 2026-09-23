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
