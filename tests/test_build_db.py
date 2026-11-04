"""Tests de tools/build_db.py : lecture des exports bruts, fusion, construction."""
import gzip
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_db as b  # noqa: E402


def profile(name, pb, birth=1985, sex='M', ffa_id=None, date='12/10/25', club='Club', league=None, dept=None):
    return {'full_name': name, 'birth_year': birth, 'sex': sex, 'pb_sec': pb, 'pb_date': date, 'club': club,
            'athlete_ffa_id': ffa_id, 'league': league, 'department': dept}


def perf(name, pb, **kw):
    p = profile(name, pb, **kw)
    p['season'] = 2027
    return p


def empty():
    return {k: [] for k, _, _ in b.DISTANCES}


class ParseTests(unittest.TestCase):
    def test_parse_time(self):
        for text, sec in [("33'05''", 1985), ("1h13'26''", 4406), ("2h05'30''", 7530), ('1:13:26', 4406),
                          ('33:05', 1985), ("33'05'' (+0,3)", 1985), ('2h05', 7500), ('', None), ('DNF', None)]:
            self.assertEqual(b.parse_time(text), sec, text)

    def test_parse_date(self):
        self.assertEqual(b.parse_date('5/9/26'), '05/09/26')
        self.assertEqual(b.parse_date('12/10/2026'), '12/10/26')
        self.assertIsNone(b.parse_date(''))

    def test_category(self):
        self.assertEqual(b.category(1993, 2027), 'SE')
        self.assertEqual(b.category(1992, 2027), 'M0')
        self.assertEqual(b.category(2012, 2027), None)  # minime : pas classé
        self.assertEqual(b.category(None, 2027), None)

    def test_load_raw(self):
        doc = {'event': '261', 'distance': '10 km', 'datasets': [{'year': 2027, 'sex': 'F', 'rows': [
            ["35'10''", 'DUPONT Marie', 'Club A', 'I-F', '077', 'SEF / 95', '12/10/26', 'Paris', '1995', '123'],
            ['???', 'ILLISIBLE Jean', '', '', '', '', '', '', '', '']]}]}
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'ffa_10km_2027.json.gz'
            with gzip.open(path, 'wt', encoding='utf-8') as f:
                json.dump(doc, f)
            perfs, report = b.load_raw([path])
        self.assertEqual(report['unreadable'], 1)
        p = perfs['10k'][0]
        self.assertEqual((p['pb_sec'], p['sex'], p['birth_year'], p['athlete_ffa_id'], p['league'], p['pb_date']),
                         (2110, 'F', 1995, '123', 'I-F', '12/10/26'))


class MergeTests(unittest.TestCase):
    def merge(self, ref, perfs):
        r, p = empty(), empty()
        r['10k'], p['10k'] = ref, perfs
        out, stats = b.merge(r, p)
        return out['10k'], stats

    def test_meilleur_temps_conserve(self):
        out, stats = self.merge([profile('DUPONT Jean', 2100, ffa_id='1', club='Ancien', league='I-F')],
                                [perf('DUPONT Jean', 2050, ffa_id='1', club='Nouveau', league='PCA', date='01/02/27'),
                                 perf('DUPONT Jean', 2200, ffa_id='1')])
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]['pb_sec'], out[0]['club'], out[0]['league'], out[0]['pb_date']), (2050, 'Nouveau', 'PCA', '01/02/27'))
        self.assertEqual(stats['improved'], 1)

    def test_temps_plus_lent_ignore(self):
        out, stats = self.merge([profile('DUPONT Jean', 2000, ffa_id='1', club='Ancien')], [perf('DUPONT Jean', 2100, ffa_id='1', club='Nouveau')])
        self.assertEqual((out[0]['pb_sec'], out[0]['club']), (2000, 'Ancien'))
        self.assertEqual(stats['unchanged'], 1)

    def test_homonymes_avec_identifiants_differents_restent_separes(self):
        out, stats = self.merge([profile('MOREAU Alexandre', 3775, ffa_id='A'), profile('MOREAU Alexandre', 2577, ffa_id='B')],
                                [perf('MOREAU Alexandre', 3000, ffa_id='A')])
        self.assertEqual(sorted(p['pb_sec'] for p in out), [2577, 3000])

    def test_sans_identifiant_par_nom_annee_sexe(self):
        # Accents et casse ignorés ; une autre année de naissance = un autre athlète.
        out, _ = self.merge([profile('Éloïse MARTIN', 2500, birth=1990, sex='F')],
                            [perf('ELOISE Martin', 2400, birth=1990, sex='F'), perf('ELOISE MARTIN', 2300, birth=1991, sex='F')])
        self.assertEqual(sorted((p['birth_year'], p['pb_sec']) for p in out), [(1990, 2400), (1991, 2300)])

    def test_identifiant_relie_a_un_profil_sans_identifiant_unique(self):
        out, stats = self.merge([profile('PETIT Luc', 2500)], [perf('PETIT Luc', 2600, ffa_id='9')])
        self.assertEqual(len(out), 1)
        self.assertEqual((out[0]['athlete_ffa_id'], out[0]['pb_sec']), ('9', 2500))
        self.assertEqual(stats['linked_id'], 1)

    def test_nouvel_athlete(self):
        out, stats = self.merge([profile('DUPONT Jean', 2000, ffa_id='1')], [perf('NOUVEAU Coureur', 2900, ffa_id='2')])
        self.assertEqual(len(out), 2)
        self.assertEqual(stats['new'], 1)

    def test_fusion_idempotente(self):
        ref = [profile('DUPONT Jean', 2100, ffa_id='1')]
        perfs = [perf('DUPONT Jean', 2050, ffa_id='1'), perf('NOUVEAU Coureur', 2900)]
        once, _ = self.merge(ref, perfs)
        twice, _ = self.merge(once, perfs)
        self.assertEqual(once, twice)


class BuildTests(unittest.TestCase):
    def test_tables_derivees(self):
        prof = empty()
        prof['10k'] = [profile('B COUREUR', 2000, ffa_id='1', league='I-F', dept='077'),
                       profile('A COUREUR', 2000, ffa_id='2'),
                       profile('ETRANGER John (GBR)', 1900, ffa_id='3'),
                       profile('C COUREUSE', 2100, sex='F', birth=1960, date='')]
        prof['5k'] = [profile('TROP RAPIDE', 600)]  # < 12 min : écarté
        with tempfile.TemporaryDirectory() as d:
            db, n = b.build(Path(d) / 'ffa.db', prof)
            self.assertEqual(n, 4)
            q = lambda sql: db.execute(sql).fetchall()
            self.assertEqual(q('SELECT full_name, r.rank, r.display_order FROM athletes a JOIN athlete_general_rank r ON r.athlete_id=a.id ORDER BY r.display_order'),
                             [('ETRANGER John (GBR)', 1, 1), ('A COUREUR', 2, 2), ('B COUREUR', 2, 3), ('C COUREUSE', 4, 4)])
            # Rang « français » = rang parmi tous, étrangers exclus de la liste.
            self.assertEqual(q('SELECT a.full_name, f.rank_general FROM athlete_french_rank f JOIN athletes a ON a.id=f.athlete_id ORDER BY 2, 1'),
                             [('A COUREUR', 2), ('B COUREUR', 2), ('C COUREUSE', 4)])
            self.assertEqual(q("SELECT rank_sex FROM athlete_search_rank s JOIN athletes a ON a.id=s.athlete_id WHERE a.sex='F'"), [(1,)])
            self.assertEqual(q("SELECT league, department, race_year FROM athlete_scope s JOIN athletes a ON a.id=s.athlete_id WHERE a.full_name='B COUREUR'"), [('I-F', '077', 2025)])
            self.assertEqual(q("SELECT race_year FROM athlete_scope s JOIN athletes a ON a.id=s.athlete_id WHERE a.full_name='C COUREUSE'"), [(None,)])
            self.assertEqual(q('SELECT distance, total FROM ffa_distance_stats'), [('10k', 4)])
            self.assertEqual(q('SELECT distance, total FROM ffa_french_stats'), [('10k', 3)])
            self.assertEqual(q("SELECT COUNT(*) FROM athlete_fts WHERE athlete_fts MATCH '\"COUREUR\"'"), [(2,)])
            sql = Path(d) / 'ffa.sql'
            b.export_sql(db, sql)
            fresh = sqlite3.connect(':memory:')
            fresh.executescript(sql.read_text(encoding='utf-8'))
            for table, _ in b.EXPORT_TABLES:
                self.assertEqual(fresh.execute(f'SELECT * FROM {table} ORDER BY 1, 2').fetchall(),
                                 db.execute(f'SELECT * FROM {table} ORDER BY 1, 2').fetchall(), table)
            self.assertEqual(fresh.execute("SELECT COUNT(*) FROM athlete_fts WHERE athlete_fts MATCH '\"COUREUR\"'").fetchall(), [(2,)])
            db.close()


if __name__ == '__main__':
    unittest.main()
