#!/usr/bin/env python3
"""Construit la base complète du comparateur (SQLite, schéma D1 de production).

Entrées :
  - la référence figée (data/reference/*.json.gz) : un profil par athlète et
    par distance, meilleure performance des saisons 2024 à 2026 ;
  - éventuellement les exports bruts V3 d'une nouvelle saison (collecte
    tools/ffa-auto-24-v3.js), fusionnés dans la référence.

Sortie : un fichier SQLite avec toutes les tables lues par api/worker.js
(athletes, recherche plein texte, rangs, périmètres, options, totaux).

Usage :
  python3 tools/build_db.py --out build/ffa.db
  python3 tools/build_db.py --out build/ffa.db --raw exports/ffa_*_2027.json.gz
  python3 tools/build_db.py --out build/ffa.db --fingerprints   # empreintes de contrôle

Aucune dépendance hors bibliothèque standard (Python 3.9+).
"""
import argparse
import gzip
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = ROOT / 'data' / 'reference'
SCHEMA = ROOT / 'api' / 'schema.sql'
MIGRATIONS = ROOT / 'api' / 'migrations'

DISTANCES = [  # ordre d'insertion = ordre des identifiants en production
    ('5k', '5km', '5 km'),
    ('10k', '10km', '10 km'),
    ('semi', 'semi', 'Semi-marathon'),
    ('marathon', 'marathon', 'Marathon'),
]
DISTANCE_LABEL = {key: label for key, _, label in DISTANCES}
MIN_PB = {'5k': 720}  # garde-fou : chronos impossibles (< 12 min sur 5 km)

# Catégories FFA : âge atteint pendant l'année de fin de saison.
CATEGORY_AGES = [
    ('CA', 16, 17), ('JU', 18, 19), ('ES', 20, 22), ('SE', 23, 34),
    ('M0', 35, 39), ('M1', 40, 44), ('M2', 45, 49), ('M3', 50, 54),
    ('M4', 55, 59), ('M5', 60, 64), ('M6', 65, 69), ('M7', 70, 74),
    ('M8', 75, 79), ('M9', 80, 84), ('M10', 85, None),
]
FRENCH_SQL = "full_name NOT GLOB '* ([A-Z][A-Z][A-Z])'"


def name_key(value):
    """Nom normalisé, ordre des mots conservé (identique à api/worker.js)."""
    s = unicodedata.normalize('NFD', str(value or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').upper()
    s = re.sub(r'[^A-Z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def category(birth_year, season):
    if birth_year is None:
        return None
    age = season - int(birth_year)
    for code, lo, hi in CATEGORY_AGES:
        if age >= lo and (hi is None or age <= hi):
            return code
    return None


# --- Référence ----------------------------------------------------------------

def load_reference(directory=REFERENCE_DIR):
    """Profils de référence, par distance, dans l'ordre des fichiers."""
    profiles = {}
    for key, file_label, _ in DISTANCES:
        path = Path(directory) / f'ffa_{file_label}_2024_2026.json.gz'
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            doc = json.load(f)
        cols = doc['columns']
        profiles[key] = [dict(zip(cols, row)) for row in doc['rows']]
    return profiles


# --- Exports bruts V3 (tools/ffa-collecte-bilans.js) ---------------------------

EVENT_DISTANCE = {'252': '5k', '261': '10k', '271': 'semi', '295': 'marathon'}
LABEL_DISTANCE = {'5 km': '5k', '10 km': '10k', 'semi-marathon': 'semi', 'marathon': 'marathon'}


def parse_time(text):
    """Performance FFA en secondes : 33'05'', 1h13'26'', 1:13:26, 33:05."""
    s = str(text or '').strip()
    m = re.search(r"(?:(\d{1,2})\s*h\s*)?(\d{1,3})\s*'\s*(\d{1,2})", s)
    if m:
        return int(m.group(1) or 0) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.match(r'^(\d{1,2}):(\d{2}):(\d{2})', s)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.match(r'^(\d{1,3}):(\d{2})(?:[.,]\d+)?$', s)
    if m:
        return int(m.group(1)) * 60 + int(m.group(2))
    m = re.match(r'^(\d{1,2})h(\d{2})$', s)  # 2h05 (minutes rondes)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60
    return None


def parse_date(text):
    """Date au format de la référence : JJ/MM/AA."""
    m = re.match(r'^(\d{1,2})/(\d{1,2})/(\d{2}|\d{4})$', str(text or '').strip())
    if not m:
        return None
    return f'{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)[-2:]}'


def load_raw(paths):
    """Performances des exports bruts, par distance, avec un rapport de lecture."""
    perfs = {key: [] for key, _, _ in DISTANCES}
    report = {'files': [], 'rows': 0, 'unreadable': 0, 'too_fast': 0, 'examples': []}
    for path in paths:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            doc = json.load(f)
        dist = EVENT_DISTANCE.get(str(doc.get('event'))) or LABEL_DISTANCE.get(str(doc.get('distance', '')).lower())
        if not dist:
            raise SystemExit(f'{path} : distance non reconnue')
        n = 0
        for ds in doc.get('datasets', []):
            sex = ds.get('sex')
            for r in ds.get('rows', []):
                report['rows'] += 1
                sec, name = parse_time(r[0]), str(r[1] or '').strip()
                if sec is None or not name:
                    report['unreadable'] += 1
                    if len(report['examples']) < 5:
                        report['examples'].append(r[:2])
                    continue
                if sec < MIN_PB.get(dist, 0):
                    # Temps impossible (erreur de saisie) : écarté avant la fusion
                    # pour ne pas écraser le vrai record de l'athlète.
                    report['too_fast'] += 1
                    continue
                birth = str(r[8] or '').strip() if len(r) > 8 else ''
                perfs[dist].append({
                    'full_name': name, 'birth_year': int(birth) if birth.isdigit() else None, 'sex': sex,
                    'pb_sec': sec, 'pb_date': parse_date(r[6]), 'club': str(r[2] or '').strip() or None,
                    'athlete_ffa_id': (str(r[9]).strip() or None) if len(r) > 9 and r[9] else None,
                    'league': str(r[3] or '').strip() or None, 'department': str(r[4] or '').strip() or None,
                    'season': ds.get('year'),
                })
                n += 1
        report['files'].append((str(path), dist, n))
    return perfs, report


def identity(p):
    """Un athlète = son identifiant FFA, sinon nom normalisé + année + sexe."""
    if p.get('athlete_ffa_id'):
        return ('id', str(p['athlete_ffa_id']))
    return ('nbs', name_key(p['full_name']), p.get('birth_year'), p.get('sex'))


def merge(profiles, perfs):
    """Fusionne les performances brutes dans les profils (meilleur temps conservé).

    Retourne les nouveaux profils et le nombre de profils améliorés / créés.
    """
    out = {}
    stats = {'improved': 0, 'new': 0, 'unchanged': 0, 'linked_id': 0}
    for key, _, _ in DISTANCES:
        plist = [dict(p) for p in profiles[key]]
        nbs = lambda p: ('nbs', name_key(p['full_name']), p.get('birth_year'), p.get('sex'))
        by_id, by_nbs = {}, {}  # by_nbs : tous les profils (avec ou sans identifiant)
        for p in plist:
            if p.get('athlete_ffa_id'):
                by_id.setdefault(str(p['athlete_ffa_id']), p)
            by_nbs.setdefault(nbs(p), []).append(p)
        # Meilleure performance de la nouvelle saison pour chaque athlète.
        best = {}
        for perf in perfs.get(key, []):
            k = identity(perf)
            if k not in best or perf['pb_sec'] < best[k]['pb_sec']:
                best[k] = perf
        for k, perf in best.items():
            cands = by_nbs.get(nbs(perf), [])
            without_id = [c for c in cands if not c.get('athlete_ffa_id')]
            p = None
            if k[0] == 'id':
                p = by_id.get(k[1])
                if p is None and len(without_id) == 1:
                    # Profil connu sans identifiant (même nom, année, sexe) : relié
                    # seulement s'il est unique, comme à l'import d'origine.
                    p = without_id[0]
                    p['athlete_ffa_id'] = perf['athlete_ffa_id']
                    by_id[k[1]] = p
                    stats['linked_id'] += 1
            else:
                # Sans identifiant : le profil sans identifiant de même nom, année et
                # sexe ; sinon l'unique profil identifié correspondant. En cas
                # d'ambiguïté (plusieurs homonymes identifiés), nouveau profil.
                if without_id:
                    p = without_id[0]
                elif len(cands) == 1:
                    p = cands[0]
            if p is None:
                new = {c: perf.get(c) for c in ('full_name', 'birth_year', 'sex', 'pb_sec', 'pb_date', 'club',
                                                 'athlete_ffa_id', 'league', 'department')}
                plist.append(new)
                if new['athlete_ffa_id']:
                    by_id[str(new['athlete_ffa_id'])] = new
                by_nbs.setdefault(nbs(new), []).append(new)
                stats['new'] += 1
            elif perf['pb_sec'] < int(p['pb_sec']):
                for c in ('pb_sec', 'pb_date', 'club', 'league', 'department'):
                    p[c] = perf.get(c)
                if p.get('birth_year') is None and perf.get('birth_year') is not None:
                    p['birth_year'] = perf['birth_year']
                stats['improved'] += 1
            else:
                if p.get('birth_year') is None and perf.get('birth_year') is not None:
                    p['birth_year'] = perf['birth_year']
                stats['unchanged'] += 1
        out[key] = plist
    return out, stats


# --- Construction de la base ---------------------------------------------------

def create_schema(db):
    db.executescript(SCHEMA.read_text(encoding='utf-8'))
    for migration in sorted(MIGRATIONS.glob('*.sql')):
        db.executescript(migration.read_text(encoding='utf-8'))


def insert_athletes(db, profiles):
    rows = []
    for key, _, label in DISTANCES:
        for p in profiles[key]:
            pb = int(p['pb_sec'] or 0)
            if pb <= 0 or pb < MIN_PB.get(key, 0):
                continue
            rows.append((key, p['full_name'], name_key(p['full_name']), p['birth_year'], p['sex'], pb,
                         label, p['pb_date'], p['club'], p['athlete_ffa_id'],
                         p.get('league') or '', p.get('department') or ''))
    db.execute('CREATE TEMP TABLE scope_src(id INTEGER PRIMARY KEY, league TEXT, department TEXT)')
    cur = db.cursor()
    for r in rows:
        cur.execute('INSERT INTO athletes(distance,full_name,name_key,birth_year,sex,pb_sec,pb_course,pb_date,club,athlete_ffa_id) '
                    'VALUES(?,?,?,?,?,?,?,?,?,?)', r[:10])
        cur.execute('INSERT INTO scope_src VALUES(?,?,?)', (cur.lastrowid, r[10], r[11]))
    return len(rows)


def category_case(season):
    """Expression SQL : catégorie FFA de birth_year pour une saison."""
    parts = []
    for code, lo, hi in CATEGORY_AGES:
        cond = f'{season} - birth_year >= {lo}' + (f' AND {season} - birth_year <= {hi}' if hi is not None else '')
        parts.append(f"WHEN {cond} THEN '{code}'")
    return 'CASE WHEN birth_year IS NULL THEN NULL ' + ' '.join(parts) + ' ELSE NULL END'


def build_derived(db, season_before, season_after):
    """Tables dérivées lues par le Worker. Rang = RANK() par temps croissant."""
    cat_b, cat_a = category_case(season_before), category_case(season_after)
    db.executescript(f'''
        INSERT INTO athlete_fts(rowid, name_key, distance) SELECT id, name_key, distance FROM athletes;

        INSERT INTO athlete_general_rank(athlete_id, distance, rank, display_order)
        SELECT id, distance,
               RANK() OVER (PARTITION BY distance ORDER BY pb_sec),
               ROW_NUMBER() OVER (PARTITION BY distance ORDER BY pb_sec, full_name, id)
        FROM athletes;

        -- Rang parmi TOUS les athlètes de la distance (vérifié sur la production),
        -- limité aux athlètes sans suffixe de nationalité.
        INSERT INTO athlete_french_rank(athlete_id, distance, rank_general)
        SELECT a.id, a.distance, g.rank
        FROM athletes a JOIN athlete_general_rank g ON g.athlete_id = a.id
        WHERE a.{FRENCH_SQL};

        CREATE TEMP TABLE cats AS
        SELECT id, distance, sex, pb_sec, birth_year, {cat_b} AS cat_b, {cat_a} AS cat_a FROM athletes;

        INSERT INTO athlete_search_rank(athlete_id, rank_general, rank_sex, rank_cat_before_sep, rank_cat_after_sep)
        SELECT id,
               RANK() OVER (PARTITION BY distance ORDER BY pb_sec),
               RANK() OVER (PARTITION BY distance, sex ORDER BY pb_sec),
               CASE WHEN cat_b IS NULL THEN NULL ELSE RANK() OVER (PARTITION BY distance, sex, cat_b ORDER BY pb_sec) END,
               CASE WHEN cat_a IS NULL THEN NULL ELSE RANK() OVER (PARTITION BY distance, sex, cat_a ORDER BY pb_sec) END
        FROM cats;

        INSERT INTO athlete_rank_cat_before(athlete_id, rank_category)
        SELECT id, RANK() OVER (PARTITION BY distance, cat_b ORDER BY pb_sec) FROM cats WHERE cat_b IS NOT NULL;

        INSERT INTO athlete_rank_cat_after(athlete_id, rank_category)
        SELECT id, RANK() OVER (PARTITION BY distance, cat_a ORDER BY pb_sec) FROM cats WHERE cat_a IS NOT NULL;

        INSERT INTO athlete_rank_year(athlete_id, rank_year, rank_sex_year)
        SELECT id,
               RANK() OVER (PARTITION BY distance, birth_year ORDER BY pb_sec),
               RANK() OVER (PARTITION BY distance, birth_year, sex ORDER BY pb_sec)
        FROM athletes;

        INSERT INTO athlete_scope(athlete_id, distance, league, department, race_year)
        SELECT a.id, a.distance, s.league, s.department,
               CASE WHEN a.pb_date GLOB '[0-9][0-9]/[0-9][0-9]/[0-9][0-9]' THEN 2000 + CAST(substr(a.pb_date, 7, 2) AS INTEGER) END
        FROM athletes a JOIN scope_src s ON s.id = a.id;

        INSERT INTO ffa_scope_options(distance, league, department, club, race_year)
        SELECT DISTINCT a.distance, s.league, s.department, COALESCE(a.club, ''), s.race_year
        FROM athletes a JOIN athlete_scope s ON s.athlete_id = a.id;

        INSERT INTO ffa_distance_stats(distance, total) SELECT distance, COUNT(*) FROM athletes GROUP BY distance;
        INSERT INTO ffa_french_stats(distance, total) SELECT distance, COUNT(*) FROM athletes WHERE {FRENCH_SQL} GROUP BY distance;
    ''')


def build(out, profiles, season_before=2026, season_after=2027):
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    db = sqlite3.connect(out)
    db.execute('PRAGMA journal_mode = OFF')
    db.execute('PRAGMA synchronous = OFF')
    create_schema(db)
    n = insert_athletes(db, profiles)
    build_derived(db, season_before, season_after)
    db.commit()
    return db, n


# --- Export SQL pour une nouvelle base D1 ----------------------------------------

EXPORT_TABLES = [
    ('athletes', 'id,distance,full_name,name_key,birth_year,sex,pb_sec,pb_course,pb_date,club,athlete_ffa_id'),
    ('athlete_general_rank', 'athlete_id,distance,rank,display_order'),
    ('athlete_french_rank', 'athlete_id,distance,rank_general'),
    ('athlete_search_rank', 'athlete_id,rank_general,rank_sex,rank_cat_before_sep,rank_cat_after_sep'),
    ('athlete_rank_cat_before', 'athlete_id,rank_category'),
    ('athlete_rank_cat_after', 'athlete_id,rank_category'),
    ('athlete_rank_year', 'athlete_id,rank_year,rank_sex_year'),
    ('athlete_scope', 'athlete_id,distance,league,department,race_year'),
    ('ffa_scope_options', 'distance,league,department,club,race_year'),
    ('ffa_distance_stats', 'distance,total'),
    ('ffa_french_stats', 'distance,total'),
]


def sql_value(v):
    if v is None:
        return 'NULL'
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def export_sql(db, path, batch=500):
    """Fichier SQL complet (schéma + données) pour une base D1 VIDE :
    npx wrangler d1 execute <nouvelle-base> --remote --file <fichier>."""
    with open(path, 'w', encoding='utf-8', newline='\n') as out:
        out.write('-- Base complète du comparateur, générée par tools/build_db.py.\n')
        out.write('-- À importer dans une base D1 vide (jamais dans la base en service).\n')
        out.write(SCHEMA.read_text(encoding='utf-8'))
        for migration in sorted(MIGRATIONS.glob('*.sql')):
            out.write('\n' + migration.read_text(encoding='utf-8'))
        out.write('\n')
        for table, cols in EXPORT_TABLES + [('athlete_fts', 'rowid,name_key,distance')]:
            q = f'SELECT {cols} FROM {table}' if table != 'athlete_fts' else 'SELECT id,name_key,distance FROM athletes'
            rows = db.execute(q)
            while True:
                chunk = rows.fetchmany(batch)
                if not chunk:
                    break
                out.write(f'INSERT INTO {table}({cols}) VALUES ' +
                          ','.join('(' + ','.join(sql_value(v) for v in r) + ')' for r in chunk) + ';\n')


# --- Empreintes de contrôle (comparables avec la production) --------------------

FINGERPRINTS = {
    'general': 'SELECT distance, COUNT(*) n, SUM(rank) s1, SUM(rank*rank) s2, SUM((rank*athlete_id)%1000003) s3, SUM(display_order) d1, SUM((display_order*athlete_id)%1000003) d3 FROM athlete_general_rank GROUP BY distance ORDER BY distance',
    'french': 'SELECT distance, COUNT(*) n, SUM(rank_general) s1, SUM((rank_general*athlete_id)%1000003) s3 FROM athlete_french_rank GROUP BY distance ORDER BY distance',
    'search': 'SELECT COUNT(*) n, SUM(rank_general) g1, SUM((rank_general*athlete_id)%1000003) g3, COUNT(rank_sex) x0, SUM(rank_sex) x1, SUM((rank_sex*athlete_id)%1000003) x3, COUNT(rank_cat_before_sep) b0, SUM(rank_cat_before_sep) b1, SUM((rank_cat_before_sep*athlete_id)%1000003) b3, COUNT(rank_cat_after_sep) a0, SUM(rank_cat_after_sep) a1, SUM((rank_cat_after_sep*athlete_id)%1000003) a3 FROM athlete_search_rank',
    'cat_before': 'SELECT COUNT(*) n, COUNT(rank_category) c0, SUM(rank_category) c1, SUM((rank_category*athlete_id)%1000003) c3 FROM athlete_rank_cat_before',
    'cat_after': 'SELECT COUNT(*) n, COUNT(rank_category) c0, SUM(rank_category) c1, SUM((rank_category*athlete_id)%1000003) c3 FROM athlete_rank_cat_after',
    'year': 'SELECT COUNT(*) n, COUNT(rank_year) y0, SUM(rank_year) y1, SUM((rank_year*athlete_id)%1000003) y3, COUNT(rank_sex_year) z0, SUM(rank_sex_year) z1, SUM((rank_sex_year*athlete_id)%1000003) z3 FROM athlete_rank_year',
    'stats': "SELECT 'all' k, distance, total FROM ffa_distance_stats UNION ALL SELECT 'fr', distance, total FROM ffa_french_stats ORDER BY 1,2",
    'options': "SELECT distance, COUNT(*) n, COUNT(DISTINCT league) l, COUNT(DISTINCT department) d, COUNT(DISTINCT club) c, SUM(COALESCE(race_year,0)) y, SUM(race_year IS NULL) ynull, SUM(club='') cempty FROM ffa_scope_options GROUP BY distance ORDER BY distance",
    'fts': 'SELECT COUNT(*) n FROM athlete_fts_docsize',
}


def fingerprints(db):
    db.row_factory = sqlite3.Row
    out = {k: [dict(r) for r in db.execute(sql)] for k, sql in FINGERPRINTS.items()}
    db.row_factory = None
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--out', required=True, help='fichier SQLite à produire')
    ap.add_argument('--season-before', type=int, default=2026, help='saison des rangs « avant septembre »')
    ap.add_argument('--season-after', type=int, default=2027, help='saison des rangs « après septembre »')
    ap.add_argument('--raw', nargs='*', default=[], help='exports bruts V3 à fusionner (une saison ou plus)')
    ap.add_argument('--sql', help='écrit aussi le SQL complet pour une nouvelle base D1')
    ap.add_argument('--fingerprints', action='store_true', help='affiche les empreintes de contrôle')
    ap.add_argument('--max-unreadable', type=float, default=0.005, help='part maximale de lignes illisibles (défaut 0,5 %%)')
    args = ap.parse_args(argv)
    t = time.time()
    profiles = load_reference()
    if args.raw:
        perfs, report = load_raw(args.raw)
        for path, dist, n in report['files']:
            print(f'  {path} : {dist}, {n:,} performances')
        share = report['unreadable'] / max(1, report['rows'])
        print(f'  lignes illisibles : {report["unreadable"]:,} / {report["rows"]:,} ({share:.2%}) {report["examples"]}')
        print(f'  temps impossibles écartés : {report["too_fast"]:,}')
        if share > args.max_unreadable:
            raise SystemExit('Trop de lignes illisibles : format de l\'export à vérifier, aucune base produite.')
        profiles, stats = merge(profiles, perfs)
        print(f'  fusion : {stats["improved"]:,} records améliorés, {stats["new"]:,} nouveaux profils, '
              f'{stats["unchanged"]:,} inchangés, {stats["linked_id"]:,} identifiants FFA reliés')
    db, n = build(args.out, profiles, args.season_before, args.season_after)
    print(f'{n:,} profils, base écrite dans {args.out} ({os.path.getsize(args.out) // 2**20} Mo, {time.time() - t:.0f} s)')
    if args.sql:
        export_sql(db, args.sql)
        print(f'SQL pour une nouvelle base D1 : {args.sql} ({os.path.getsize(args.sql) // 2**20} Mo)')
    if args.fingerprints:
        print(json.dumps(fingerprints(db), ensure_ascii=False))
    db.close()


if __name__ == '__main__':
    sys.exit(main())
