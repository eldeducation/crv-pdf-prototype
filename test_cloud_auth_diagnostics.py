"""Offline regression checks: no API key, Render instance or video needed."""
import io
import json
import secrets
import time
import unittest
from contextlib import redirect_stdout
from email.message import Message
from unittest.mock import patch

import cloud_entry


class CloudAuthDiagnosticsTest(unittest.TestCase):
    def setUp(self):
        self.old_tokens = cloud_entry.CloudHandler.login_tokens
        cloud_entry.CloudHandler.login_tokens = {}
        self.token = secrets.token_urlsafe(32)
        cloud_entry.CloudHandler.login_tokens[self.token] = time.monotonic() + 28800
        self.handler = object.__new__(cloud_entry.CloudHandler)
        self.with_cookie()

    def tearDown(self):
        cloud_entry.CloudHandler.login_tokens = self.old_tokens

    def with_cookie(self):
        self.handler.headers = Message()
        self.handler.headers['Cookie'] = '__Host-video_access=' + self.token + '; video_session=opaque'

    def test_no_three_minute_expiry(self):
        self.assertTrue(self.handler.authenticated())
        with patch('cloud_entry.time.monotonic', return_value=time.monotonic()+240):
            self.assertTrue(self.handler.authenticated())

    def test_missing_cookie_is_identifiable(self):
        self.handler.headers = Message()
        self.assertFalse(self.handler.authenticated())
        self.assertEqual(self.handler.auth_denial_reason(), 'missing_login_cookie')

    def test_server_restart_equivalent_is_identifiable(self):
        cloud_entry.CloudHandler.login_tokens.clear()
        self.assertFalse(self.handler.authenticated())
        self.assertEqual(self.handler.auth_denial_reason(), 'login_token_not_in_server_memory')

    def test_diagnostic_never_prints_cookie_token(self):
        out = io.StringIO()
        with redirect_stdout(out):
            cloud_entry._diagnostic('auth_denied', boot='test', reason='missing_login_cookie')
        message = json.loads(out.getvalue())
        self.assertEqual(message['reason'], 'missing_login_cookie')
        self.assertNotIn(self.token, out.getvalue())

    def test_expired_token_is_reported_before_authentication_purges_it(self):
        cloud_entry.CloudHandler.login_tokens[self.token] = time.monotonic() - 1
        self.handler.command = 'POST'
        self.handler.path = '/opaque/stop'
        self.handler.public_origin = 'https://example.test'
        self.handler.headers['Host'] = 'example.test'
        self.handler.send = lambda *a, **k: None
        with patch('cloud_entry._sample_resources', return_value={}), patch('cloud_entry._diagnostic') as log:
            self.handler.do_GET()
        self.assertEqual(log.call_args.kwargs['reason'], 'expired_login_token')
        self.assertNotIn(self.token, cloud_entry.CloudHandler.login_tokens)

    def test_memory_sample_and_unavailable_cgroup(self):
        with patch('cloud_entry.Path.read_text', return_value='104857600'):
            self.assertEqual(cloud_entry._cgroup_memory_mib(), 100.0)
        with patch('cloud_entry.Path.read_text', side_effect=OSError):
            self.assertIsNone(cloud_entry._cgroup_memory_mib())

if __name__ == '__main__':
    unittest.main()
