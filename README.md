# RP — Running Performance

PWA (pensée pour iPhone) qui compare les résultats d'une course aux meilleures performances des **bilans FFA 2024–2026** sur 5 km, 10 km, semi-marathon et marathon.

Application : <https://shurikn57.github.io/10km-FFA/>

## Fonctionnalités

- **Recherche** d'un athlète FFA et de son rang (général, H/F, catégorie).
- **Classement** complet filtrable : sexe, catégorie, année de naissance, ligue, département, club, saison, fourchette de temps, nom.
- **Analyse** d'un classement de course (GoTiming, UTMB, ACN Timing ou texte collé) : chaque coureur est associé à son profil FFA, avec l'écart à son record.

## Structure du dépôt

```
.
├── index.html             Redirection vers mobile.html
├── mobile.html            L'application (HTML, CSS, JS)
├── core.js                Logique pure : temps, noms, catégories, lecture des classements, matching
├── sw.js                  Service worker : ouverture instantanée et hors ligne, bouton « MAJ »
├── manifest.webmanifest   Manifeste PWA
├── icons/                 Icônes de l'app
│
├── api/                   API Cloudflare Worker + base D1 (voir api/README.md)
│   ├── worker.js          Routes /search, /ranking, /ranking-options, /match, /health
│   ├── wrangler.toml      Configuration du Worker (base D1, limitation de débit)
│   ├── schema.sql         Schéma complet de la base de production
│   └── prepare_import.py  Génère l'import SQL de la table athletes depuis data/
│
├── data/                  Bilans FFA compressés (une ligne par athlète et par distance)
├── tools/                 Scripts navigateur de collecte et d'import
│   ├── ffa-auto-24-v3.js                 Collecte des 24 bilans sur athle.fr (console)
│   ├── import_comparateur_user.js        Userscript : envoie un classement GoTiming/UTMB/ACN à l'app
│   └── Installer_Raccourci_iPhone_v7.html  Le même import en raccourci iPhone
│
├── tests/                 Tests unitaires, d'intégration SQL et de bout en bout
└── .github/workflows/     CI (tests) et déploiement du Worker
```

L'app reste à la racine : GitHub Pages la sert depuis `main`, et l'adresse de la PWA installée ne doit pas changer.

## Développement

```bash
npm test
```

Tests sans dépendance (`node --test`, Node ≥ 22) :
- `tests/core.test.js` : logique de `core.js` ;
- `tests/worker.test.mjs` : comportement de l'API (erreurs, pagination, cache, limitation de débit) ;
- `tests/worker-sql.test.mjs` : toutes les requêtes SQL de l'API exécutées sur une base SQLite construite avec `api/schema.sql`.

```bash
npm run test:e2e
```

Test de bout en bout de l'app dans Chromium avec l'API simulée (nécessite Playwright) : recherche, classement, filtres, changement de distance, import d'une course.

Pour lancer l'app en local :

```bash
python3 -m http.server 8000
```

puis ouvrir <http://localhost:8000/mobile.html>.

## Déploiement

- **App** : GitHub Pages (« Deploy from a branch », `main`).
  **À chaque modification de l'app** (`mobile.html`, `core.js`, `index.html`, manifeste, icônes), incrémenter `SHELL_CACHE` dans `sw.js`, par exemple `comparateur-ffa-shell-v17` → `v18`. Ce changement fait apparaître le bouton « ↻ MAJ disponible » sur les téléphones. Sans lui, la nouveauté n'arrive qu'à l'ouverture suivante. La CI fait échouer une PR qui modifie l'app sans incrémenter `SHELL_CACHE`.
- **API** : le workflow `deploy-cloudflare-worker.yml` lance les tests, puis déploie le Worker quand `api/worker.js` ou `api/wrangler.toml` change sur `main`.

## Maintenance

- **Après un réimport des bilans** : incrémenter `CACHE_VERSION` dans `api/worker.js` pour vider le cache de l'API.
- **Chaque saison** : les catégories suivent la saison FFA (bascule le 1er septembre), mais pas au-delà de la dernière saison dont les rangs par catégorie sont précalculés dans D1 (2027). Après recalcul de ces rangs, augmenter `RANK_CAT_AFTER_SEASON` (`api/worker.js`) et `FFA_LATEST_RANKED_SEASON` (`core.js`).

## Données personnelles

Les données proviennent des bilans publics de la FFA (athle.fr). Une mention « Données & vie privée » figure dans l'application. Les demandes de rectification ou de retrait passent par les [issues GitHub](https://github.com/ShurikN57/10km-FFA/issues).
