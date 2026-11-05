#!/usr/bin/env python3
"""Vérifie le binding d'une publication, puis son API publique après déploiement."""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.request import Request, urlopen

from import_d1_candidate import production_binding


def check_config(root, release):
    actual = production_binding(Path(root)/'api/wrangler.toml')
    if (actual['database_id'], actual['database_name']) != (release['database_id'], release['database_name']):
        raise ValueError('Le binding D1 ne correspond pas à la publication validée.')
    counts = release['distances']
    if set(counts) != {'5k', '10k', 'semi', 'marathon'} or any(type(n) is not int or n < 1 for n in counts.values()):
        raise ValueError('Totaux des quatre distances invalides.')
    if sum(counts.values()) != release['profiles']:
        raise ValueError('Le total des profils ne correspond pas aux quatre distances.')
    cache = re.search(r'\bconst\s+CACHE_VERSION\s*=\s*(\d+)', (Path(root)/'api/worker.js').read_text())
    if not cache or int(cache[1]) != release['cache_version']:
        raise ValueError('CACHE_VERSION ne correspond pas à la publication validée.')


def constant(path, name):
    match = re.search(r'\bconst\s+' + re.escape(name) + r'''\s*=\s*(['"])(.*?)\1''', Path(path).read_text(encoding='utf-8'))
    if not match:
        raise ValueError(f'Constante {name} absente.')
    return match[2]


def read_json(url, origin):
    request = Request(url, headers={'Origin': origin, 'User-Agent': 'RP-Release-Check/1.0'})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def check_api(release, api, origin, reader=read_json):
    health = reader(api + '/health', origin)
    if health.get('ok') is not True or health.get('athletes') != release['profiles']:
        raise ValueError('Le total de l’API publique diffère de la nouvelle base validée.')
    for distance, count in release['distances'].items():
        ranking = reader(api + '/ranking?distance=' + distance + '&page=1', origin)
        if ranking.get('total') != count or not ranking.get('rows') or ranking['rows'][0].get('rank') != 1:
            raise ValueError(f'Classement public incohérent pour {distance}.')
    search = reader(api + '/search?distance=10k&q=MARTIN&mode=general', origin)
    if not search.get('rows'):
        raise ValueError('La recherche publique ne renvoie aucun résultat de contrôle.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--config-only', action='store_true')
    args = parser.parse_args(argv)
    root = Path(args.root)
    try:
        release = json.loads((root/'data/current-release.json').read_text(encoding='utf-8'))
        check_config(root, release)
        if not args.config_only:
            api = constant(root/'mobile.html', 'FFA_API')
            origin = constant(root/'api/worker.js', 'ALLOWED_ORIGIN')
            if not api.startswith('https://') or not origin.startswith('https://'):
                raise ValueError('URL HTTPS attendue pour les contrôles de publication.')
            check_api(release, api, origin)
        print(f"Publication cohérente : {release['profiles']:,} profils ; " +
              ('configuration seule contrôlée.' if args.config_only else 'API, quatre classements et recherche contrôlés.'))
        return 0
    except (OSError, ValueError, KeyError) as error:
        print(f'Contrôle de publication en échec : {error}', file=sys.stderr)
        return 2


if __name__ == '__main__': sys.exit(main())
