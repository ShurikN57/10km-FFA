# API Cloudflare Worker + D1 — Comparateur FFA

API en lecture seule utilisée par `mobile.html` pour la recherche, le classement et le matching des coureurs, sans charger les 1,4 million de profils dans Safari/iPhone.

## Fichiers

- `worker.js` : l'API.
- `wrangler.toml` : configuration du Worker (base D1, limitation de débit).
- `schema.sql` : **schéma complet de la base de production**, extrait de D1 le 2026-11-04, avec une description de chaque table. Il sert aussi aux tests d'intégration.
- `migrations/` : modifications de la base appliquées après cet extrait, dans l'ordre (`0001_…`, `0002_…`). Schéma actuel = `schema.sql` + migrations.
- `prepare_import.py` : lit les bilans de `data/` (4 distances) et génère `ffa_d1_import.sql` (table `athletes`, fichier ignoré par Git).

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
| Ligue / département | 700–1 000 ms | 20–150 ms |
| Saison (avec la migration 0001) | 0,6–1,6 s | 5–30 ms |
| Français + sexe (avec la migration 0001) | ~1 s | 11–37 ms |

Principes appliqués :
- **Trier par temps plutôt que par colonne de rang** : chaque rang est un `RANK()` par temps sur un ensemble qui contient le filtre courant, donc l'ordre est le même, mais SQLite peut suivre l'index `(distance, sexe, pb_sec)` et s'arrêter à la page demandée au lieu de trier toutes les lignes.
- **Catégories** : le Worker compte d'abord la catégorie (2 ms). Au-delà de 4 % de la distance, il parcourt par temps (`+a.birth_year` désactive l'index par année) ; en dessous, il passe par l'index par année de naissance.
- **Ligue / département** : `CROSS JOIN` depuis `athlete_scope`, pour partir de son index au lieu de parcourir toute la distance.
- **Classements par périmètre** (saison, ligue, département, club, français) triés par rang ou temps : au lieu de calculer `RANK()` sur tout le périmètre, le Worker lit seulement la page et déduit les rangs exacts de 1 à 3 comptages sur l'index (rang = 1 + nombre d'athlètes plus rapides). Vérifié contre une référence indépendante sur 112 combinaisons (`tests/worker-scoped-ranks.test.mjs`).
- **Index de la migration 0001** : saison (index sur expression) et « français » (index partiel). Sans eux, le code fonctionne mais ces filtres restent lents.
- **Cache** : `/search`, `/ranking` et `/ranking-options` sont mis en cache 1 h côté Cloudflare et 5 min dans le navigateur. Après un réimport, incrémenter `CACHE_VERSION`.

Encore lents (0,5–0,8 s, rares) : tri par nom ou recherche par nom à l'intérieur d'un périmètre (saison, ligue…).

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

**Toujours manquant :** les requêtes SQL qui remplissent les tables de rang. Elles sont indispensables pour recalculer les rangs ou réimporter les données.

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

Automatique via `.github/workflows/deploy-cloudflare-worker.yml` (tests puis `wrangler deploy`) à chaque modification de `worker.js` ou `wrangler.toml` sur `main`. Secrets GitHub requis : `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.

Réimport complet de la table `athletes` :

```bash
cd api
python prepare_import.py
npx wrangler d1 execute ffa-comparateur --remote --file ffa_d1_import.sql
```

⚠️ `prepare_import.py` ne fait qu'insérer : la table `athletes` doit être vidée avant. Le réimport recrée les `id`, donc les tables de rang et la recherche plein texte doivent ensuite être régénérées, puis `CACHE_VERSION` incrémenté.
