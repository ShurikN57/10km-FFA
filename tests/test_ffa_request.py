import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from ffa_request import resolve_request


class RequestTests(unittest.TestCase):
    def test_commit_requests_full_season(self):
        result = resolve_request('push', {}, {'season': 2027, 'mode': 'full', 'requested_at': '2026-11-05T08:00:00Z'})
        self.assertEqual(result, {'season': '2027', 'mode': 'full', 'resume_run': ''})

    def test_pr_is_always_probe(self):
        result = resolve_request('pull_request', {'mode': 'full', 'resume_run': '12'}, {'mode': 'full'})
        self.assertEqual(result['mode'], 'probe')
        self.assertEqual(result['resume_run'], '')

    def test_manual_resume(self):
        self.assertEqual(resolve_request('workflow_dispatch', {'season': '2027', 'mode': 'full', 'resume_run': '123'})['resume_run'], '123')

    def test_rejects_invalid_inputs(self):
        for values in [{'season': '2027\nmode=full'}, {'mode': 'shell'}, {'resume_run': '../1'}, {'resume_run': '-1'}]:
            with self.assertRaises(ValueError):
                resolve_request('workflow_dispatch', values)

    def test_commit_requires_timestamp(self):
        for doc in [None, {}, {'requested_at': '2026-11-05'}, {'requested_at': 'bad'}]:
            with self.assertRaises(ValueError):
                resolve_request('push', {}, doc)

    def test_unknown_event_rejected(self):
        with self.assertRaises(ValueError):
            resolve_request('schedule', {})


if __name__ == '__main__':
    unittest.main()
