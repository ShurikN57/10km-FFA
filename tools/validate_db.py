#!/usr/bin/env python3
"""Contrôle une reconstruction FFA hors production contre une base de référence.

Les deux bases sont ouvertes en lecture seule. Aucun accès réseau ou D1.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import time

from build_db import CATEGORY_AGES, DISTANCES, FRENCH_SQL, RANK_SEASON_BEFORE, RANK_SEASON_AFTER, category

# Limite par instruction, documentée par Cloudflare (vérifiée le 05/11/2026) :
# https://developers.cloudflare.com/d1/platform/limits/
D1_SQL_STATEMENT_LIMIT = 100_000


def open_readonly(path):
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True)


def validate(database, baseline, season_before=RANK_SEASON_BEFORE, season_after=RANK_SEASON_AFTER, sql_path=None):
    started = time.monotonic()
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'checks': [],
              'database_bytes': Path(database).stat().st_size,
              'baseline_bytes': Path(baseline).stat().st_size, 'distances': []}
    def check(name, actual, expected):
        report['checks'].append({'name': name, 'ok': actual == expected,
                                 'actual': actual, 'expected': expected})
    with open_readonly(database) as db, open_readonly(baseline) as old:
        db.row_factory = old.row_factory = sqlite3.Row
        rows = lambda sql, params=(): [tuple(r) for r in db.execute(sql, params)]
        scalar = lambda sql, params=(): db.execute(sql, params).fetchone()[0]
        check('sqlite_quick_check', rows('PRAGMA quick_check'), [('ok',)])
        schema_query = "SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type,name"
        check('schema_et_index', rows(schema_query), [tuple(r) for r in old.execute(schema_query)])
        total = scalar('SELECT COUNT(*) FROM athletes')
        check('fts_nombre', scalar('SELECT COUNT(*) FROM athlete_fts'), total)
        check('fts_contenu', scalar('SELECT COUNT(*) FROM athletes a LEFT JOIN athlete_fts f ON f.rowid=a.id WHERE f.rowid IS NULL OR f.name_key IS NOT a.name_key OR f.distance IS NOT a.distance'), 0)
        for table in ['athlete_general_rank', 'athlete_search_rank', 'athlete_rank_year', 'athlete_scope']:
            check(table + '_nombre', scalar(f'SELECT COUNT(*) FROM {table}'), total)
            check(table + '_orphelins', scalar(f'SELECT COUNT(*) FROM {table} r LEFT JOIN athletes a ON a.id=r.athlete_id WHERE a.id IS NULL'), 0)
        for table, season in [('athlete_rank_cat_before', season_before), ('athlete_rank_cat_after', season_after)]:
            eligible = scalar('SELECT COUNT(*) FROM athletes WHERE birth_year IS NOT NULL AND ?-birth_year>=16', (season,))
            check(table + '_nombre', scalar(f'SELECT COUNT(*) FROM {table}'), eligible)
            check(table + '_eligibilite', scalar(f'SELECT COUNT(*) FROM {table} r LEFT JOIN athletes a ON a.id=r.athlete_id WHERE a.id IS NULL OR a.birth_year IS NULL OR ?-a.birth_year<16', (season,)), 0)
        check('stats_totaux', rows('SELECT distance,total FROM ffa_distance_stats ORDER BY distance'), rows('SELECT distance,COUNT(*) FROM athletes GROUP BY distance ORDER BY distance'))
        check('stats_francais', rows('SELECT distance,total FROM ffa_french_stats ORDER BY distance'), rows(f'SELECT distance,COUNT(*) FROM athletes WHERE {FRENCH_SQL} GROUP BY distance ORDER BY distance'))
        expected_french = scalar(f'SELECT COUNT(*) FROM athletes WHERE {FRENCH_SQL}')
        check('francais_nombre', scalar('SELECT COUNT(*) FROM athlete_french_rank'), expected_french)
        check('francais_rangs', scalar(f'SELECT COUNT(*) FROM athlete_french_rank f LEFT JOIN athletes a ON a.id=f.athlete_id LEFT JOIN athlete_general_rank g ON g.athlete_id=f.athlete_id WHERE a.id IS NULL OR NOT (a.{FRENCH_SQL}) OR f.rank_general IS NOT g.rank OR f.distance IS NOT a.distance'), 0)
        check('perimetres_distance', scalar('SELECT COUNT(*) FROM athlete_scope s JOIN athletes a ON a.id=s.athlete_id WHERE s.distance IS NOT a.distance'), 0)
        options = "SELECT DISTINCT a.distance,s.league,s.department,COALESCE(a.club,''),s.race_year FROM athletes a JOIN athlete_scope s ON s.athlete_id=a.id"
        for direction, left, right in [('manquantes', options, 'SELECT * FROM ffa_scope_options'), ('en_trop', 'SELECT * FROM ffa_scope_options', options)]:
            check('options_' + direction, scalar(f'SELECT COUNT(*) FROM ({left} EXCEPT {right})'), 0)
        for distance, _, _ in DISTANCES:
            count = scalar('SELECT COUNT(*) FROM athletes WHERE distance=?', (distance,))
            before = old.execute('SELECT COUNT(*) FROM athletes WHERE distance=?', (distance,)).fetchone()[0]
            check(distance + '_profils_conserves', count >= before, True)
            # Le constructeur conserve l'ordre de la référence dans chaque distance,
            # puis ajoute les nouveaux profils. Les IDs globaux peuvent changer.
            fields = 'full_name,birth_year,sex,pb_sec,athlete_ffa_id'
            current = iter(db.execute(f'SELECT {fields} FROM athletes WHERE distance=? ORDER BY id', (distance,)))
            lost = 0
            improved = 0
            for ref in old.execute(f'SELECT {fields} FROM athletes WHERE distance=? ORDER BY id', (distance,)):
                new = next(current, None)
                if new is None:
                    lost += 1
                    continue
                if (new['full_name'] != ref['full_name'] or new['sex'] != ref['sex'] or
                    (ref['birth_year'] is not None and new['birth_year'] != ref['birth_year']) or
                    (ref['athlete_ffa_id'] and new['athlete_ffa_id'] != ref['athlete_ffa_id']) or
                    new['pb_sec'] > ref['pb_sec']):
                    lost += 1
                improved += new['pb_sec'] < ref['pb_sec']
            check(distance + '_historique_sans_regression', lost, 0)
            report['distances'].append({'distance': distance, 'before': before, 'after': count,
                                        'new': count - before, 'improved_existing': improved})
            order = rows('SELECT COUNT(*),COUNT(DISTINCT display_order),MIN(display_order),MAX(display_order) FROM athlete_general_rank WHERE distance=?', (distance,))[0]
            check(distance + '_ordre_contigu', order, (count, count, 1 if count else None, count or None))
            # Échantillon déterministe : tête, milieu et fin du classement, avec
            # comptages indexés indépendants des RANK() de construction.
            positions = sorted({1, min(2, count), max(1, count // 2), count}) if count else []
            for position in positions:
                athlete = db.execute('SELECT a.*,g.rank,g.display_order FROM athlete_general_rank g JOIN athletes a ON a.id=g.athlete_id WHERE g.distance=? AND g.display_order=?', (distance, position)).fetchone()
                if athlete is None:
                    check(f'{distance}_position_{position}', None, 'profil présent')
                    continue
                a = athlete
                prefix = f'{distance}_id{a["id"]}_'
                faster = 1 + scalar('SELECT COUNT(*) FROM athletes WHERE distance=? AND pb_sec<?', (distance, a['pb_sec']))
                check(prefix + 'general', a['rank'], faster)
                derived = db.execute('SELECT * FROM athlete_search_rank WHERE athlete_id=?', (a['id'],)).fetchone()
                if derived is None:
                    check(prefix + 'search', None, 'profil présent')
                    continue
                check(prefix + 'search_general', derived['rank_general'], faster)
                check(prefix + 'sexe', derived['rank_sex'], 1 + scalar('SELECT COUNT(*) FROM athletes WHERE distance=? AND sex IS ? AND pb_sec<?', (distance, a['sex'], a['pb_sec'])))
                year = db.execute('SELECT * FROM athlete_rank_year WHERE athlete_id=?', (a['id'],)).fetchone()
                if year is not None:
                    check(prefix + 'annee', year['rank_year'], 1 + scalar('SELECT COUNT(*) FROM athletes WHERE distance=? AND birth_year IS ? AND pb_sec<?', (distance, a['birth_year'], a['pb_sec'])))
                    check(prefix + 'sexe_annee', year['rank_sex_year'], 1 + scalar('SELECT COUNT(*) FROM athletes WHERE distance=? AND birth_year IS ? AND sex IS ? AND pb_sec<?', (distance, a['birth_year'], a['sex'], a['pb_sec'])))
                for suffix, season, table in [('before_sep', season_before, 'athlete_rank_cat_before'), ('after_sep', season_after, 'athlete_rank_cat_after')]:
                    code = category(a['birth_year'], season)
                    expected, expected_sex = None, None
                    if code:
                        _, lo, hi = next(x for x in CATEGORY_AGES if x[0] == code)
                        clause = 'distance=? AND pb_sec<? AND birth_year<=?'
                        args = (distance, a['pb_sec'], season - lo)
                        if hi is not None:
                            clause += ' AND birth_year>=?'
                            args += (season - hi,)
                        expected = 1 + scalar('SELECT COUNT(*) FROM athletes WHERE ' + clause, args)
                        expected_sex = 1 + scalar('SELECT COUNT(*) FROM athletes WHERE ' + clause + ' AND sex IS ?', args + (a['sex'],))
                    rank = db.execute(f'SELECT rank_category FROM {table} WHERE athlete_id=?', (a['id'],)).fetchone()
                    check(prefix + 'categorie_' + suffix, rank[0] if rank else None, expected)
                    check(prefix + 'sexe_categorie_' + suffix, derived['rank_cat_' + suffix], expected_sex)
    if sql_path is not None:
        pending = ''
        longest, statements = 0, 0
        with open(sql_path, encoding='utf-8') as stream:
            for line in stream:
                pending += line
                longest = max(longest, len(pending.encode('utf-8')))
                if longest > D1_SQL_STATEMENT_LIMIT:
                    break
                if sqlite3.complete_statement(pending):
                    statements += 1
                    pending = ''
        check('sql_taille_instructions_d1', longest <= D1_SQL_STATEMENT_LIMIT, True)
        check('sql_instructions_terminees', not pending.strip(), True)
        report['sql'] = {'bytes': Path(sql_path).stat().st_size, 'statements': statements,
                         'largest_statement_bytes': longest, 'statement_limit_bytes': D1_SQL_STATEMENT_LIMIT}
    report['ok'] = all(c['ok'] for c in report['checks'])
    report['duration_seconds'] = round(time.monotonic() - started, 2)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--sql', help='contrôle aussi la taille des instructions SQL pour D1')
    parser.add_argument('--season-before', type=int, default=RANK_SEASON_BEFORE)
    parser.add_argument('--season-after', type=int, default=RANK_SEASON_AFTER)
    args = parser.parse_args(argv)
    try:
        report = validate(args.db, args.baseline, args.season_before, args.season_after, args.sql)
    except (OSError, sqlite3.Error) as error:
        report = {'ok': False, 'error': str(error)}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Validation : {'OK' if report['ok'] else 'ÉCHEC'}, rapport {out}")
    return 0 if report['ok'] else 2


if __name__ == '__main__':
    sys.exit(main())
