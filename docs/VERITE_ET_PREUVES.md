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

## Observations

| Observation | Source |
|---|---|
| Une vingtaine de projets personnels vivent dans des comptes et dossiers séparés, sans vue commune | inventaire `projects_labs` |
| Les URL de développement publiques sont sondées par des robots en quelques minutes | journaux Fluxio |
| Le cycle complet commit → push → pull → HMR mesure environ 25 s, dominé par le trajet GitHub | mesures Fluxio |

## Hypothèses — à prouver avant d'en parler

| Hypothèse | Comment on la tranchera |
|---|---|
| Écrire directement dans le conteneur ramène le cycle à 1–2 s | mesure sur un projet réel |
| Voir l'état de tous ses projets fait passer la reprise sous la minute | chronométrage sur les deux premiers utilisateurs |
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
