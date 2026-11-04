# RP — Running Performance

PWA (pensée pour iPhone) qui compare les résultats d'une course aux meilleures performances des **bilans FFA 2024–2026** sur 5 km, 10 km, semi-marathon et marathon.

Application : <https://shurikn57.github.io/10km-FFA/>

## Fonctionnalités

- **Recherche** d'un athlète FFA et de son rang (général, H/F, catégorie).
- **Classement** complet filtrable (sexe, catégorie, année, ligue, département, club, saison, fourchette de temps).
- **Analyse** d'un classement de course (GoTiming, UTMB, ACN Timing, CSV, Excel ou texte collé) : chaque coureur est associé à son profil FFA, avec l'écart à son record.

## Architecture

| Élément | Rôle |
|---|---|
| `mobile.html` | Application (HTML/CSS/JS), servie par GitHub Pages. `index.html` redirige dessus. |
| `core.js` | Logique pure partagée : parsing des temps et des classements, matching des noms, catégories FFA. |
| `sw.js`, `manifest.webmanifest`, `icons/` | PWA (service worker « réseau d'abord », installation sur l'écran d'accueil). |
| `cloudflare-prototype/` | API Cloudflare Worker + base D1 : `/search`, `/ranking`, `/ranking-options`, `/match`, `/health`. Voir son [README](cloudflare-prototype/README.md). |
| `ffa_*.json.gz` | Bases FFA compressées : source d'import de D1 et secours hors API. |
| `ffa-auto-24-v3.js` | Script à lancer dans la console sur athle.fr pour collecter les 24 bilans (4 distances × 3 années × 2 sexes). |
| `import_comparateur_user.js` | Userscript qui récupère un classement GoTiming/UTMB/ACN et l'envoie à l'app. |
| `Installer_Raccourci_iPhone_v7.html` | Page d'installation du même script sous forme de raccourci iPhone (version minifiée). |

## Développement

```bash
npm test
```

Tests unitaires sans dépendance (`node --test`, Node ≥ 22) sur `core.js` et sur le Worker avec une base D1 simulée. Ils tournent aussi en CI sur chaque PR.

Pour tester l'app en local :

```bash
python3 -m http.server 8000
```

puis ouvrir <http://localhost:8000/mobile.html>.

## Déploiement

- **Front** : GitHub Pages, à chaque push sur `main`. Après une modification de `mobile.html` ou `core.js`, incrémenter `SHELL_CACHE` dans `sw.js` pour que les PWA installées proposent la mise à jour.
- **API** : le workflow `deploy-cloudflare-worker.yml` lance les tests puis déploie le Worker quand `cloudflare-prototype/worker.js` ou `wrangler.toml` change sur `main`.

## Maintenance saisonnière

Les catégories (CA, JU, ES, SE, M0…M10) sont calculées automatiquement à partir de la saison FFA en cours (bascule le 1er septembre). En revanche, **les rangs par catégorie sont précalculés dans D1** pour les saisons 2026 et 2027 : il faut les recalculer avant septembre 2027 (voir `RANK_CAT_AFTER_SEASON` dans `worker.js`).

## Données personnelles

Les données proviennent des bilans publics de la FFA (athle.fr). Une mention « Données & vie privée » figure dans l'application. Les demandes de rectification ou de retrait passent par les [issues GitHub](https://github.com/ShurikN57/10km-FFA/issues).
