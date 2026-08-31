# Prototype Cloudflare D1 — Comparateur FFA

Ce dossier est volontairement indépendant de `mobile.html`. La version GitHub Pages actuelle continue donc de fonctionner sans changement.

## Objectif

Tester la recherche et le classement via une API Cloudflare Worker + D1 afin de ne plus charger 123k/527k profils dans Safari/iPhone.

## Fichiers

- `schema.sql` : table + index D1.
- `worker.js` : API `/health`, `/search`, `/ranking`.
- `prepare_import.py` : lit directement les bases gzip 5 km et 10 km du dépôt et génère `ffa_d1_import.sql`.
- `wrangler.toml` : configuration du Worker, à compléter uniquement avec l'identifiant D1 créé par Cloudflare.

## Mise en place

Depuis la racine du dépôt :

```bash
cd cloudflare-prototype
npm install -g wrangler
wrangler login
wrangler d1 create ffa-comparateur --location weur
```

Copier le `database_id` affiché par Cloudflare dans `wrangler.toml`, puis :

```bash
wrangler d1 execute ffa-comparateur --remote --file schema.sql
python prepare_import.py
wrangler d1 execute ffa-comparateur --remote --file ffa_d1_import.sql
wrangler deploy
```

## Tests

Une fois le Worker déployé :

```text
/health
/search?distance=10k&q=MACHOUCHE
/search?distance=5k&q=DUPONT
/ranking?distance=10k&page=1
/ranking?distance=5k&sex=M&minPb=900&maxPb=1200&page=1
```

## Sécurité du prototype

Le CORS autorise uniquement `https://shurikn57.github.io`. L'API est en lecture seule : aucune route d'écriture n'est exposée.

## Étape suivante

Quand `/search` est validé sur iPhone, brancher uniquement l'onglet Recherche sur cette API. Le chargement gzip actuel reste alors disponible en secours jusqu'à validation complète. Le classement sera migré ensuite.
