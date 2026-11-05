# API Cloudflare Worker + D1 — Comparateur FFA

API en lecture seule utilisée par `mobile.html` pour la recherche, le classement et le matching des coureurs, sans charger les 1,4 million de profils dans Safari/iPhone.

## Fichiers

- `worker.js` : l'API.
- `wrangler.toml` : configuration du Worker (base D1, limitation de débit).
- `schema.sql` : **schéma complet de la base de production**, extrait de D1 le 2026-11-04, avec une description de chaque table. Il sert aussi aux tests d'intégration.
- `migrations/` : modifications de la base appliquées après cet extrait, dans l'ordre (`0001_…`, `0002_…`). Schéma actuel = `schema.sql` + migrations.

## Routes

| Route | Description |
|---|---|
| `GET /health` | Nombre total de profils. |
| `GET /search?distance=10k&q=NOM&mode=general\|sex\|category` | Recherche plein texte (100 résultats max), avec rang. |
| `GET /ranking?distance=10k&page=1&sex=&category=&year=&league=&department=&club=&seasonYear=&minPb=&maxPb=&q=&french=1&sort=rank\|name\|time&dir=asc\|desc` | Classement paginé (100 par page, page 10 000 max). |
| `GET /ranking-options?distance=10k` | Ligues, départements, clubs et années disponibles. |
| `POST /match?distance=10k` (corps `{"names":[...]}`) | Profils correspondant à une liste de noms (1000 max par requête ; l'app découpe les grosses courses). |

`distance` ∈ `5k`, `10k`, `semi`, `marathon`.

Réponses d'erreur : `400` (paramètre invalide), `404`, `429` (limite de débit, `Retry-After: 60`), `500` (`{"error":"internal_error"}`, détail dans les logs Cloudflare). Toutes portent les en-têtes CORS.

## Performances

Mesurées sur une copie locale complète de la base (1 437 065 profils, schéma de production) :

| Vue | Avant | Après |
|---|---|---|
| Classement général, page 1 | 1 ms | 1 ms |
| Général trié par temps ou par nom | ~900 ms | 1 ms |
| Hommes / femmes | ~850 ms | ~12 ms |
| Catégorie (SE, M0…) | 100–1 000 ms | 2–25 ms |
| Saison (avec la migration 0001) | 0,6–1,6 s | 5–35 ms |
| Français + sexe (avec la migration 0001) | ~1 s | 10–35 ms |
| Ligue / département | 0,4–1 s | 30–170 ms |
| Tri par nom ou recherche par nom dans un périmètre | 0,6–1,5 s | 20–100 ms |
| Périmètre + catégorie | 80–500 ms | 40–330 ms |

Sur 50 cas de classement par périmètre : 35,9 s → 3,8 s au total, aucun cas plus lent qu'avant.

Principes appliqués :
- **Trier par temps plutôt que par colonne de rang** : chaque rang est un `RANK()` par temps sur un ensemble qui contient le filtre courant, donc l'ordre est le même, mais SQLite peut suivre l'index `(distance, sexe, pb_sec)` et s'arrêter à la page demandée au lieu de trier toutes les lignes.
- **Catégories** : le Worker compte d'abord la catégorie (2 ms). Au-delà de 4 % de la distance, il parcourt par temps (`+a.birth_year` désactive l'index par année) ; en dessous, il passe par l'index par année de naissance.
- **Ligue / département** : `CROSS JOIN` depuis `athlete_scope`, pour partir de son index au lieu de parcourir toute la distance.
- **Classements par périmètre** (saison, ligue, département, club, français) : au lieu de calculer `RANK()` sur tout le périmètre, le Worker lit la page demandée (index par temps, ou par nom), compte le total, puis calcule le rang des seuls temps présents sur la page : un comptage groupé par temps sur l'index, limité au temps le plus lent de la page, puis une somme cumulée (rang = 1 + athlètes du périmètre strictement plus rapides). Même mécanisme pour le tri par rang, par temps ou par nom, avec ou sans recherche par nom. Avec une catégorie ou un club, le périmètre est lu une seule fois (`MATERIALIZED`). Vérifié contre une référence indépendante sur 768 combinaisons (`tests/worker-scoped-ranks.test.mjs`).
- **Index de la migration 0001** : saison (index sur expression) et « français » (index partiel). Sans eux, le code fonctionne mais ces filtres restent lents.
- **Cache** : `/search`, `/ranking` et `/ranking-options` sont mis en cache 1 h côté Cloudflare et 5 min dans le navigateur. Après un réimport, incrémenter `CACHE_VERSION`.


## Sécurité

- CORS limité à `https://shurikn57.github.io`. Ce n'est pas une protection contre les clients hors navigateur.
- Aucune route d'écriture. Toutes les valeurs passent par des requêtes préparées ; colonnes et tris viennent de listes fermées.
- Limitation de débit par IP : 300 requêtes/minute (binding `RATE_LIMITER`). La limite est volontairement large car les opérateurs mobiles partagent souvent une même IP.

## Schéma de la base

| Table | Contenu |
|---|---|
| `athletes` | Un profil par athlète et par distance (≈ 1,44 million de lignes, ~1,1 Go). |
| `athlete_fts` | Recherche plein texte (trigrammes) sur `name_key`. |
| `athlete_general_rank` / `athlete_french_rank` | Rang général par distance (tous / sans nationalité étrangère). |
| `athlete_search_rank` | Rangs général, par sexe et par sexe + catégorie (saisons 2026 et 2027). |
| `athlete_rank_cat_before` / `_after` | Rang par catégorie tous sexes (saisons 2026 / 2027). |
| `athlete_rank_year` | Rang par année de naissance (et sexe). |
| `athlete_scope`, `ffa_scope_options` | Ligue, département, club, année : filtres « périmètre ». |
| `ffa_distance_stats`, `ffa_french_stats` | Totaux par distance. |

Toutes ces tables sont reconstruites par `tools/build_db.py`. Les définitions ont été vérifiées par empreintes contre la base de production : rang = `RANK()` par temps croissant ; `display_order` = ordre temps, nom, id ; le rang « français » est le rang parmi tous les athlètes.

Pour comparer avec la production, extraire de nouveau le schéma (en lecture seule) :

```sql
SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE '_cf_%' AND name NOT LIKE 'sqlite_%';
```

### Maintenance saisonnière

`rank_cat_before_sep` / `athlete_rank_cat_before` correspondent à la saison 2026, `rank_cat_after_sep` / `athlete_rank_cat_after` à la saison 2027. Les catégories ne dépassent pas la saison 2027 tant que ces rangs n'ont pas été recalculés. Après recalcul, augmenter `RANK_CAT_AFTER_SEASON` (`worker.js`) et `FFA_LATEST_RANKED_SEASON` (`core.js`).

## Appliquer une migration

Dans le tableau de bord Cloudflare : **Storage & Databases → D1 → ffa-comparateur → Console**, coller le contenu du fichier de migration et exécuter. Ou en ligne de commande :

```bash
npx wrangler d1 execute ffa-comparateur --remote --file api/migrations/0001_index_saison_francais.sql
```

Les migrations de ce dépôt n'ajoutent que des index (`CREATE INDEX IF NOT EXISTS`) : aucune donnée modifiée, rejouables sans risque.

## Déploiement

Automatique via `.github/workflows/deploy-cloudflare-worker.yml` à chaque modification de `worker.js` ou `wrangler.toml` sur `main` : tests, cohérence du binding et de `data/current-release.json`, `wrangler deploy`, puis contrôle de l'API publique (total, quatre classements et recherche). Secrets GitHub requis : `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.

Mise à jour des bilans : voir [`data/README.md`](../data/README.md). La base complète (toutes les tables ci-dessus) est construite par `tools/build_db.py`, puis importée dans une **nouvelle** base D1 ; on bascule ensuite `database_id` dans `wrangler.toml`.
