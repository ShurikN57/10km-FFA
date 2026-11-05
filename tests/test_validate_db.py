import copy
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_db as b
import validate_db as v


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.baseline, self.database = root / 'before.db', root / 'after.db'
        self.profiles = {}
        for key, seconds in [('5k', 1000), ('10k', 2000), ('semi', 5000), ('marathon', 12000)]:
            self.profiles[key] = [dict(full_name='A COUREUR', birth_year=1985, sex='M', pb_sec=seconds,
                pb_date='01/10/25', club='Club', athlete_ffa_id=key+'A', league='G-E', department='057'),
                dict(full_name='B COUREUSE (GBR)', birth_year=1990, sex='F', pb_sec=seconds,
                pb_date='02/10/25', club=None, athlete_ffa_id=key+'B', league=None, department=None)]
        b.build(self.baseline, self.profiles)[0].close()
        self.after = copy.deepcopy(self.profiles)
        self.after['10k'][0]['pb_sec'] -= 10
        self.after['10k'][0]['pb_date'] = '01/10/26'
        new = dict(self.after['10k'][0], full_name='NOUVEAU Coureur', athlete_ffa_id='N', pb_sec=2500)
        self.after['10k'].append(new)
        b.build(self.database, self.after)[0].close()

    def check(self):
        return v.validate(self.database, self.baseline)

    def change(self, sql):
        with sqlite3.connect(self.database) as db:
            db.executescript(sql)

    def test_valid_update_and_readonly(self):
        before = self.database.read_bytes()
        report = self.check()
        self.assertTrue(report['ok'], [x for x in report['checks'] if not x['ok']])
        self.assertEqual(next(x for x in report['distances'] if x['distance']=='10k')['new'], 1)
        self.assertEqual(next(x for x in report['distances'] if x['distance']=='10k')['improved_existing'], 1)
        self.assertEqual(self.database.read_bytes(), before)

    def test_rank_error_detected(self):
        self.change('UPDATE athlete_general_rank SET rank=999')
        self.assertFalse(self.check()['ok'])

    def test_missing_search_row_detected(self):
        self.change('DELETE FROM athlete_fts WHERE rowid=(SELECT MIN(id) FROM athletes)')
        self.assertFalse(self.check()['ok'])

    def test_missing_options_detected(self):
        self.change('DELETE FROM ffa_scope_options')
        self.assertFalse(self.check()['ok'])

    def test_historical_pb_regression_detected_even_when_ranks_rebuilt(self):
        self.after['5k'][0]['pb_sec'] += 30
        b.build(self.database, self.after)[0].close()
        report = self.check()
        self.assertFalse(report['ok'])
        self.assertFalse(next(c for c in report['checks'] if c['name']=='5k_historique_sans_regression')['ok'])

    def test_missing_index_detected(self):
        self.change('DROP INDEX idx_athletes_next_distance_pb')
        self.assertFalse(self.check()['ok'])

    def test_single_profile_and_missing_birth(self):
        profiles = {k: [] for k, _, _ in b.DISTANCES}
        profiles['10k'] = [dict(self.profiles['10k'][0], birth_year=None, sex=None)]
        b.build(self.baseline, profiles)[0].close()
        b.build(self.database, profiles)[0].close()
        report = self.check()
        self.assertTrue(report['ok'], [x for x in report['checks'] if not x['ok']])

    def test_missing_database_returns_failure_report(self):
        out = Path(self.tmp.name) / 'report.json'
        code = v.main(['--db', str(self.database), '--baseline', str(out.with_suffix('.db')), '--out', str(out)])
        self.assertEqual(code, 2)
        self.assertTrue(out.exists())

    def test_generated_sql_and_multiline_literals(self):
        path = Path(self.tmp.name) / 'export.sql'
        with sqlite3.connect(self.database) as db:
            b.export_sql(db, path)
        report = v.validate(self.database, self.baseline, sql_path=path)
        self.assertTrue(report['ok'])
        self.assertGreater(report['sql']['statements'], 0)
        path.write_text("INSERT INTO x VALUES ('texte;\nété');\n", encoding='utf-8')
        self.assertTrue(v.validate(self.database, self.baseline, sql_path=path)['ok'])

    def test_oversized_utf8_sql_and_unterminated_statement_rejected(self):
        path = Path(self.tmp.name) / 'export.sql'
        for sql in ["INSERT INTO x VALUES ('" + 'é' * 50_000 + "');\n", 'INSERT INTO x VALUES (1)']:
            path.write_text(sql, encoding='utf-8')
            self.assertFalse(v.validate(self.database, self.baseline, sql_path=path)['ok'])


if __name__ == '__main__':
    unittest.main()
