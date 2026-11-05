# Données des bilans FFA

## Principe

```
data/reference/   référence figée : meilleur temps par athlète et par distance, saisons 2024 à 2026
       +
exports bruts     saison en cours (2027), recollectée à chaque mise à jour
       ↓  tools/build_db.py
base complète     athletes, recherche, rangs, ligues/départements, filtres, totaux
       ↓
nouvelle base D1  l'API bascule dessus ; l'ancienne reste disponible pour revenir en arrière
```

On ne recollecte **jamais** l'historique : la référence contient déjà le meilleur temps 2024–2026 de chaque athlète. À chaque mise à jour, on recollecte **toute la saison en cours** (8 bilans : 4 distances × hommes/femmes). Le résultat ne dépend donc pas des mises à jour précédentes, et une performance corrigée ou retirée par la FFA est prise en compte.

## La référence (`data/reference/`)

Instantané de la base de production au 2026-11-04 (collecte de septembre 2026), un fichier par distance, au format `rp-reference-v2` :

| Colonne | Contenu |
|---|---|
| `full_name` | Nom tel qu'affiché par la FFA (suffixe « (GBR) » pour un athlète étranger) |
| `birth_year`, `sex` | Année de naissance (peut manquer), sexe |
| `pb_sec`, `pb_date` | Meilleur temps (secondes) et sa date (JJ/MM/AA) |
| `club`, `league`, `department` | Club, ligue et département de la performance (vides pour un non-licencié) |
| `athlete_ffa_id` | Identifiant de la fiche athle.fr (peut manquer) |

Reconstruire la base depuis la référence seule redonne exactement la base de production : toutes les tables ont été comparées par empreintes.

## Contrôles des exports bruts (avant toute fusion)

`tools/build_db.py` refuse de produire une base, avec le code de sortie 2 et la liste des problèmes, si :
- la version de schéma d'un export n'est pas 3 ;
- une des 4 distances manque, ou figure deux fois ;
- pour une distance, les bilans ne sont pas exactement « hommes + femmes » de la ou des saisons annoncées par `--season` : bilan manquant, en trop, en double ou vide ;
- la saison est déjà couverte par la référence (on ne fusionne pas deux fois une saison) ;
- plus de 0,5 % des lignes sont illisibles.

Les temps impossibles sont écartés **avant** la fusion, sur toutes les distances, juste sous les records du monde sur route : 12 min au 5 km, 25 min au 10 km, 55 min au semi, 1 h 55 au marathon. Aucun profil de la référence n'est concerné.

## Règles de fusion d'une nouvelle saison

- Un athlète est identifié par son **identifiant FFA**, sinon par **nom normalisé + année de naissance + sexe**. Accents et casse sont ignorés.
- On garde le **meilleur temps** entre la référence et la nouvelle saison. S'il est amélioré, la date, le club, la ligue et le département sont ceux de la nouvelle performance.
- **Résultat indépendant de l'ordre des entrées.** Tous les rattachements sont décidés d'abord, en ne consultant que la référence et l'ensemble des athlètes entrants. Les mises à jour sont appliquées ensuite. Les égalités sont départagées de façon déterministe (temps, date, nom…).
- Un nouvel identifiant FFA est relié à un profil sans identifiant seulement si c'est le seul profil de même nom, année et sexe **et** si aucun autre nouvel identifiant ne le réclame.
- Un résultat **sans** identifiant va au profil sans identifiant de même nom, année et sexe ; à défaut, à l'unique athlète identifié correspondant, dans la référence ou parmi les nouveaux. **S'il peut appartenir à plusieurs homonymes, il est écarté et signalé** dans le rapport (« résultats ambigus »), jamais attribué au hasard.

## Mettre à jour les bilans

### Collecte sans navigateur (essai GitHub Actions)

Le workflow **Collecte FFA (sans publication)** remplace l'étape navigateur pour
la collecte uniquement. Il n'a aucun secret Cloudflare, ne crée pas de D1 et ne
déploie rien. Le collecteur navigateur existant reste disponible en secours.

Il peut aussi être déclenché en modifiant `data/collection-request.json` sur
`main` (via une PR). Ce fichier porte la saison, le mode et une nouvelle date
`requested_at` pour chaque demande. C'est la voie utilisable par un assistant
disposant du connecteur GitHub, sans connexion dans un navigateur. Ajouter
`"resume_run": "123456"` permet de reprendre un run interrompu de moins de 24 h ;
retirer ce champ pour toute nouvelle actualisation. Le workflow valide les
valeurs avant toute reprise ou requête réseau. Une PR déclenche seulement un
essai limité ; sa fusion déclenche la demande effective. Aucun horaire mensuel
ni accès D1 n'est ajouté par ce mécanisme.

Dans **GitHub → Actions → Collecte FFA (sans publication) → Run workflow** :

1. Laisser la saison vide (saison FFA courante, heure de Paris) ou saisir `2027`.
2. Choisir `probe` pour le premier essai : première, deuxième et dernière page de
   chacun des huit bilans. Ce mode ne produit **aucun export utilisable pour une
   mise à jour**. Un essai est également lancé lors d'une PR sur le collecteur.
3. Après validation de cet essai, choisir `full` : toute la saison est collectée,
   puis les quatre fichiers V3 sont générés.
4. Lire le résumé du run. L'artefact `ffa-collection-<run>` contient le rapport
   et les pages de reprise. En mode complet réussi uniquement, l'artefact distinct
   `ffa-exports-<run>` contient les quatre exports à passer à `build_db.py`.

Les requêtes sont séquentielles, espacées d'au moins une seconde, avec quatre
tentatives maximum en cas d'erreur réseau. Une page non reconnue, une pagination
ignorée, des pages identiques ou un total de lignes différent du total FFA font
échouer la collecte. La première page est relue à la fin de chaque bilan pour
détecter un changement en cours de lecture. Cela ne constitue pas un instantané
transactionnel du site FFA : le contrôle des données avant publication reste requis.

**Interruption :** les pages terminées sont conservées dans l'artefact, y compris
si le run échoue normalement. Relancer le workflow avec la même saison, le même
mode et l'ID du run interrompu dans `resume_run`, sous 24 heures. Les premières
pages sont revérifiées ; si elles ou les totaux ont changé, une nouvelle collecte
est requise (champ `resume_run` vide). Un arrêt forcé du runner peut empêcher
l'envoi de l'artefact : recommencer dans ce cas. Une actualisation mensuelle doit
toujours être une **nouvelle** collecte, jamais une reprise du mois précédent.

Les artefacts sont conservés 14 jours. Il faut les télécharger pour une conservation
plus longue. Ils ne sont pas ajoutés au dépôt Git. La collecte complète, sa durée
depuis GitHub et les éventuels blocages athle.fr doivent être validés avant d'activer
un horaire mensuel. Aucun horaire ni publication automatique n'est activé à ce stade.

Exécution locale, Python 3.9+ sans dépendance supplémentaire :

```bash
python3 tools/collect_ffa.py --season 2027 --mode probe --out build/essai-2027
python3 tools/collect_ffa.py --season 2027 --mode full --out build/collecte-2027
# Seulement pour reprendre la même campagne interrompue depuis moins de 24 h :
python3 tools/collect_ffa.py --season 2027 --mode full --out build/collecte-2027 --resume
```

### Construction et publication après collecte

Après une collecte complète réussie sur `main`, le workflow **Reconstruire et
valider FFA (hors production)** se lance automatiquement. Il télécharge seulement
les exports du collecteur de ce dépôt, construit une base de référence et une
base actualisée, puis contrôle l'intégrité SQLite, les index, la recherche FTS,
les tables dérivées, les filtres, la conservation de tous les profils historiques
et un échantillon de rangs calculés par comptage indépendant (tête, milieu et fin
de chaque distance, sexes, catégories et années).

Les rapports et journaux sont dans `ffa-validation-<run>`. La base SQLite et son
SQL d'import ne sont fournis dans `ffa-base-validee-<run>` **que si tous les
contrôles passent**. Les deux sont conservés 14 jours. `provenance.json` contient
les commits de collecte/construction et les SHA-256 des quatre exports. Il est
également possible de relancer la validation avec le bouton du workflow et l'ID
d'un run de collecte complète réussi sur `main`.

Cette validation compare avec la référence figée du dépôt, pas avec une lecture
directe de D1. Elle ne remplace pas un essai d'import dans une nouvelle D1 ni les
mesures de l'API Cloudflare avant bascule. Les saisons de catégories restent
2026/2027 ; leur passage à 2027/2028 exige toujours l'adaptation décrite plus bas.

En local, après les deux constructions :

```bash
python3 tools/validate_db.py --db build/ffa.db --baseline build/baseline.db --out build/validation.json
```

1. **Collecte** (ordinateur, sur athle.fr) : ouvrir une page « Bilans », fermer les autres onglets athle.fr, lancer `tools/ffa-collecte-bilans.js` en mode `nouvelle`. Le script efface la collecte précédente de la saison et **vérifie que la base locale est vide** ; si l'effacement est bloqué, il s'arrête sans rien collecter. Il recollecte ensuite les 8 bilans de la saison en cours. Lancer enfin le mode `export` : 4 fichiers `ffa_<distance>_2027.json.gz`, qui portent les dates de collecte (`collected_from` / `collected_to`).
2. **Construction hors production** : placer les 4 fichiers dans `data/exports/2027/` (non versionné), puis :
   ```bash
   python3 tools/build_db.py --out build/ffa.db --sql build/ffa.sql --season 2027 --raw data/exports/2027/*.json.gz
   ```
   Le rapport indique les performances lues, les lignes illisibles, les temps écartés, les records améliorés, les nouveaux profils, les identifiants reliés et les résultats ambigus.
3. **Contrôle** : `npm test` et `python3 tests/test_build_db.py`, puis comparer quelques classements de `build/ffa.db` avec la base actuelle.
4. **Mise en service** (étape manuelle) : créer une **nouvelle** base D1, y importer `build/ffa.sql`, puis changer `database_id` dans `api/wrangler.toml` et incrémenter `CACHE_VERSION` dans `api/worker.js`, dans une même PR. L'ancienne base reste intacte pour revenir en arrière. Le workflow GitHub ne fait que déployer le Worker : il ne reconstruit pas et ne publie pas la base.

## Fin de saison : prolonger la référence

Après la dernière collecte complète de la saison 2027 (en septembre 2027) :

```bash
python3 tools/build_db.py --out build/ffa.db --season 2027 --raw data/exports/2027/*.json.gz --write-reference data/reference
```

La référence devient `ffa_<distance>_2024_2027.json.gz` : les fichiers 2024–2026 sont remplacés, et la saison 2027 n'est plus acceptée en `--raw`. Les mises à jour suivantes ne collectent plus que 2028. En même temps :
- les rangs par catégorie passent aux saisons 2027 et 2028 : `--season-before 2027 --season-after 2028`, et `RANK_CAT_AFTER_SEASON` (`api/worker.js`) / `FFA_LATEST_RANKED_SEASON` (`core.js`) passent à 2028.
