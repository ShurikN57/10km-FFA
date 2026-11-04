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

## Règles de fusion d'une nouvelle saison

- Un athlète est identifié par son **identifiant FFA**, sinon par **nom normalisé + année de naissance + sexe**. Accents et casse sont ignorés.
- On garde le **meilleur temps** entre la référence et la nouvelle saison. S'il est amélioré, la date, le club, la ligue et le département sont ceux de la nouvelle performance.
- Un identifiant FFA nouveau est relié à un profil sans identifiant seulement si un seul profil a le même nom, la même année et le même sexe.
- Sur 5 km, les temps sous 12 min sont écartés (erreurs de saisie).

## Mettre à jour les bilans

1. **Collecte** (ordinateur, sur athle.fr) : ouvrir une page « Bilans », lancer `tools/ffa-collecte-bilans.js` en mode `nouvelle`. Il efface la collecte précédente de la saison, puis recollecte les 8 bilans de la saison en cours. Lancer ensuite le mode `export`. On obtient 4 fichiers : `ffa_5km_2027.json.gz`, `ffa_10km_2027.json.gz`, `ffa_semi_2027.json.gz`, `ffa_marathon_2027.json.gz`.
2. **Construction** : placer les 4 fichiers dans `data/exports/2027/` (non versionné), puis :
   ```bash
   python3 tools/build_db.py --out build/ffa.db --sql build/ffa.sql --raw data/exports/2027/*.json.gz
   ```
   Le script s'arrête si plus de 0,5 % des lignes sont illisibles. Il affiche le nombre de records améliorés et de nouveaux profils.
3. **Contrôle** : `npm test`, puis comparer quelques classements de `build/ffa.db` avec la base actuelle.
4. **Mise en service** : créer une **nouvelle** base D1, y importer `build/ffa.sql`, puis changer `database_id` dans `api/wrangler.toml` et incrémenter `CACHE_VERSION` dans `api/worker.js`, dans une même PR. L'ancienne base reste intacte pour revenir en arrière.

## Changement de saison (septembre)

Au 1er septembre 2027, la saison 2027 se termine. On fait une dernière collecte complète de 2027, puis :
- les rangs par catégorie passent aux saisons 2027 et 2028 : `--season-before 2027 --season-after 2028`, et `RANK_CAT_AFTER_SEASON` / `FFA_LATEST_RANKED_SEASON` passent à 2028 ;
- la référence peut être prolongée à 2024–2027, pour que les mises à jour suivantes ne recollectent que 2028.
