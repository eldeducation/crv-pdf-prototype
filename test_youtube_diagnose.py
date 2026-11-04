from pathlib import Path
import sys, json, unittest, subprocess
from types import SimpleNamespace
from unittest.mock import patch, Mock, MagicMock
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import youtube_diagnose as diag

URL = 'https://www.youtube.com/watch?v=Q2w4-mluYo0'


class DiagnosisTests(unittest.TestCase):
    def test_rejects_non_youtube_sources(self):
        for source in ('http://127.0.0.1/', 'file:///etc/passwd', 'https://youtube.com.evil.invalid/watch?v=Q2w4-mluYo0'):
            with patch('builtins.print'):
                report = diag.run_probe(source, ROOT)
            self.assertEqual(report['error_code'], 'diagnosis_failed')

    def test_client_options_are_anonymous_and_unretried(self):
        opts = diag.client_options('mweb', diag.QuietLogger())
        self.assertIsNone(opts.get('cookiefile'))
        self.assertIsNone(opts.get('cookiesfrombrowser'))
        self.assertIsNone(opts.get('proxy'))
        self.assertEqual(opts['extractor_retries'], 0)
        self.assertEqual(opts['extractor_args']['youtube']['player_client'], ['mweb'])

    def test_only_safe_enumerated_fields_are_logged(self):
        child = {'success': False, 'verdict': 'network_refused_even_for_real_browser', 'client_mweb': 'bot_check',
                 'egress_colo': 'PDX', 'ip': '203.0.113.9', 'cookie': 'secret-must-not-appear',
                 'token': 'secret-must-not-appear', 'egress_ip_version': 4}
        folder = MagicMock(); folder.__enter__.return_value = '/fresh'
        proc = Mock(returncode=1); proc.communicate.return_value = (json.dumps(child), None)
        with patch.object(diag.tempfile, 'TemporaryDirectory', return_value=folder), \
                patch.object(diag.subprocess, 'Popen', return_value=proc) as spawn, \
                patch.dict(diag.os.environ, {'OPENROUTER_API_KEY': 'secret-must-not-appear'}), \
                patch('builtins.print') as output:
            report = diag.run_probe(URL, ROOT)
        self.assertNotIn('secret-must-not-appear', str(output.call_args_list))
        self.assertNotIn('203.0.113.9', str(output.call_args_list))
        self.assertNotIn('OPENROUTER_API_KEY', spawn.call_args.kwargs['env'])
        self.assertEqual(spawn.call_args.kwargs['env']['HOME'], '/fresh')
        self.assertEqual(report['client_mweb'], 'bot_check')
        self.assertEqual(report['ai_calls'], 0)
        proc.communicate.assert_called_once_with(timeout=diag.CHILD_TIMEOUT)

    def test_timeout_kills_process_group(self):
        folder = MagicMock(); folder.__enter__.return_value = '/fresh'
        proc = Mock(pid=55); proc.communicate.side_effect = [subprocess.TimeoutExpired('x', 1), ('', None)]
        with patch.object(diag.tempfile, 'TemporaryDirectory', return_value=folder), \
                patch.object(diag.subprocess, 'Popen', return_value=proc), \
                patch.object(diag, 'os', SimpleNamespace(name='posix', killpg=Mock())) as fake_os, \
                patch.object(diag.signal, 'SIGKILL', 9, create=True), patch('builtins.print'):
            report = diag.run_probe(URL, ROOT)
        self.assertEqual(report['error_code'], 'timeout')
        fake_os.killpg.assert_called_once_with(55, 9)

    def test_verdicts(self):
        self.assertEqual(diag.verdict({'success': True}), 'downloaded')
        self.assertEqual(diag.verdict({'client_ios': 'ok'}), 'client_ok_download_failed')
        self.assertEqual(diag.verdict({'browser_watch_status': 'LOGIN_REQUIRED', 'browser_watch_bot': True,
                                       'embed_played': False}), 'network_refused_even_for_real_browser')
        self.assertEqual(diag.verdict({'browser_watch_played': True}), 'real_browser_plays_only_ytdlp_refused')

    def test_playable_ignores_storyboards(self):
        self.assertFalse(diag.playable({'formats': [{'vcodec': 'none', 'ext': 'mhtml', 'url': 'x'}]}))
        self.assertTrue(diag.playable({'formats': [{'vcodec': 'avc1', 'ext': 'mp4', 'url': 'x'}]}))


if __name__ == '__main__':
    unittest.main()
