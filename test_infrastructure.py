"""Infrastructure regressions only; no provider calls or AI quality claims."""
import contextlib
import io
import json
import os
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

MODULE_ROOT = Path(__file__).resolve().parent
if not (MODULE_ROOT / 'security.py').is_file(): MODULE_ROOT = MODULE_ROOT.parent
sys.path.insert(0, str(MODULE_ROOT))

import security
import share_gateway as gateway
import pipeline


class InfrastructureTests(unittest.TestCase):
    def test_child_receives_runtime_settings_but_no_unrelated_secrets(self):
        source = {'PATH': os.environ.get('PATH', ''), 'LANG': 'ja_JP.UTF-8',
                  'PYTHONIOENCODING': 'utf-8', 'VIDEO_PDF_MODEL': 'unchanged-model',
                  'CRV_NO_MEMORY': '1', 'HF_HOME': '/cache/models',
                  'OPENAI_API_KEY': 'fake-openai', 'ANTHROPIC_API_KEY': 'fake-anthropic',
                  'OPENROUTER_API_KEY': 'fake-router', 'GITHUB_TOKEN': 'fake-github',
                  'AWS_SECRET_ACCESS_KEY': 'fake-aws', 'VIDEO_PDF_ACCESS_PASSWORD': 'fake-invite',
                  'VIDEO_PDF_UNKNOWN_SECRET': 'fake-other', 'PYTHONPATH': 'unsafe-hook',
                  'NODE_OPTIONS': '--require=unsafe-hook'}
        env = security.child_environment(source)
        self.assertEqual(set(env), {'PATH', 'LANG', 'PYTHONIOENCODING', 'VIDEO_PDF_MODEL', 'CRV_NO_MEMORY', 'HF_HOME'})
        # Test the real process boundary, not just the filtering expression.
        output = pipeline.command_run([sys.executable, '-I', '-c',
            'import os,json; print(json.dumps({k:v for k,v in os.environ.items() if k in '+repr(list(source))+'}))'], env=source)
        child = json.loads(output)
        self.assertEqual(child['VIDEO_PDF_MODEL'], source['VIDEO_PDF_MODEL'])
        for key in set(source)-set(env): self.assertNotIn(key, child)
        self.assertEqual(source['GITHUB_TOKEN'], 'fake-github')

    def test_errors_hide_host_paths_and_keys_without_changing_input(self):
        source = {'error': 'HTTP 403 at "C:\\Users\\Person Name\\private\\video.mp4" sk-or-v1-'+'fixture'*8,
                  'job': {'message': 'failed /app/work/private/session/tool.py:13'},
                  'source': '/app/work/private/session/upload.mp4',
                  'url': 'https://www.youtube.com/watch?v=N1P4VpXhrfo',
                  'markdown': '# 元の原稿\n変更しない'}
        before = json.dumps(source)
        result = security.public_errors(source)
        self.assertNotIn('Person Name', result['error'])
        self.assertNotIn('sk-or-v1-', result['error'])
        self.assertNotIn('/app/work', result['job']['message'])
        self.assertIn('HTTP 403', result['error'])
        self.assertEqual(result['url'], source['url'])
        self.assertEqual(result['markdown'], source['markdown'])
        self.assertEqual(result['source'], 'upload.mp4')
        self.assertEqual(json.dumps(source), before)
        self.assertNotIn('利用者名', security.public_error('failed C:/Users/利用者名/App Data/x', roots=('C:/Users/利用者名',)))

    def test_audit_records_only_fixed_categories_and_status(self):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            security.audit_request('POST', '/secret-session-token/configure?api_key=private', 200)
            security.audit_request('GET', '/secret/files/20261030-010101-abc123/private.pdf', 200)
            security.audit_request('GET', '/secret/status', 200)
        rows = [json.loads(line) for line in stream.getvalue().splitlines()]
        self.assertEqual([r['route'] for r in rows], ['configure', 'download'])
        self.assertEqual(set(rows[0]), {'event', 'time', 'method', 'route', 'status'})
        for secret in ('secret-session-token', 'private', 'api_key', 'private.pdf'):
            self.assertNotIn(secret, stream.getvalue())

    def test_slow_start_does_not_hold_gateway_lock_and_pending_capacity_is_counted(self):
        ready, release = threading.Event(), threading.Event()
        errors = []
        def slow_start(identity):
            ready.set()
            if not release.wait(5): raise TimeoutError('Test release was not signalled')
            return 'new-session', {'fixture': True}
        def launch():
            try: gateway.create_session()
            except Exception as error: errors.append(error)
        with patch.object(gateway, 'SESSIONS', {str(i): {} for i in range(7)}), patch.object(gateway, 'PENDING_SESSIONS', 0), patch.object(gateway, '_launch_session', side_effect=slow_start):
            thread = threading.Thread(target=launch)
            thread.start()
            try:
                self.assertTrue(ready.wait(2))
                acquired = gateway.LOCK.acquire(timeout=.5)
                self.assertTrue(acquired, 'Existing users must not wait on startup')
                if acquired: gateway.LOCK.release()
                with self.assertRaises(gateway.SessionCapacityError): gateway.create_session()
                self.assertEqual(gateway.PENDING_SESSIONS, 1)
            finally:
                release.set(); thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(gateway.PENDING_SESSIONS, 0)
            self.assertEqual(len(gateway.SESSIONS), 8)

    def test_failed_start_releases_reserved_capacity(self):
        with patch.object(gateway, 'SESSIONS', {}), patch.object(gateway, 'PENDING_SESSIONS', 0), patch.object(gateway, '_launch_session', side_effect=OSError('fixture failure')):
            with self.assertRaises(OSError): gateway.create_session()
            self.assertEqual(gateway.PENDING_SESSIONS, 0)
            self.assertEqual(gateway.SESSIONS, {})


if __name__ == '__main__': unittest.main()
