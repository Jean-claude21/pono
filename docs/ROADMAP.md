# Roadmap

> **La tranche en cours est détaillée. Les suivantes tiennent en une ligne.**
> C'est volontaire : on n'écrit le détail d'une tranche qu'au moment de la prendre. Planifier la V3
> avant d'avoir livré la V1 est une ligne rouge (`docs/PRINCIPES.md`, principe 9).

## L'indicateur unique

> **Le temps entre « je veux ce projet » et « je vois mon premier lien qui marche ».**

Tout le reste — vitesse du hot reload, nombre de garde-fous, richesse des canevas — n'est qu'un
moyen de le réduire. Il se mesure dès la première session, y compris les nôtres.

---

## Tranche 0 — Le socle visuel · *en cours*

**La seule chose à livrer :** des jetons de design et six composants, partagés par la landing et la
console.

- Jetons en CSS (couleur, typographie, espacement, rayon, élévation), consommés par Tailwind 4.
- Les six composants dont la tranche 1 a besoin : carte de projet, badge d'état, barre de quota,
  liste, bouton, boîte de confirmation.
- Le mode sombre, dès le départ, pas après coup.
- La landing re-basculée sur les jetons.

**Preuve de fin :** la landing et un écran de console rendus avec les mêmes jetons, en clair et en
sombre.

**Gate humaine :** la direction visuelle et le symbole sont approuvés avant toute production
d'actifs de marque.

---

## Tranche 1 — L'atelier qui tient les projets

**La seule chose à livrer :** voir l'état réel de ses propres projets au même endroit.

### Le contenu

1. **Le modèle de domaine** : organisation, membre, rôle, projet, environnement, connexion,
   déploiement. Objet ancre : le **projet**. Frontière dure : l'**organisation**.
   *Prérequis dur : le modèle avant la première migration, le RLS dans la migration créatrice.*
2. **La connexion d'un fournisseur de code**, par autorisation et non par clé permanente.
3. **L'import d'un projet existant** depuis un dépôt, avec son manifeste.
4. **L'état réel** : branches, dernier déploiement, environnements, liens qui marchent.
5. **Les quotas** du fournisseur d'hébergement et de la base, avec alerte avant la pause.
6. **L'écran d'atelier** : la liste des projets et leur état.

### Preuve de fin

Les projets réels de l'atelier — au moins cinq — importés et affichés avec un état juste.
**Temps de reprise mesuré sous la minute.**

### Ce qui reste dehors

Le runtime, le serveur MCP, le plugin, les canevas, l'inscription publique.

---

## Les tranches suivantes — une ligne chacune, sans détail

| # | Tranche | La seule chose à livrer |
|---|---|---|
| 2 | Le serveur MCP et le plugin | piloter ses projets depuis Claude, et depuis la console |
| 3 | Le runtime de développement | écrire, et voir l'écran changer en quelques secondes |
| 4 | Les garde-fous de mise en ligne | la production refusée sans validation humaine, mécaniquement |
| 5 | Les rôles et l'invité | une deuxième personne sur un projet, avec ses droits |
| 6 | La sortie et la dérive | partir en cinq minutes ; voir quand l'état diverge |

Elles ne seront détaillées qu'au moment de les prendre, après avoir mesuré la précédente.

---

## Backlog — plus tard, ou jamais

Canevas métier et marketplace · infrastructure fournie · autres fournisseurs de base et
d'hébergement · analyses de l'application depuis l'agent · SSO d'entreprise · application mobile ·
édition à plusieurs en temps réel · facturation à l'usage fine.

Chacun est défendable un jour. Aucun n'aide les deux premiers utilisateurs cette semaine.

---

## La boucle, après chaque tranche

Livrer → observer l'usage réel → mesurer l'indicateur → comprendre l'écart → corriger le produit,
le principe ou l'exécution. Une tranche sans mesure n'est pas terminée, elle est seulement écrite.
