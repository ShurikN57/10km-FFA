#!/usr/bin/env python3
"""Construit la base complète du comparateur (SQLite, schéma D1 de production).

Entrées :
  - la référence (data/reference/) : un profil par athlète et par distance,
    meilleure performance des saisons qu'elle couvre (2024 à 2026 à ce jour) ;
  - éventuellement les exports bruts V3 d'une saison suivante (collecte
    tools/ffa-collecte-bilans.js), contrôlés puis fusionnés dans la référence.

Sorties : un fichier SQLite avec toutes les tables lues par api/worker.js
(athletes, recherche plein texte, rangs, périmètres, options, totaux), et sur
demande le SQL d'import pour une nouvelle base D1 ou la référence prolongée.

Usage :
  python3 tools/build_db.py --out build/ffa.db
  python3 tools/build_db.py --out build/ffa.db --sql build/ffa.sql --season 2027 --raw data/exports/2027/*.json.gz
  python3 tools/build_db.py --out build/ffa.db --fingerprints   # empreintes de contrôle
  # Fin de saison : prolonger la référence (2024–2026 → 2024–2027)
  python3 tools/build_db.py --out build/ffa.db --season 2027 --raw data/exports/2027/*.json.gz --write-reference data/reference

Code de sortie 2 si la référence ou les exports sont invalides ou incomplets
(aucune base produite).

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
# Garde-fou : temps impossibles (erreurs de saisie), juste sous les records du
# monde sur route (12'49'', 26'24'', 57'30'', 2h00'35''). Aucun profil de la
# référence n'est concerné.
MIN_PB = {'5k': 12 * 60, '10k': 25 * 60, 'semi': 55 * 60, 'marathon': 115 * 60}
RANK_SEASON_BEFORE = 2026
RANK_SEASON_AFTER = 2027

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

REFERENCE_FORMAT = 'rp-reference-v2'
REFERENCE_COLUMNS = ['full_name', 'birth_year', 'sex', 'pb_sec', 'pb_date', 'club', 'athlete_ffa_id', 'league', 'department']


class InputError(Exception):
    """Entrée invalide ou incomplète : aucune base n'est produite."""


def rank_seasons_for(season, before=None, after=None):
    """Refuse une nouvelle saison si ses catégories n'ont pas été préparées."""
    before = RANK_SEASON_BEFORE if before is None else before
    after = RANK_SEASON_AFTER if after is None else after
    if after != before + 1:
        raise InputError('Les deux saisons de catégories doivent être consécutives.')
    if int(season) > after:
        raise InputError(f'Saison {season} plus récente que les catégories préparées ({before}/{after}) : '
                         'adapter les saisons de classement avant de reconstruire.')
    return before, after


def load_reference(directory=REFERENCE_DIR):
    """Profils de référence par distance, et saisons couvertes.

    Un fichier par distance : ffa_<distance>_<première>_<dernière>.json.gz. Les
    saisons sont lues dans les fichiers et doivent être les mêmes partout.
    """
    profiles, seasons, problems = {}, None, []
    for key, file_label, _ in DISTANCES:
        files = sorted(Path(directory).glob(f'ffa_{file_label}_*.json.gz'))
        if len(files) != 1:
            problems.append(f'{file_label} : {len(files)} fichier(s) de référence au lieu d\'un seul')
            continue
        with gzip.open(files[0], 'rt', encoding='utf-8') as f:
            doc = json.load(f)
        if doc.get('format') != REFERENCE_FORMAT or doc.get('distance') != key:
            problems.append(f'{files[0].name} : format ou distance inattendus')
            continue
        if doc.get('columns') != REFERENCE_COLUMNS:
            problems.append(f'{files[0].name} : colonnes inattendues')
            continue
        file_seasons = sorted(int(x) for x in doc.get('seasons', []))
        if seasons is None:
            seasons = file_seasons
        elif file_seasons != seasons:
            problems.append(f'{files[0].name} : saisons {file_seasons} différentes des autres distances {seasons}')
        profiles[key] = [dict(zip(REFERENCE_COLUMNS, row)) for row in doc['rows']]
    if problems:
        raise InputError('Référence invalide :\n  ' + '\n  '.join(problems))
    return profiles, seasons


def write_reference(profiles, seasons, directory, source):
    """Écrit une nouvelle référence (prolongation en fin de saison), puis retire
    l'ancienne. Les fichiers sont d'abord écrits sous un nom temporaire."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    tag = f'{seasons[0]}_{seasons[-1]}'
    written = []
    for key, file_label, _ in DISTANCES:
        rows = [[p.get(c) for c in REFERENCE_COLUMNS] for p in profiles[key]]
        doc = {'format': REFERENCE_FORMAT, 'distance': key, 'seasons': seasons, 'source': source,
               'columns': REFERENCE_COLUMNS, 'rows': rows}
        tmp = directory / f'ffa_{file_label}_{tag}.json.gz.tmp'
        with gzip.open(tmp, 'wt', encoding='utf-8', compresslevel=9) as f:
            json.dump(doc, f, ensure_ascii=False, separators=(',', ':'))
        written.append((tmp, directory / f'ffa_{file_label}_{tag}.json.gz'))
    for key, file_label, _ in DISTANCES:
        for old in directory.glob(f'ffa_{file_label}_*.json.gz'):
            old.unlink()
    for tmp, final in written:
        tmp.rename(final)
    return [final for _, final in written]


# --- Exports bruts V3 (tools/ffa-collecte-bilans.js) ---------------------------

RAW_SCHEMA_VERSION = 3
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


def load_raw(paths, seasons):
    """Performances des exports bruts, par distance, avec un rapport de lecture.

    Contrôle d'exhaustivité avant toute lecture des lignes : version de schéma,
    les 4 distances (une fois chacune), et pour chacune exactement les bilans
    hommes et femmes des saisons attendues, non vides. Lève InputError sinon.
    """
    seasons = sorted(int(x) for x in seasons)
    expected = {(year, sex) for year in seasons for sex in ('M', 'F')}
    perfs = {key: [] for key, _, _ in DISTANCES}
    report = {'files': [], 'rows': 0, 'unreadable': 0, 'too_fast': 0, 'examples': []}
    docs, problems = {}, []
    for path in paths:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            doc = json.load(f)
        name = Path(path).name
        dist = EVENT_DISTANCE.get(str(doc.get('event'))) or LABEL_DISTANCE.get(str(doc.get('distance', '')).lower())
        if not dist:
            problems.append(f'{name} : distance non reconnue')
            continue
        if doc.get('schema_version') != RAW_SCHEMA_VERSION:
            problems.append(f'{name} : version de schéma {doc.get("schema_version")!r}, attendu {RAW_SCHEMA_VERSION}')
        if 'seasons' in doc and sorted(int(x) for x in doc['seasons']) != seasons:
            problems.append(f'{name} : saisons {doc["seasons"]} au lieu de {seasons}')
        if dist in docs:
            problems.append(f'{name} : deuxième export pour {dist} ({docs[dist][0]})')
            continue
        datasets = doc.get('datasets') or []
        found = [(int(ds.get('year', 0)), ds.get('sex')) for ds in datasets]
        if sorted(found) != sorted(expected) or len(found) != len(set(found)):
            missing = sorted(expected - set(found))
            extra = sorted(set(found) - expected)
            problems.append(f'{name} : bilans attendus {sorted(expected)} ; manquants {missing}, en trop {extra}'
                            + (', doublons' if len(found) != len(set(found)) else ''))
        for ds in datasets:
            if not ds.get('rows'):
                problems.append(f'{name} : bilan {ds.get("year")} {ds.get("sex")} vide')
        docs[dist] = (name, doc)
    for key, _, _ in DISTANCES:
        if key not in docs:
            problems.append(f'export manquant pour la distance {key}')
    if problems:
        raise InputError('Exports bruts incomplets ou invalides, aucune base produite :\n  ' + '\n  '.join(problems))

    for key, _, _ in DISTANCES:
        name, doc = docs[key]
        n = 0
        for ds in doc['datasets']:
            sex = ds['sex']
            for r in ds['rows']:
                report['rows'] += 1
                sec, full_name = parse_time(r[0]), str(r[1] or '').strip()
                if sec is None or not full_name:
                    report['unreadable'] += 1
                    if len(report['examples']) < 5:
                        report['examples'].append(r[:2])
                    continue
                if sec < MIN_PB[key]:
                    # Temps impossible (erreur de saisie) : écarté avant la fusion
                    # pour ne pas écraser le vrai record de l'athlète.
                    report['too_fast'] += 1
                    continue
                birth = str(r[8] or '').strip() if len(r) > 8 else ''
                perfs[key].append({
                    'full_name': full_name, 'birth_year': int(birth) if birth.isdigit() else None, 'sex': sex,
                    'pb_sec': sec, 'pb_date': parse_date(r[6]), 'club': str(r[2] or '').strip() or None,
                    'athlete_ffa_id': (str(r[9]).strip() or None) if len(r) > 9 and r[9] else None,
                    'league': str(r[3] or '').strip() or None, 'department': str(r[4] or '').strip() or None,
                    'season': int(ds['year']),
                })
                n += 1
        report['files'].append((name, key, n))
    return perfs, report


# --- Fusion ----------------------------------------------------------------------

def identity(p):
    """Un athlète = son identifiant FFA, sinon nom normalisé + année + sexe."""
    if p.get('athlete_ffa_id'):
        return ('id', str(p['athlete_ffa_id']))
    return nbs_key(p)


def nbs_key(p):
    return ('nbs', name_key(p['full_name']), p.get('birth_year'), p.get('sex'))


def _date_order(d):
    """JJ/MM/AA → AAMMJJ pour trier ; date absente en dernier."""
    return d[6:8] + d[3:5] + d[0:2] if d and len(d) == 8 else '999999'


def perf_order(p):
    """Ordre total entre performances : temps, puis date, puis champs texte.
    Rend le choix du meilleur résultat indépendant de l'ordre des fichiers.
    Le nom original vient en dernier : deux graphies d'un même nom normalisé
    (« Éloïse MARTIN » / « ELOISE MARTIN ») sont ainsi toujours départagées
    de la même façon."""
    return (int(p['pb_sec']), _date_order(p.get('pb_date')), name_key(p.get('full_name')),
            str(p.get('athlete_ffa_id') or ''), str(p.get('club') or ''), str(p.get('league') or ''),
            str(p.get('department') or ''), p.get('birth_year') or 0, str(p.get('full_name') or ''))


def merge(profiles, perfs):
    """Fusionne les performances brutes dans les profils (meilleur temps conservé).

    Deux temps, pour un résultat indépendant de l'ordre des entrées :
      1. chaque athlète entrant est rattaché à un profil, en ne consultant que la
         référence et l'ensemble des athlètes entrants (jamais un profil créé
         pendant la fusion) ;
      2. les mises à jour et créations sont appliquées.
    Un résultat sans identifiant qui peut correspondre à plusieurs athlètes est
    écarté et signalé (stats['ambiguous']), jamais attribué arbitrairement.
    """
    out = {}
    stats = {'improved': 0, 'new': 0, 'unchanged': 0, 'linked_id': 0, 'ambiguous': 0, 'ambiguous_examples': []}
    for key, _, _ in DISTANCES:
        plist = [dict(p) for p in profiles[key]]
        ref_by_id, ref_by_nbs = {}, {}
        for i, p in enumerate(plist):
            if p.get('athlete_ffa_id'):
                ref_by_id.setdefault(str(p['athlete_ffa_id']), i)
            ref_by_nbs.setdefault(nbs_key(p), []).append(i)

        # Meilleure performance de la saison pour chaque athlète entrant.
        best = {}
        for perf in perfs.get(key, []):
            k = identity(perf)
            if k not in best or perf_order(perf) < perf_order(best[k]):
                best[k] = perf

        # 1. Rattachements, calculés sur des ensembles fixes.
        unmatched_ids = {k: perf for k, perf in best.items() if k[0] == 'id' and k[1] not in ref_by_id}
        claims = {}  # nom/année/sexe → identifiants entrants inconnus de la référence
        for k, perf in unmatched_ids.items():
            claims.setdefault(nbs_key(perf), []).append(k)
        target = {}  # identité entrante → ('ref', index) | ('new', identité)
        linked = set()
        ambiguous = []
        for k, perf in best.items():
            n = nbs_key(perf)
            ref_cands = ref_by_nbs.get(n, [])
            ref_noid = [i for i in ref_cands if not plist[i].get('athlete_ffa_id')]
            if k[0] == 'id':
                if k[1] in ref_by_id:
                    target[k] = ('ref', ref_by_id[k[1]])
                elif len(ref_noid) == 1 and len(claims.get(n, [])) == 1:
                    # Nouvel identifiant relié au seul profil sans identifiant de
                    # même nom, année et sexe, et réclamé par ce seul identifiant.
                    target[k] = ('ref', ref_noid[0])
                    linked.add(k)
                else:
                    target[k] = ('new', k)
            else:
                if len(ref_noid) == 1:
                    target[k] = ('ref', ref_noid[0])
                elif len(ref_noid) > 1:
                    target[k] = None
                else:
                    # Profils identifiés possibles : ceux de la référence et les
                    # nouveaux identifiants entrants de même nom, année et sexe.
                    possible = {('ref', i) for i in ref_cands}
                    possible |= {('new', c) for c in claims.get(n, []) if c not in linked}
                    if len(possible) == 1:
                        target[k] = possible.pop()
                    elif not possible:
                        target[k] = ('new', k)
                    else:
                        target[k] = None
            if target[k] is None:
                stats['ambiguous'] += 1
                ambiguous.append((perf['full_name'], perf.get('birth_year'), perf.get('sex'), perf['pb_sec']))

        stats['ambiguous_examples'] = sorted(stats['ambiguous_examples'] + ambiguous, key=lambda x: (str(x[0]), x[1] or 0, x[2] or '', x[3]))[:10]

        # 2. Application : pour chaque profil cible, le meilleur résultat entrant.
        groups = {}
        for k, t in target.items():
            if t is not None:
                groups.setdefault(t, []).append(best[k])
        new_profiles = []
        for t in sorted(groups, key=lambda t: (t[0], t[1] if t[0] == 'ref' else repr(t[1]))):
            incoming = sorted(groups[t], key=perf_order)
            top = incoming[0]
            births = [p['birth_year'] for p in incoming if p.get('birth_year') is not None]
            ids = sorted({str(p['athlete_ffa_id']) for p in incoming if p.get('athlete_ffa_id')})
            if t[0] == 'new':
                new = {c: top.get(c) for c in REFERENCE_COLUMNS}
                if new.get('birth_year') is None and births:
                    new['birth_year'] = births[0]
                if not new.get('athlete_ffa_id') and len(ids) == 1:
                    new['athlete_ffa_id'] = ids[0]
                new_profiles.append(new)
                stats['new'] += 1
                continue
            p = plist[t[1]]
            if not p.get('athlete_ffa_id') and len(ids) == 1:
                p['athlete_ffa_id'] = ids[0]
                stats['linked_id'] += 1
            if p.get('birth_year') is None and births:
                p['birth_year'] = births[0]
            if int(top['pb_sec']) < int(p['pb_sec']):
                for c in ('pb_sec', 'pb_date', 'club', 'league', 'department'):
                    p[c] = top.get(c)
                stats['improved'] += 1
            else:
                stats['unchanged'] += 1
        new_profiles.sort(key=lambda p: (name_key(p['full_name']), p.get('birth_year') or 0, p.get('sex') or '',
                                         str(p.get('athlete_ffa_id') or ''), perf_order(p)))
        out[key] = plist + new_profiles
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
            if pb <= 0 or pb < MIN_PB[key]:
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


def build(out, profiles, season_before=RANK_SEASON_BEFORE, season_after=RANK_SEASON_AFTER):
    """Construit la base SQLite complète à partir des profils."""
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
    ap.add_argument('--reference', default=str(REFERENCE_DIR), help='dossier de la référence (défaut data/reference)')
    ap.add_argument('--raw', nargs='*', default=[], help='exports bruts V3 à fusionner (4 fichiers, un par distance)')
    ap.add_argument('--season', type=int, action='append', default=[],
                    help='saison attendue dans les exports (obligatoire avec --raw ; répétable)')
    ap.add_argument('--season-before', type=int, default=RANK_SEASON_BEFORE, help='saison des rangs « avant septembre »')
    ap.add_argument('--season-after', type=int, default=RANK_SEASON_AFTER, help='saison des rangs « après septembre »')
    ap.add_argument('--sql', help='écrit aussi le SQL complet pour une nouvelle base D1')
    ap.add_argument('--write-reference', metavar='DOSSIER',
                    help='écrit la référence prolongée (référence + saisons fusionnées) : fin de saison uniquement')
    ap.add_argument('--fingerprints', action='store_true', help='affiche les empreintes de contrôle')
    ap.add_argument('--max-unreadable', type=float, default=0.005, help='part maximale de lignes illisibles (défaut 0,5 %%)')
    args = ap.parse_args(argv)
    t = time.time()
    try:
        profiles, ref_seasons = load_reference(args.reference)
        print(f'Référence : saisons {ref_seasons[0]}–{ref_seasons[-1]}')
        seasons = ref_seasons
        if args.raw:
            if not args.season:
                raise InputError('--season est obligatoire avec --raw (ex. --season 2027).')
            overlap = sorted(set(args.season) & set(ref_seasons))
            if overlap:
                raise InputError(f'Saison(s) {overlap} déjà dans la référence : la fusionner à nouveau est refusé.')
            for season in args.season:
                rank_seasons_for(season, args.season_before, args.season_after)
            perfs, report = load_raw(args.raw, args.season)
            for name, dist, n in report['files']:
                print(f'  {name} : {dist}, {n:,} performances')
            share = report['unreadable'] / max(1, report['rows'])
            print(f'  lignes illisibles : {report["unreadable"]:,} / {report["rows"]:,} ({share:.2%}) {report["examples"]}')
            print(f'  temps impossibles écartés : {report["too_fast"]:,}')
            if share > args.max_unreadable:
                raise InputError('Trop de lignes illisibles : format de l\'export à vérifier.')
            profiles, stats = merge(profiles, perfs)
            print(f'  fusion : {stats["improved"]:,} records améliorés, {stats["new"]:,} nouveaux profils, '
                  f'{stats["unchanged"]:,} inchangés, {stats["linked_id"]:,} identifiants FFA reliés')
            print(f'  résultats ambigus écartés (homonymes) : {stats["ambiguous"]:,} {stats["ambiguous_examples"]}')
            seasons = sorted(set(ref_seasons) | set(args.season))
        elif args.write_reference:
            raise InputError('--write-reference demande des exports (--raw) à fusionner.')
    except InputError as e:
        print(e, file=sys.stderr)
        return 2
    db, n = build(args.out, profiles, args.season_before, args.season_after)
    print(f'{n:,} profils, base écrite dans {args.out} ({os.path.getsize(args.out) // 2**20} Mo, {time.time() - t:.0f} s)')
    if args.sql:
        export_sql(db, args.sql)
        print(f'SQL pour une nouvelle base D1 : {args.sql} ({os.path.getsize(args.sql) // 2**20} Mo)')
    if args.write_reference:
        files = write_reference(profiles, seasons, args.write_reference,
                                f'Référence {ref_seasons[0]}–{ref_seasons[-1]} prolongée avec la saison {args.season}')
        print('Référence prolongée : ' + ', '.join(str(f) for f in files))
    if args.fingerprints:
        print(json.dumps(fingerprints(db), ensure_ascii=False))
    db.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
