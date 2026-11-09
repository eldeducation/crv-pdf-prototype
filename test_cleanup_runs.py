"""runs/ cleanup: listing is the default, and only unreferenced old failures are offered."""
import contextlib
import io
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import cleanup_runs

NOW = time.mktime(time.strptime('20261109120000', '%Y%m%d%H%M%S'))


class CleanupRunsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.runs = Path(tmp.name) / 'runs'
        self.runs.mkdir()

    def run_folder(self, name, status=None, payload=b'x' * 1000, **report):
        folder = self.runs / name
        (folder / 'work').mkdir(parents=True)
        (folder / 'work' / 'data.bin').write_bytes(payload)
        if status:
            (folder / 'run.json').write_text(json.dumps({'status': status, **report}), encoding='utf-8')
        return folder

    def decisions(self):
        return {e['name']: (e['keep'], e['reason']) for e in cleanup_runs.survey(self.runs, 2, NOW)}

    def test_keeps_finished_referenced_recent_and_newest_failed(self):
        source = self.run_folder('20261101-100000-aaaaaa', 'complete')
        evidence = str(source / 'work' / 'crv')
        self.run_folder('20261102-100000-bbbbbb', 'failed', evidence_dir=evidence)
        self.run_folder('20261103-100000-cccccc', 'needs_review', restyle_from='20261102-100000-bbbbbb')
        self.run_folder('20261104-100000-dddddd', 'failed')
        self.run_folder('20261105-100000-eeeeee', 'failed')
        self.run_folder('20261105-110000-ffffff', 'running')
        self.run_folder('20261109-100000-999999', 'failed')     # today
        empty = self.runs / '20261101-090000-000000'
        empty.mkdir()
        (self.runs / 'notes').mkdir()
        got = self.decisions()
        self.assertEqual(got['20261101-100000-aaaaaa'], (True, 'finished document'))
        self.assertEqual(got['20261102-100000-bbbbbb'], (True, 'reused by 20261103-100000-cccccc'))
        self.assertEqual(got['20261105-110000-ffffff'][0], True)
        self.assertEqual(got['20261109-100000-999999'][0], True)
        self.assertEqual(got['notes'][0], True)
        self.assertEqual(got['20261104-100000-dddddd'], (False, 'old failed run'))
        self.assertEqual(got['20261105-100000-eeeeee'], (False, 'old failed run'))
        self.assertFalse(got['20261101-090000-000000'][0])

    def test_newest_failed_is_kept_when_nothing_is_recent(self):
        self.run_folder('20261101-100000-aaaaaa', 'failed')
        self.run_folder('20261102-100000-bbbbbb', 'failed')
        got = self.decisions()
        self.assertFalse(got['20261101-100000-aaaaaa'][0])
        self.assertEqual(got['20261102-100000-bbbbbb'], (True, 'newest failed run (can be resumed)'))

    def test_a_failed_run_reusing_a_source_does_not_protect_itself(self):
        self.run_folder('20261101-100000-aaaaaa', 'failed')
        self.run_folder('20261102-100000-bbbbbb', 'failed', restyle_from='20261101-100000-aaaaaa')
        self.run_folder('20261103-100000-cccccc', 'failed')
        got = self.decisions()
        self.assertFalse(got['20261101-100000-aaaaaa'][0])
        self.assertFalse(got['20261102-100000-bbbbbb'][0])

    def run_main(self, *args, answer=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), mock.patch('time.time', return_value=NOW), \
                mock.patch('builtins.input', return_value=answer) as asked:
            cleanup_runs.main(['--runs', str(self.runs), *args])
        return out.getvalue(), asked

    def test_listing_never_deletes(self):
        old = self.run_folder('20261101-100000-aaaaaa', 'failed')
        self.run_folder('20261102-100000-bbbbbb', 'failed')
        text, asked = self.run_main()
        self.assertTrue(old.exists())
        asked.assert_not_called()
        self.assertIn('DELETE? 20261101-100000-aaaaaa', text)
        self.assertIn('削除はしていません', text)

    def test_delete_asks_and_only_yes_deletes(self):
        old = self.run_folder('20261101-100000-aaaaaa', 'failed')
        kept = self.run_folder('20261102-100000-bbbbbb', 'failed')
        self.run_main('--delete', answer='y')
        self.assertTrue(old.exists())
        self.run_main('--delete', answer='yes')
        self.assertFalse(old.exists())
        self.assertTrue(kept.exists())

    def test_delete_refuses_paths_outside_runs(self):
        outside = self.runs.parent / '20261101-100000-aaaaaa'
        outside.mkdir()
        entry = {'keep': False, 'path': outside, 'size': 0}
        cleanup_runs.delete([entry], self.runs)
        self.assertTrue(outside.exists())


if __name__ == '__main__':
    unittest.main()
