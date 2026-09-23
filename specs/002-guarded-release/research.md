# Research — 002-guarded-release

Décisions techniques de la phase 2. Chaque décision part d'un fait vérifié le 2026-09-23 sur les
projets réels de l'auteur ou sur la documentation des fournisseurs.

## R-01 — Le blocage : une vérification obligatoire que seul Pono peut rendre favorable

- **Decision** : chaque tentative porte, chez le fournisseur de code, une vérification nommée
  `pono/release` sur le commit de tête de la proposition. La protection de la branche de production
  exige cette vérification **liée à l'identifiant de l'app Pono** : une autre app, un jeton
  personnel ou un agent qui publierait un statut du même nom ne la satisfont pas. La vérification
  reste « en échec » ou « en cours » tant que le verdict n'est pas « validé ».
- **Rationale** : D-004 et constitution IV — le blocage est appliqué par le fournisseur de code, pas
  demandé à l'agent. Lier la vérification à l'app ferme le contournement le plus simple (publier
  soi-même un statut vert).
- **Alternatives considered** : un statut de commit simple (rejeté : n'importe quel détenteur d'un
  accès en écriture peut publier un statut du même nom) ; une relecture obligatoire (rejeté : un
  auteur seul ne peut pas approuver sa propre proposition, et la relecture ne porte pas les
  garde-fous).

## R-02 — Détecter les tentatives : relevé toutes les minutes, sans webhook

- **Decision** : le worker gagne une tâche `releases` toutes les 60 secondes. Pour chaque projet dont
  le manifeste déclare une branche de production, il liste les propositions ouvertes vers cette
  branche, crée ou met à jour la tentative, et évalue les garde-fous pour toute nouvelle version.
  La console peut demander une évaluation immédiate.
- **Rationale** : SC-003 (verdict en moins de 2 minutes après la preview) tient avec une minute de
  cadence. Aucun secret de webhook à gérer, aucun point d'entrée public de plus, même modèle
  d'exécuteur qu'en phase 1 (constitution I).
- **Alternatives considered** : webhooks du fournisseur de code (plus réactifs ; à ajouter si la
  cadence ne suffit plus, derrière le même cas d'usage).

## R-03 — Garde-fou des secrets : motifs sur les lignes ajoutées

- **Decision** : seules les lignes **ajoutées** par le changement sont lues. Motifs : jetons des
  fournisseurs courants (GitHub, bots de messagerie, clés d'accès cloud, clés de paiement en
  production, jetons Slack), blocs de clé privée, adresses de base avec mot de passe
  (`postgres://user:motdepasse@`), et affectations évidentes (`password|secret|token|api_key` suivi
  d'une valeur littérale de 8 caractères ou plus). Un fichier `.env` ajouté (hors `.env.example`,
  `.env.sample`, `.env.template`) échoue d'office. Les fichiers déclarés comme exemples dans le
  manifeste (`release.exampleFiles`) sont exclus. Le détail porte le fichier, la ligne et le type de
  motif, **jamais la valeur**. Un fichier texte trop gros pour être lu fait échouer le garde-fou
  (échec fermé) ; un fichier binaire est ignoré.
- **Rationale** : FR-004, SC-006. Les motifs réutilisent ceux de la rédaction des journaux de la
  phase 1 (`infrastructure/logging.py`), déjà éprouvés.
- **Alternatives considered** : un outil externe d'analyse de secrets (rejeté : dépendance lourde,
  un binaire à embarquer, pour un gain marginal à cette échelle) ; l'entropie seule (rejeté : trop
  de faux positifs sur les empreintes et les identifiants).

## R-04 — Garde-fou des migrations : analyse SQL, échec fermé

- **Decision** : les projets réels écrivent leurs migrations en SQL (`drizzle/*.sql` pour
  lectio-reads et livio, `supabase/migrations/*.sql` pour nettio). Le garde-fou lit les fichiers
  `.sql` ajoutés ou modifiés sous les dossiers de migrations : ceux que déclare le manifeste
  (`release.migrations`), sinon les conventions `drizzle/`, `supabase/migrations/`,
  `prisma/migrations/`, `migrations/`, `db/migrations/`. Chaque instruction est analysée par
  `sqlglot` (dialecte Postgres, D-009, déjà prévu par D-010). Sont refusés : `DROP TABLE`,
  `DROP COLUMN`, tout renommage de table ou de colonne, `ALTER COLUMN … TYPE`, `TRUNCATE`, `DELETE`
  sans `WHERE`. Le fichier est découpé en instructions par Pono (chaînes, commentaires et corps
  `$$ … $$` respectés) ; chaque instruction est analysée par `sqlglot`. **Constat du 2026-09-23** :
  `sqlglot` ne lit ni `CREATE POLICY`, ni `ENABLE ROW LEVEL SECURITY`, ni les fonctions PL/pgSQL
  d'une vraie migration de nettio. Une instruction qu'il ne lit pas est donc examinée **en texte**,
  chaînes et corps de fonction compris, pour les mêmes opérations destructrices (y compris un
  `EXECUTE 'DROP TABLE …'`). Un fichier de migration écrit dans un langage de code (`.py`, `.ts`,
  `.js`…) ou illisible fait échouer le garde-fou (on refuse ce qu'on ne comprend pas). Une
  migration déjà présente sur la branche de production et modifiée par le changement échoue aussi :
  réécrire l'histoire des migrations est destructeur par nature.
- **Destruction déclarée (clarification FR-008)** : le manifeste peut porter
  `release.declaredDestructions: [{ "file": "...", "operation": "drop_column" }]`. Une opération
  destructrice est acceptée seulement si elle y figure **et** si le changement ne contient que ce
  fichier de migration et la modification du manifeste. Le journal l'enregistre comme destruction
  déclarée.
- **Rationale** : FR-005, FR-008, SC-001 ; la constitution demande qu'une migration destructrice soit
  « nommée en clair avant d'être proposée ».
- **Alternatives considered** : rejouer les migrations sur une base jetable et comparer les schémas
  (plus exact, mais demande une base par évaluation ; à garder pour plus tard) ; accepter les
  migrations d'un ORM en Python (rejeté pour la phase : aucun projet réel n'en a).

## R-05 — Garde-fou de la preview : la preview du commit de tête doit répondre

- **Decision** : le port d'hébergement gagne `find_preview(ref, change_number, head_sha)`, qui rend
  l'état de la preview de cette proposition : en construction, prête (avec son adresse), en échec,
  absente. Netlify : le déploiement de contexte `deploy-preview` dont `review_id` est le numéro de
  la proposition et `commit_ref` le commit de tête. Coolify : le déploiement dont `pull_request_id`
  est ce numéro et dont le commit est le commit de tête ; l'adresse suit le modèle d'adresse de
  preview de l'application. Une preview prête est vérifiée comme un lien de la phase 1 (deux essais
  de 10 secondes). Absente : échec, avec la marche à suivre pour activer les previews
  (clarification FR-006). En construction depuis plus de 30 minutes : échec.
- **Rationale** : FR-006 ; exiger le commit de tête empêche de valider une preview d'une version
  antérieure (US1 scénario 4).
- **Alternatives considered** : se contenter de la dernière preview de la branche (rejeté : peut
  être celle d'un commit précédent).

## R-06 — La validation : dans la console, sur une version exacte

- **Decision** : `POST /projects/{id}/releases/{releaseId}/approval` avec le commit de tête que la
  personne a vu. Le service refuse si le commit a changé (`release.version_changed`) ou si un
  garde-fou n'est pas réussi (`release.not_ready`). Sinon il enregistre la validation, passe la
  vérification `pono/release` à « réussie » sur ce commit et écrit le journal. Une nouvelle version
  crée une nouvelle vérification sur le nouveau commit, en attente : la validation précédente ne la
  couvre pas. La route exige la session de personne (cookie `HttpOnly`, `SameSite=Lax`) ; aucune
  clé d'API, aucun jeton d'agent n'existe en phase 2 (FR-011).
- **Rationale** : FR-009 à FR-012, US2.

## R-07 — La protection : lue à chaque relevé, posée par Pono sur un clic

- **Decision** : le port du fournisseur de code gagne `read_protection(installation, repo, branch)`
  et `apply_protection(installation, repo, branch)`. Protégé signifie : proposition obligatoire (sans
  nombre minimal d'approbations, la validation humaine est dans Pono), vérification `pono/release`
  obligatoire et liée à l'app Pono, règles appliquées aux administrateurs, ni envoi forcé ni
  suppression de la branche. Une réponse « offre insuffisante » du fournisseur donne l'état
  **impossible sur cette offre**. `apply_protection` est la seule écriture de Pono hors de ses
  branches de proposition (clarification FR-015) ; elle passe par un garde dédié qui n'autorise que
  la règle de protection de la branche de production déclarée dans le manifeste. L'app demande la
  permission de dépôt « Administration : écriture » et « Checks : écriture ».
- **Rationale** : FR-013 à FR-015, US3. Fait vérifié : lectio-reads et fluxio-runtime-test sont
  publics, nettio est privé ; aucun n'est protégé aujourd'hui.

## R-08 — Le retour arrière : une API par hébergeur, chaque usage tracé

- **Decision** : le port d'hébergement gagne `rollback(ref, target)`, où `target` est le dernier
  déploiement de production réussi avant l'actuel. Netlify : restaurer ce déploiement
  (`POST /sites/{site}/deploys/{deploy}/restore`). Coolify 4.3.23 (instance de l'auteur, vérifié) :
  `POST /applications/{uuid}/rollback` avec le commit de l'image, pris dans
  `GET /applications/{uuid}/rollback-images`. Le résultat est vérifié par le relevé suivant de la
  production (lien qui répond, déploiement réussi) et affiché tel quel. Chaque appel est tracé comme
  usage de clé (FR-024).
- **Rationale** : FR-016, FR-017, SC-005. C'est la seule écriture des adaptateurs d'hébergement ;
  elle amende D-014 (« Coolify en lecture seule ») et est consignée en D-016.
- **Alternatives considered** : ré-épingler un commit dans la configuration Coolify puis redéployer
  (rejeté : laisse l'application épinglée, à défaire à la main).

## R-09 — Le journal : ajout seul, garanti par la base

- **Decision** : table `project_events`, RLS forcée dans sa migration créatrice ; `pono_app` n'a que
  `SELECT` et `INSERT` ; un déclencheur refuse `UPDATE` et `DELETE` pour tout rôle, y compris le
  propriétaire. Chaque entrée : heure, type d'événement (code stable), auteur (personne, agent
  désigné par le fournisseur de code, ou Pono), commit concerné, charge utile en codes seulement.
- **Rationale** : FR-018 à FR-020, SC-007, constitution VI.

## R-10 — Le contrat : un document par phase, vérifiés ensemble

- **Decision** : `contracts/openapi.yaml` de cette phase ne porte que les routes et schémas ajoutés
  ou modifiés ; le vérificateur de contrat de la phase 1 charge les deux documents et les fusionne.
  Le SDK reste généré depuis l'OpenAPI du service.
- **Rationale** : garder la phase 1 intacte et lisible, sans dupliquer son contrat.

## R-11 — Mise en production sans validation

- **Decision** : quand une proposition vers la branche de production est fusionnée alors que son
  commit de tête n'a pas de validation (protection retirée entre-temps, ou fusion par un
  administrateur si la protection ne s'applique pas à eux), le journal enregistre « mise en
  production sans validation » et le projet passe en verdict d'alerte jusqu'à la tentative
  suivante validée.
- **Rationale** : cas limite de la spec ; le mensonge par omission est pire que l'alerte.

Sources vérifiées le 2026-09-23 : API Coolify (`openapi.json` de `coollabsio/coolify`, branche
`v4.x`, et l'instance de l'auteur en 4.3.23) ; arborescences de lectio-reads, nettio, livio et firmo
chez le fournisseur de code.
