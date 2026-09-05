#!/usr/bin/env python3
import gzip, json, re, unicodedata
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).with_name('ffa_d1_import.sql')
SOURCES = [
    ('5k', ROOT / 'ffa_5km_2024_2026.json.gz'),
    ('10k', ROOT / 'ffa_base.json.gz'),
    ('semi', ROOT / 'ffa_semi_2024_2026.json.gz'),
    ('marathon', ROOT / 'ffa_marathon_2024_2026.json.gz'),
]

# Profils officiellement vérifiés mais non liés dans les bilans FFA
# (notamment certains participants enregistrés avec un PPS).
PROFILE_ID_OVERRIDES = {
    ('semi', 'BITTEROLF THOMAS', '', 'M'): '3611328',
}


def name_key(value):
    s = unicodedata.normalize('NFD', str(value or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').upper()
    s = re.sub(r'[^A-Z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def identity_key(row):
    return (name_key(row[0]), str(row[1] or ''), str(row[2] or '').upper())


def sql(v):
    if v is None or v == '':
        return 'NULL'
    if isinstance(v, (int, float)):
        return str(int(v))
    return "'" + str(v).replace("'", "''") + "'"


def rows_from(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get('rows', [])


for _, path in SOURCES:
    if not path.exists():
        raise SystemExit(f'Missing source: {path}')

# Un identifiant présent sur une autre distance est réutilisé seulement si
# nom normalisé + année de naissance + sexe conduisent à un ID unique.
identity_ids = defaultdict(set)
for _, path in SOURCES:
    for row in rows_from(path):
        if isinstance(row, list) and len(row) >= 8 and row[7]:
            identity_ids[identity_key(row)].add(str(row[7]).strip())

unique_identity_ids = {
    key: next(iter(ids))
    for key, ids in identity_ids.items()
    if len(ids) == 1
}

count = 0
backfilled = 0
overridden = 0
with OUT.open('w', encoding='utf-8', newline='\n') as out:
    out.write('BEGIN TRANSACTION;\n')
    for distance, path in SOURCES:
        for r in rows_from(path):
            if not isinstance(r, list) or len(r) < 8:
                continue
            pb = int(r[3] or 0)
            if pb <= 0:
                continue
            if distance == '5k' and pb < 720:
                continue

            athlete_id = str(r[7] or '').strip()
            if not athlete_id:
                override_key = (
                    distance,
                    name_key(r[0]),
                    str(r[1] or ''),
                    str(r[2] or '').upper(),
                )
                athlete_id = PROFILE_ID_OVERRIDES.get(override_key, '')
                if athlete_id:
                    overridden += 1
                else:
                    athlete_id = unique_identity_ids.get(identity_key(r), '')
                    if athlete_id:
                        backfilled += 1

            vals = [
                distance, r[0], name_key(r[0]), r[1], r[2], pb,
                r[4], r[5], r[6], athlete_id,
            ]
            out.write(
                'INSERT INTO athletes(distance,full_name,name_key,birth_year,sex,'
                'pb_sec,pb_course,pb_date,club,athlete_ffa_id) VALUES('
            )
            out.write(','.join(sql(v) for v in vals))
            out.write(');\n')
            count += 1
    out.write('COMMIT;\n')

print(f'{count:,} rows written to {OUT}')
print(f'{backfilled:,} missing profile IDs propagated safely across distances')
print(f'{overridden:,} verified profile ID overrides applied')
print('Import with: npx wrangler d1 execute ffa-comparateur --remote --file cloudflare-prototype/ffa_d1_import.sql')
