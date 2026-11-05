import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import import_d1_candidate as d
import build_db as b
from test_build_db import profile, empty


class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = self.root / 'production.toml'
        self.prod = '11111111-1111-4111-8111-111111111111'
        self.candidate = '22222222-2222-4222-8222-222222222222'
        self.config.write_text(f'[[d1_databases]]\nbinding="DB"\ndatabase_name="production"\ndatabase_id="{self.prod}"\n')
        d.save(self.root/'validation.json', {'ok': True, 'checks': [{'ok': True}], 'distances': [{'after': 123}]})
        d.save(self.root/'provenance.json', {'season': 2027})
        self.state = self.root/'candidate.json'
        self.api = Mock()
        self.api.create.return_value = {'uuid': self.candidate}

    def create(self):
        return d.create_candidate(self.root, self.state, self.config, '123', '456', '1', self.api)

    def test_creates_distinct_database_without_editing_production(self):
        before = self.config.read_bytes()
        state = self.create()
        self.assertFalse(state['ready'])
        self.assertEqual(state['database_id'], self.candidate)
        self.assertEqual(state['expected_profiles'], 123)
        self.assertEqual(self.config.read_bytes(), before)

    def test_rejects_report_failure_before_cloudflare_call(self):
        d.save(self.root/'validation.json', {'ok': False})
        with self.assertRaises(ValueError): self.create()
        self.api.create.assert_not_called()

    def test_rejects_failed_check_even_if_report_claims_success(self):
        d.save(self.root/'validation.json', {'ok': True, 'checks': [{'ok': False}]})
        with self.assertRaises(ValueError): self.create()
        self.api.create.assert_not_called()

    def test_production_id_is_never_an_import_target(self):
        self.api.create.return_value = {'uuid': self.prod}
        with self.assertRaises(ValueError): self.create()

    def test_production_change_blocks_candidate(self):
        state = self.create()
        state['production_database_id'] = self.candidate
        with self.assertRaises(ValueError): d.assert_candidate(state, self.config)

    def test_invalid_run_id_never_creates_database(self):
        with self.assertRaises(ValueError):
            d.create_candidate(self.root, self.state, self.config, '../123', '456', '1', self.api)
        self.api.create.assert_not_called()

    def test_production_target_never_launches_wrangler(self):
        state = self.create()
        state['database_id'] = self.prod
        d.save(self.state, state)
        runner = Mock()
        with self.assertRaises(ValueError):
            d.import_candidate(self.root, self.state, self.config, self.api, runner)
        runner.assert_not_called()

    def prepare_files(self):
        profiles = empty()
        for key, sec in [('5k', 1000), ('10k', 2000), ('semi', 4000), ('marathon', 8000)]:
            profiles[key] = [profile('MARTIN Jean', sec, ffa_id=key)]
        db, _ = b.build(self.root/'ffa.db', profiles)
        b.export_sql(db, self.root/'ffa.sql')
        db.close()
        d.save(self.root/'validation.json', {'ok': True, 'checks': [{'ok': True}],
            'distances': [{'after': 1} for _ in range(4)],
            'database_bytes': (self.root/'ffa.db').stat().st_size,
            'sql': {'bytes': (self.root/'ffa.sql').stat().st_size}})
        return self.create()

    def test_import_and_checks_pass_without_modifying_production(self):
        self.prepare_files()
        def query(state, config, sql):
            d.assert_candidate(state, config)
            with d.sqlite3.connect(self.root/'ffa.db') as db:
                db.row_factory = d.sqlite3.Row
                return [dict(r) for r in db.execute(sql)], {'duration': 1}
        self.api.query.side_effect = query
        runner = Mock()
        before = self.config.read_bytes()
        result = d.import_candidate(self.root, self.state, self.config, self.api, runner)
        self.assertTrue(result['ready'])
        self.assertEqual(len(result['checks']), 18)
        self.assertEqual(self.config.read_bytes(), before)
        command = runner.call_args.args[0]
        self.assertIn('--remote', command)
        self.assertIn(str(self.root/'candidate.toml'), command)
        self.assertNotIn(str(self.config), command)

    def test_remote_mismatch_keeps_candidate_unready(self):
        self.prepare_files()
        self.api.query.return_value = ([], {})
        with self.assertRaises(ValueError):
            d.import_candidate(self.root, self.state, self.config, self.api, Mock())
        state = json.loads(self.state.read_text())
        self.assertFalse(state['ready'])
        self.assertEqual(state['status'], 'failed')


if __name__ == '__main__': unittest.main()
