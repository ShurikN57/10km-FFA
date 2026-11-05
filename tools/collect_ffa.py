#!/usr/bin/env python3
"""Collecte HTTP des bilans FFA, sans navigateur et sans accès à D1.

Le mode probe vérifie au plus 3 pages par bilan et ne produit aucun export.
Le mode full produit les quatre exports V3 consommés par build_db.py.
"""
import argparse
import gzip
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlencode, urlsplit
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from build_db import DISTANCES, EVENT_DISTANCE, RAW_SCHEMA_VERSION, InputError, load_raw

EVENTS = {distance: event for event, distance in EVENT_DISTANCE.items()}
SCHEMA = ['Performance', 'Nom', 'Club', 'Ligue', 'Dep.', 'Infos', 'Date', 'Lieu',
          'Annee naissance', 'Athlete FFA ID']
CHECKPOINT_VERSION = 1


def now():
    return datetime.now(timezone.utc).isoformat()


def current_season():
    date = datetime.now(ZoneInfo('Europe/Paris'))
    return date.year + (date.month >= 9)


def clean(value):
    return ' '.join(value.split())


class BilansParser(HTMLParser):
    """Lit uniquement la table des bilans ; tolère les balises i/b mal fermées."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.table_depth = 0
        self.cells = None
        self.cell = None
        self.rows = []
        self.text = []
        self.selected_query = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table':
            if self.table_depth or attrs.get('id') == 'ctnBilans':
                self.table_depth += 1
        if self.table_depth != 1:
            return
        if 'selected' in attrs.get('class', '').split() and attrs.get('data-url'):
            query = parse_qs(urlsplit(attrs['data-url']).query)
            if 'frmposition' in query and self.selected_query is None:
                self.selected_query = query
        if tag == 'tr':
            self.cells = []
        elif tag == 'td' and self.cells is not None:
            self.cell = {'text': [], 'id': ''}
        elif tag == 'a' and self.cell is not None:
            match = re.search(r'/athletes/([A-Z0-9]+)(?:/|$)', attrs.get('href', ''), re.I)
            if match:
                self.cell['id'] = match[1]
        elif tag == 'br':
            self.handle_data(' ')

    def handle_data(self, data):
        if self.table_depth == 1:
            self.text.append(data)
        if self.table_depth == 1 and self.cell is not None:
            self.cell['text'].append(data)

    def handle_endtag(self, tag):
        if tag == 'table':
            self.table_depth = max(0, self.table_depth - 1)
            return
        if self.table_depth != 1:
            return
        if tag == 'td' and self.cell is not None:
            self.cells.append((clean(''.join(self.cell['text'])), self.cell['id']))
            self.cell = None
        elif tag == 'tr' and self.cells is not None:
            self.rows.append(self.cells)
            self.cells = None


def parse_page(html, page, season=None, sex=None, distance=None):
    parser = BilansParser()
    parser.feed(html)
    text = clean(' '.join(parser.text))
    if season is not None:
        heading = re.search(r'\b(\d{4})\s*\|\s*[^|]+\|\s*([MF])\b', text)
        if not heading or (int(heading[1]), heading[2]) != (season, sex):
            raise InputError('Saison ou sexe du bilan reçu différents de la demande.')
    if distance is not None:
        expected = {'frmannee': str(season), 'frmepreuve': EVENTS[distance],
                    'frmsexe': sex, 'frmposition': str(page)}
        query = parser.selected_query or {}
        if any(query.get(k) != [v] for k, v in expected.items()):
            raise InputError('Le sélecteur FFA ne correspond pas au bilan demandé (distance, saison, sexe ou page).')
    pagination = re.search(r'Page\s*>\s*(\d+)\s*/\s*(\d+)\s*<', text)
    count = re.search(r'([\d ]+)\s+résultats?\b', text, re.I)
    if not pagination or not count:
        raise InputError('Pagination ou total FFA absent : page bloquée ou format modifié.')
    current, total = map(int, pagination.groups())
    expected_rows = int(count[1].replace(' ', ''))
    if current != page + 1 or not 1 <= current <= total or expected_rows < 1:
        raise InputError(f'Page reçue {current}/{total}, attendue {page + 1} ; total {expected_rows}.')
    rows = []
    for cells in parser.rows:
        if len(cells) < 9 or not re.fullmatch(r'\d+|-', cells[0][0]):
            continue
        values = [value for value, _ in cells]
        if not values[1] or not values[2]:
            raise InputError('Ligne FFA sans performance ou sans nom.')
        birth = re.search(r'/\s*(\d{2,4})\b', values[6])
        year = int(birth[1]) if birth else None
        if year is not None and year < 100:
            year += 1900 if year >= 30 else 2000
        rows.append([values[1], values[2], values[3], values[4], values[5], values[6],
                     values[7], values[8], str(year) if year is not None else '', cells[2][1]])
    if not rows:
        raise InputError('Aucune ligne FFA reconnue : export interdit.')
    return {'page': page, 'total_pages': total, 'expected_rows': expected_rows, 'rows': rows}


def page_url(season, distance, sex, page):
    return 'https://www.athle.fr/bases/liste.aspx?' + urlencode({
        'frmbase': 'bilans', 'frmmode': '1', 'frmespace': '0', 'frmannee': season,
        'frmepreuve': EVENTS[distance], 'frmsexe': sex, 'frmposition': page,
    })


def fetch_page(season, distance, sex, page, delay=1.0):
    url = page_url(season, distance, sex, page)
    for attempt in range(4):
        time.sleep(delay if attempt == 0 else max(delay, 2 ** attempt))
        try:
            request = Request(url, headers={'User-Agent': 'RP-RunningPerformance/1.0 (FFA bilans maintenance)'})
            with urlopen(request, timeout=45) as response:
                if response.url.split('?')[0] != url.split('?')[0]:
                    raise InputError('Redirection FFA inattendue : collecte arrêtée.')
                html = response.read().decode(response.headers.get_content_charset() or 'utf-8')
            result = parse_page(html, page, season, sex, distance)
            result.update(collected_at=now(), source_url=url)
            return result
        except InputError:
            raise  # Un CAPTCHA ou un format inattendu ne déclenche pas une rafale de requêtes.
        except (OSError, UnicodeError) as error:
            if attempt == 3:
                raise InputError(f'Échec HTTP après 4 tentatives : {url} ({error})') from error


def digest(rows):
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def write_json(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(doc, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def validate_pages(pages, first, full):
    seen = set()
    for number, record in sorted(pages.items()):
        if record.get('page') != number or record.get('total_pages') != first['total_pages'] or record.get('expected_rows') != first['expected_rows']:
            raise InputError('Pagination modifiée pendant la collecte : recommencer dans un nouveau dossier.')
        signature = digest(record['rows'])
        if signature in seen:
            raise InputError('Deux pages FFA identiques : collecte incomplète ou pagination ignorée.')
        seen.add(signature)
    if full:
        if set(pages) != set(range(first['total_pages'])):
            raise InputError('Pages manquantes : aucun export autorisé.')
        actual = sum(len(p['rows']) for p in pages.values())
        if actual != first['expected_rows']:
            raise InputError(f'Total différent de la FFA : {actual} lignes / {first["expected_rows"]} attendues.')


def collect_dataset(season, distance, sex, folder, mode, resume, fetcher):
    folder.mkdir(parents=True, exist_ok=True)
    first = fetcher(season, distance, sex, 0)
    saved = folder / '0.json'
    if resume and saved.exists():
        old = json.loads(saved.read_text(encoding='utf-8'))
        if any(old.get(k) != first.get(k) for k in ('rows', 'total_pages', 'expected_rows')):
            raise InputError('Bilan FFA modifié depuis l’interruption : lancer une nouvelle collecte.')
    write_json(saved, first)
    numbers = range(first['total_pages']) if mode == 'full' else sorted({0, min(1, first['total_pages'] - 1), first['total_pages'] - 1})
    pages = {0: first}
    signatures = {digest(first['rows'])}
    for number in numbers:
        if number == 0:
            continue
        path = folder / f'{number}.json'
        if resume and path.exists():
            record = json.loads(path.read_text(encoding='utf-8'))
            if record.get('source_url') != page_url(season, distance, sex, number):
                raise InputError('Point de reprise incompatible avec le bilan demandé.')
        else:
            record = fetcher(season, distance, sex, number)
            write_json(path, record)
        validate_pages({number: record}, first, False)
        signature = digest(record['rows'])
        if signature in signatures:
            raise InputError('Deux pages FFA identiques : pagination ignorée.')
        signatures.add(signature)
        pages[number] = record
        print(f'{distance} {sex} : page {number + 1}/{first["total_pages"]}', flush=True)
    # Détecter une modification du bilan pendant sa lecture.
    last_check = fetcher(season, distance, sex, 0)
    if any(last_check[k] != first[k] for k in ('rows', 'total_pages', 'expected_rows')):
        raise InputError('Le bilan a changé pendant sa collecte : recommencer avant publication.')
    validate_pages(pages, first, mode == 'full')
    ordered = [pages[n] for n in sorted(pages)]
    rows = [row for p in ordered for row in p['rows']]
    report = {'distance': distance, 'sex': sex, 'pages_checked': len(pages),
              'total_pages': first['total_pages'], 'rows_checked': len(rows),
              'expected_rows': first['expected_rows'], 'ids': sum(bool(r[9]) for r in rows),
              'birth_years': sum(bool(r[8]) for r in rows)}
    return rows, ordered, report


def run(season, mode, out, resume=False, delay=1.0, fetcher=None):
    out = Path(out)
    meta_path = out / 'collection.json'
    if resume:
        if not meta_path.exists():
            raise InputError('Aucune collecte à reprendre dans ce dossier.')
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if (meta.get('version'), meta.get('season'), meta.get('mode')) != (CHECKPOINT_VERSION, season, mode):
            raise InputError('Saison, mode ou version de reprise incompatibles.')
        age = datetime.now(timezone.utc) - datetime.fromisoformat(meta['started_at'])
        if not 0 <= age.total_seconds() <= 86400:
            raise InputError('Reprise trop ancienne (> 24 h) : commencer une nouvelle collecte.')
    else:
        if out.exists() and any(out.iterdir()):
            raise InputError('Dossier non vide : choisir un nouveau dossier ou --resume pour une interruption récente.')
        meta = {'version': CHECKPOINT_VERSION, 'season': season, 'mode': mode, 'started_at': now()}
        write_json(meta_path, meta)
    # Un ancien export n’est jamais présenté comme le résultat d’une reprise échouée.
    for path in (out / 'exports').glob('*.json.gz'):
        path.unlink()
    report = {**meta, 'complete': False, 'datasets': []}
    write_json(out / 'report.json', report)
    fetcher = fetcher or (lambda *args: fetch_page(*args, delay=delay))
    documents = []
    try:
        for key, file_label, label in DISTANCES:
            datasets, stamps = [], []
            for sex in ('M', 'F'):
                rows, pages, summary = collect_dataset(season, key, sex, out / 'pages' / key / sex, mode, resume, fetcher)
                datasets.append({'year': season, 'sex': sex, 'rows': rows})
                stamps.extend(p['collected_at'] for p in pages)
                report['datasets'].append(summary)
                write_json(out / 'report.json', report)
            documents.append((f'ffa_{file_label}_{season}.json.gz', {
                'schema_version': RAW_SCHEMA_VERSION, 'generated_at': now(), 'seasons': [season],
                'collected_from': min(stamps), 'collected_to': max(stamps), 'distance': label,
                'event': EVENTS[key], 'schema': SCHEMA, 'datasets': datasets,
            }))
        if mode == 'full':
            staging = out / 'pending-exports'
            staging.mkdir(exist_ok=True)
            paths = []
            for name, doc in documents:
                path = staging / name
                with gzip.open(path, 'wt', encoding='utf-8') as stream:
                    json.dump(doc, stream, ensure_ascii=False)
                paths.append(path)
            _, parsed = load_raw(paths, [season])
            if parsed['unreadable'] / max(1, parsed['rows']) > 0.005:
                raise InputError('Plus de 0,5 % de lignes illisibles : aucun export validé.')
            report['validation'] = parsed
            exports = out / 'exports'
            exports.mkdir(exist_ok=True)
            for path in paths:
                path.replace(exports / path.name)
            staging.rmdir()
        report.update(complete=True, finished_at=now(), exports_ready=mode == 'full')
    except Exception as error:
        report.update(error=str(error), finished_at=now())
        raise
    finally:
        write_json(out / 'report.json', report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--season', type=int, default=current_season())
    parser.add_argument('--mode', choices=['probe', 'full'], default='probe')
    parser.add_argument('--out', required=True)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(argv)
    try:
        report = run(args.season, args.mode, args.out, args.resume)
        print(f'Terminé : {len(report["datasets"])} bilans contrôlés ; exports : {report["exports_ready"]}.')
        return 0
    except (InputError, OSError, ValueError) as error:
        print(f'Collecte arrêtée : {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
