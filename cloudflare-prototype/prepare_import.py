#!/usr/bin/env python3
import gzip, json, re, unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).with_name('ffa_d1_import.sql')
SOURCES = [
    ('5k', ROOT / 'ffa_5km_2024_2026.json.gz'),
    ('10k', ROOT / 'ffa_base.json.gz'),
]

def name_key(value):
    s = unicodedata.normalize('NFD', str(value or ''))
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn').upper()
    s = re.sub(r'[^A-Z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()

def sql(v):
    if v is None or v == '': return 'NULL'
    if isinstance(v, (int, float)): return str(int(v))
    return "'" + str(v).replace("'", "''") + "'"

def rows_from(path):
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get('rows', [])

count = 0
with OUT.open('w', encoding='utf-8', newline='\n') as out:
    out.write('BEGIN TRANSACTION;\n')
    for distance, path in SOURCES:
        if not path.exists():
            raise SystemExit(f'Missing source: {path}')
        for r in rows_from(path):
            if not isinstance(r, list) or len(r) < 8: continue
            pb = int(r[3] or 0)
            if pb <= 0: continue
            if distance == '5k' and pb < 720: continue
            vals = [distance, r[0], name_key(r[0]), r[1], r[2], pb, r[4], r[5], r[6], r[7]]
            out.write('INSERT INTO athletes(distance,full_name,name_key,birth_year,sex,pb_sec,pb_course,pb_date,club,athlete_ffa_id) VALUES(')
            out.write(','.join(sql(v) for v in vals))
            out.write(');\n')
            count += 1
    out.write('COMMIT;\n')

print(f'{count:,} rows written to {OUT}')
print('Import with: npx wrangler d1 execute ffa-comparateur --remote --file cloudflare-prototype/ffa_d1_import.sql')
