#!/usr/bin/env python3
"""Crée et contrôle une nouvelle D1, sans modifier le binding de production.

Python 3.11+. Les secrets Cloudflare sont lus dans l'environnement uniquement.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import tomllib
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(path)


def production_binding(config):
    doc = tomllib.loads(Path(config).read_text(encoding='utf-8'))
    bindings = [d for d in doc.get('d1_databases', []) if d.get('binding') == 'DB']
    if len(bindings) != 1:
        raise ValueError('Binding DB de production absent ou ambigu.')
    return bindings[0]


def checked_report(folder):
    folder = Path(folder)
    report = json.loads((folder / 'validation.json').read_text(encoding='utf-8'))
    provenance = json.loads((folder / 'provenance.json').read_text(encoding='utf-8'))
    if report.get('ok') is not True or not report.get('checks') or any(c.get('ok') is not True for c in report['checks']):
        raise ValueError('Un rapport entièrement validé est requis avant création de D1.')
    season = provenance.get('season')
    if not isinstance(season, int) or not 1000 <= season <= 9999:
        raise ValueError('Saison invalide dans la provenance.')
    return report, provenance


def assert_candidate(state, config):
    production = production_binding(config)
    candidate = state['database_id']
    UUID(candidate)
    if candidate == production['database_id'] or state['database_name'] == production['database_name']:
        raise ValueError('Import refusé : la cible correspond à la production.')
    if not re.fullmatch(r'ffa-stage-[0-9-]+', state['database_name']):
        raise ValueError('Nom de base candidate invalide.')
    if state['production_database_id'] != production['database_id']:
        raise ValueError('Le binding de production a changé pendant la préparation.')


class Cloudflare:
    def __init__(self):
        self.token = os.environ.get('CLOUDFLARE_API_TOKEN', '')
        account = os.environ.get('CLOUDFLARE_ACCOUNT_ID', '')
        if not self.token or not re.fullmatch(r'[a-fA-F0-9]{32}', account):
            raise ValueError('Secrets Cloudflare requis et identifiant de compte valide.')
        self.base = f'https://api.cloudflare.com/client/v4/accounts/{account}/d1/database'

    def call(self, suffix='', body=None):
        req = Request(self.base + suffix, data=json.dumps(body).encode() if body is not None else None,
                      headers={'Authorization': 'Bearer ' + self.token, 'Content-Type': 'application/json'})
        try:
            with urlopen(req, timeout=60) as response:
                doc = json.load(response)
        except HTTPError as error:
            # Ne jamais journaliser les en-têtes, le token ou une URL signée.
            raise RuntimeError(f'Cloudflare HTTP {error.code} : vérifier les droits D1 du jeton existant.') from None
        if doc.get('success') is not True:
            codes = [e.get('code') for e in doc.get('errors', [])]
            raise RuntimeError(f'Cloudflare a refusé la requête (codes {codes}).')
        return doc['result']

    def create(self, name):
        return self.call(body={'name': name, 'primary_location_hint': 'weur'})

    def query(self, state, config, sql):
        assert_candidate(state, config)
        if not sql.lstrip().upper().startswith('SELECT '):
            raise ValueError('Les contrôles distants sont limités à SELECT.')
        results = self.call('/' + state['database_id'] + '/query', {'sql': sql})
        if len(results) != 1 or results[0].get('success') is not True:
            raise RuntimeError('Résultat de contrôle D1 inattendu.')
        return results[0].get('results', []), results[0].get('meta', {})


def create_candidate(folder, state_path, config, validation_run, execution, attempt, api):
    report, provenance = checked_report(folder)
    for value in (validation_run, execution, attempt):
        if not re.fullmatch(r'[1-9][0-9]*', str(value)):
            raise ValueError('Identifiant de run ou de tentative invalide.')
    production = production_binding(config)
    name = f'ffa-stage-{provenance["season"]}-{execution}-{attempt}'
    state = {'ready': False, 'status': 'creating', 'validation_run': str(validation_run),
             'validation_provenance': provenance, 'database_name': name,
             'production_database_id': production['database_id'],
             'production_database_name': production['database_name'],
             'expected_profiles': sum(d['after'] for d in report['distances']),
             'created_at': datetime.now(timezone.utc).isoformat()}
    created = api.create(name)
    state['database_id'] = created['uuid']
    state['status'] = 'created'
    save(state_path, state)
    assert_candidate(state, config)
    return state


def sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(2**20), b''):
            digest.update(block)
    return digest.hexdigest()


def import_candidate(folder, state_path, config, api, runner=subprocess.run):
    folder, state_path = Path(folder), Path(state_path)
    state = json.loads(state_path.read_text(encoding='utf-8'))
    report, _ = checked_report(folder)
    assert_candidate(state, config)
    database, sql = folder / 'ffa.db', folder / 'ffa.sql'
    if database.stat().st_size != report['database_bytes'] or sql.stat().st_size != report['sql']['bytes']:
        raise ValueError('Les tailles des fichiers diffèrent du rapport validé.')
    with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
        if db.execute('SELECT COUNT(*) FROM athletes').fetchone()[0] != state['expected_profiles']:
            raise ValueError('Le nombre de profils diffère du rapport validé.')
    state['sql_sha256'] = sha256(sql)
    candidate_config = state_path.parent / 'candidate.toml'
    candidate_config.write_text('name = "ffa-d1-import-validation"\ncompatibility_date = "2026-08-31"\n'
        '[[d1_databases]]\nbinding = "DB"\n' +
        'database_name = ' + json.dumps(state['database_name']) + '\n' +
        'database_id = ' + json.dumps(state['database_id']) + '\n', encoding='utf-8')
    state['status'] = 'importing'
    save(state_path, state)
    try:
        assert_candidate(state, config)
        runner(['npx', '--yes', 'wrangler@4.157.0', 'd1', 'execute', state['database_name'],
                '--remote', '--config', str(candidate_config), '--file', str(sql), '--yes'], check=True)
        state['status'] = 'checking'
        state['checks'] = []
        save(state_path, state)
        queries = [('profils', 'SELECT COUNT(*) AS n FROM athletes'),
                   ('stats', 'SELECT distance,total FROM ffa_distance_stats ORDER BY distance'),
                   ('stats_francais', 'SELECT distance,total FROM ffa_french_stats ORDER BY distance'),
                   ('index', "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%' ORDER BY name")]
        for table in ['athlete_fts', 'athlete_general_rank', 'athlete_french_rank', 'athlete_search_rank',
                      'athlete_rank_cat_before', 'athlete_rank_cat_after', 'athlete_rank_year', 'athlete_scope', 'ffa_scope_options']:
            queries.append((table, f'SELECT COUNT(*) AS n FROM {table}'))
        for distance in ('5k', '10k', 'semi', 'marathon'):
            queries.append(('classement_' + distance, f"SELECT a.full_name,a.pb_sec,g.rank,g.display_order,s.rank_sex,s.rank_cat_after_sep FROM athlete_general_rank g JOIN athletes a ON a.id=g.athlete_id JOIN athlete_search_rank s ON s.athlete_id=a.id WHERE g.distance='{distance}' ORDER BY g.display_order LIMIT 10"))
        queries.append(('recherche_fts', '''SELECT COUNT(*) AS n FROM athlete_fts WHERE athlete_fts MATCH '"MARTIN"' '''))
        with sqlite3.connect(database.resolve().as_uri() + '?mode=ro', uri=True) as db:
            db.row_factory = sqlite3.Row
            for label, query in queries:
                expected = [dict(r) for r in db.execute(query)]
                actual, meta = api.query(state, config, query)
                state['checks'].append({'name': label, 'ok': actual == expected,
                                        'expected': expected, 'actual': actual,
                                        'd1_duration_ms': meta.get('duration')})
                save(state_path, state)
                if actual != expected:
                    raise ValueError(f'Contrôle D1 différent de SQLite : {label}.')
        state.update(ready=True, status='validated', finished_at=datetime.now(timezone.utc).isoformat())
        save(state_path, state)
        return state
    except Exception as error:
        state.update(ready=False, status='failed', error=str(error))
        save(state_path, state)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=['create', 'import'])
    parser.add_argument('--folder', required=True)
    parser.add_argument('--state', required=True)
    parser.add_argument('--config', default='api/wrangler.toml')
    parser.add_argument('--validation-run')
    args = parser.parse_args(argv)
    try:
        api = Cloudflare()
        if args.phase == 'create':
            state = create_candidate(args.folder, args.state, args.config, args.validation_run,
                os.environ['GITHUB_RUN_ID'], os.environ['GITHUB_RUN_ATTEMPT'], api)
        else:
            state = import_candidate(args.folder, args.state, args.config, api)
        print(f"Base candidate : {state['database_name']}, état : {state['status']}. Production inchangée.")
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print(f'Préparation D1 arrêtée : {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
