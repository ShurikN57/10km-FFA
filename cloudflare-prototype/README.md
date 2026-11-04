# API Cloudflare Worker + D1 — Comparateur FFA

API en lecture seule utilisée par `mobile.html` pour la recherche, le classement et le matching des coureurs, sans charger les 500 000+ profils dans Safari/iPhone.

## Fichiers

- `worker.js` : l'API.
- `wrangler.toml` : configuration du Worker (base D1, limitation de débit).
- `prepare_import.py` : lit les bases gzip du dépôt (4 distances) et génère `ffa_d1_import.sql` (table `athletes`).
- `schema.sql` : **schéma partiel**, avec seulement la table `athletes` et ses index (voir plus bas).

## Routes

| Route | Description |
|---|---|
| `GET /health` | Nombre total de profils. |
| `GET /search?distance=10k&q=NOM&mode=general\|sex\|category` | Recherche plein texte (100 résultats max), avec rang. |
| `GET /ranking?distance=10k&page=1&sex=&category=&year=&league=&department=&club=&seasonYear=&minPb=&maxPb=&q=&french=1&sort=rank\|name\|time&dir=asc\|desc` | Classement paginé (100 par page, page 10 000 max). |
| `GET /ranking-options?distance=10k` | Ligues, départements, clubs et années disponibles. |
| `POST /match?distance=10k` (corps `{"names":[...]}`) | Profils correspondant à une liste de noms (1000 max). |

`distance` ∈ `5k`, `10k`, `semi`, `marathon`.

Réponses d'erreur : `400` (paramètre invalide), `404`, `429` (limite de débit, `Retry-After: 60`), `500` (`{"error":"internal_error"}`, détail dans les logs Cloudflare). Toutes portent les en-têtes CORS.

## Sécurité

- CORS limité à `https://shurikn57.github.io`. Ce n'est pas une protection contre les clients hors navigateur.
- Aucune route d'écriture. Toutes les valeurs passent par des requêtes préparées ; colonnes et tris viennent de listes fermées.
- Limitation de débit par IP : 300 requêtes/minute (binding `RATE_LIMITER`). La limite est volontairement large car les opérateurs mobiles partagent souvent une même IP.

## Schéma de la base

En plus de `athletes`, le Worker utilise des tables précalculées qui **ne sont pas encore versionnées** dans ce dépôt :
`athlete_fts` (FTS5), `athlete_search_rank`, `athlete_general_rank`, `athlete_french_rank`, `athlete_scope`, `athlete_rank_year`, `athlete_rank_cat_before`, `athlete_rank_cat_after`, `ffa_scope_options`, `ffa_distance_stats`, `ffa_french_stats`.

Pour récupérer le schéma réel depuis la base de production et le versionner :

```bash
npx wrangler d1 export ffa-comparateur --remote --no-data --output schema.full.sql
```

Les requêtes SQL qui remplissent ces tables doivent aussi être ajoutées au dépôt : sans elles, la base ne peut pas être reconstruite.

### Maintenance saisonnière

`rank_cat_before_sep` / `athlete_rank_cat_before` correspondent à la saison 2026, `rank_cat_after_sep` / `athlete_rank_cat_after` à la saison 2027. Avant le 1er septembre 2027, il faut recalculer ces rangs et mettre à jour `RANK_CAT_AFTER_SEASON` dans `worker.js`.

## Déploiement

Automatique via `.github/workflows/deploy-cloudflare-worker.yml` (tests puis `wrangler deploy`) à chaque modification de `worker.js` ou `wrangler.toml` sur `main`. Secrets GitHub requis : `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`.

Réimport complet de la table `athletes` :

```bash
cd cloudflare-prototype
python prepare_import.py
npx wrangler d1 execute ffa-comparateur --remote --file ffa_d1_import.sql
```

⚠️ Ce réimport recrée les `id` : les tables de rang précalculées doivent ensuite être régénérées.
