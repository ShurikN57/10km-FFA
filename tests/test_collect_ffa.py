"""Contrôles hors réseau de la collecte HTTP et des exports V3."""
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import collect_ffa as c


def html(page=0, total=2, count=2):
    # Même structure que les bilans : balises i/b mal fermées, détails mobiles
    # dans une table imbriquée, et options de pagination après la page courante.
    return f'''<table id="ctnBilans"><tr><td>Page&nbsp;&gt;&nbsp;{page+1:03}/{total:03}&nbsp;&lt;
    <div>Page &gt; 001/{total} &lt;</div>{count} résultats</td></tr>
    <tr><td>2027 | 10 Km Route | F</td></tr>
    <tr><td>{page+1}</td><td><i><b>40'00''</i></b> (RP)</td>
    <td><a href="/athletes/A{page}/bilans">MARTIN Éloïse</a></td>
    <td>Club &amp; co</td><td>G-E</td><td>057</td><td>SEF/<a>95</a></td>
    <td>01/10/26</td><td>Metz</td><td>+</td></tr>
    <tr><td colspan="4"><table><tr><td>Club</td><td>Détail mobile</td></tr></table></td></tr>
    <tr><td>Ne pas lire</td></tr></table>'''


def fake_fetch(season, distance, sex, page):
    result = c.parse_page(html(page), page)
    if distance in ('semi', 'marathon'):
        result['rows'][0][0] = "2h30'00''"
    result['rows'][0][1] += f' {distance} {sex} {page}'
    result.update(collected_at=c.now(), source_url=c.page_url(season, distance, sex, page))
    return result


class ParsingTests(unittest.TestCase):
    def test_nested_mobile_details_and_fields(self):
        page = c.parse_page(html(), 0)
        self.assertEqual(page['total_pages'], 2)
        self.assertEqual(page['expected_rows'], 2)
        self.assertEqual(page['rows'], [["40'00'' (RP)", 'MARTIN Éloïse', 'Club & co',
            'G-E', '057', 'SEF/95', '01/10/26', 'Metz', '1995', 'A0']])

    def test_wrong_page_rejected(self):
        with self.assertRaises(c.InputError):
            c.parse_page(html(0), 1)

    def test_wrong_season_or_sex_rejected(self):
        c.parse_page(html(), 0, 2027, 'F')
        for season, sex in [(2026, 'F'), (2027, 'M')]:
            with self.assertRaises(c.InputError):
                c.parse_page(html(), 0, season, sex)

    def test_blocked_or_changed_format_rejected(self):
        for source in ['<html>captcha</html>', '<table id="ctnBilans">Page > 1/1 < 1 résultat</table>']:
            with self.assertRaises(c.InputError):
                c.parse_page(source, 0)

    def test_grouped_total_and_no_id(self):
        source = html().replace('2 résultats', '48\u00a0272 résultats').replace('/athletes/A0/bilans', '/autre')
        result = c.parse_page(source, 0)
        self.assertEqual(result['expected_rows'], 48272)
        self.assertEqual(result['rows'][0][9], '')


class CollectionTests(unittest.TestCase):
    def test_probe_never_exports(self):
        with tempfile.TemporaryDirectory() as directory:
            report = c.run(2027, 'probe', directory, fetcher=fake_fetch)
            self.assertTrue(report['complete'])
            self.assertFalse(report['exports_ready'])
            self.assertEqual(len(report['datasets']), 8)
            self.assertFalse((Path(directory) / 'exports').exists())

    def test_full_exports_accepted_by_existing_builder(self):
        with tempfile.TemporaryDirectory() as directory:
            report = c.run(2027, 'full', directory, fetcher=fake_fetch)
            paths = list((Path(directory) / 'exports').glob('*.json.gz'))
            self.assertEqual(len(paths), 4)
            perfs, _ = c.load_raw(paths, [2027])
            self.assertEqual({k: len(v) for k, v in perfs.items()}, dict.fromkeys(c.EVENTS, 4))
            self.assertTrue(report['exports_ready'])

    def test_duplicate_pages_fail_without_exports(self):
        def repeated(*args):
            record = fake_fetch(*args)
            record['rows'] = fake_fetch(*args[:3], 0)['rows']
            return record
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(c.InputError):
                c.run(2027, 'full', directory, fetcher=repeated)
            self.assertFalse(json.loads((Path(directory) / 'report.json').read_text())['complete'])
            self.assertFalse((Path(directory) / 'exports').exists())

    def test_ffa_count_mismatch_fails(self):
        def wrong_count(*args):
            record = fake_fetch(*args)
            record['expected_rows'] = 3
            return record
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(c.InputError):
                c.run(2027, 'full', directory, fetcher=wrong_count)

    def test_bilan_changes_during_collection(self):
        calls = 0
        def changed(*args):
            nonlocal calls
            calls += 1
            result = fake_fetch(*args)
            if calls == 3:
                result['rows'][0][1] = 'MODIFIÉ'
            return result
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(c.InputError):
                c.run(2027, 'full', directory, fetcher=changed)

    def test_resume_skips_saved_pages_but_rechecks_first(self):
        with tempfile.TemporaryDirectory() as directory:
            def interrupted(season, dist, sex, page):
                if sex == 'F':
                    raise c.InputError('Interruption réseau simulée')
                return fake_fetch(season, dist, sex, page)
            with self.assertRaises(c.InputError):
                c.run(2027, 'full', directory, fetcher=interrupted)
            calls = []
            def traced(*args):
                calls.append(args)
                return fake_fetch(*args)
            report = c.run(2027, 'full', directory, resume=True, fetcher=traced)
            self.assertTrue(report['exports_ready'])
            self.assertNotIn((2027, '5k', 'M', 1), calls)
            self.assertEqual(calls.count((2027, '5k', 'M', 0)), 2)

    def test_resume_rejects_changed_data_and_old_campaign(self):
        with tempfile.TemporaryDirectory() as directory:
            c.run(2027, 'probe', directory, fetcher=fake_fetch)
            def changed(*args):
                record = fake_fetch(*args)
                record['rows'][0][1] = 'MODIFIÉ'
                return record
            with self.assertRaises(c.InputError):
                c.run(2027, 'probe', directory, resume=True, fetcher=changed)
            path = Path(directory) / 'collection.json'
            meta = json.loads(path.read_text())
            meta['started_at'] = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            c.write_json(path, meta)
            with self.assertRaises(c.InputError):
                c.run(2027, 'probe', directory, resume=True, fetcher=fake_fetch)

    def test_existing_folder_requires_explicit_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            c.run(2027, 'probe', directory, fetcher=fake_fetch)
            with self.assertRaises(c.InputError):
                c.run(2027, 'probe', directory, fetcher=fake_fetch)
            with self.assertRaises(c.InputError):
                c.run(2028, 'probe', directory, resume=True, fetcher=fake_fetch)


if __name__ == '__main__':
    unittest.main()
