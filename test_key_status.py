"""Key allowance lookup (GET /api/v1/key): amounts only, fixed host, no generation (offline)."""
import io
import json
import re
import unittest
from pathlib import Path
from unittest import mock

import model_catalog as catalog
import share_gateway

FAKE = 'sk-or-v1-not-a-real-key-fixture-only'
ROOT = Path(__file__).resolve().parent
RESPONSE = {'data': {'label': 'sk-or-v1-au7...890', 'creator_user_id': 'user_123', 'workspace_id': 'ws_1',
                     'limit': 15, 'limit_remaining': 0.8, 'limit_reset': 'monthly', 'usage': 14.2, 'usage_monthly': 14.2,
                     'is_free_tier': False,
                     'effective_budget': {'limit_usd': 50, 'remaining_usd': 17.5, 'reset_interval': 'weekly',
                                          'resets_at': '2026-11-16T00:00:00.000Z', 'spend_usd': 32.5}}}


def opener_returning(body):
    opener = mock.Mock()
    opener.open.return_value = io.BytesIO(json.dumps(body).encode('utf-8'))
    return opener


class KeyStatusTest(unittest.TestCase):
    def test_returns_amounts_only(self):
        opener = opener_returning(RESPONSE)
        with mock.patch('urllib.request.build_opener', return_value=opener):
            status = catalog.key_status(FAKE)
        self.assertEqual(status['limit_usd'], 15.0)
        self.assertEqual(status['remaining_usd'], 0.8)
        self.assertEqual(status['limit_reset'], 'monthly')
        self.assertEqual(status['usage_usd'], 14.2)
        self.assertEqual(status['budget']['remaining_usd'], 17.5)
        text = json.dumps(status)
        for secret in (FAKE, 'sk-or-v1', 'user_123', 'ws_1'):
            self.assertNotIn(secret, text)

    def test_request_goes_only_to_the_official_endpoint_with_get(self):
        opener = opener_returning(RESPONSE)
        with mock.patch('urllib.request.build_opener', return_value=opener):
            catalog.key_status(FAKE)
        request = opener.open.call_args[0][0]
        self.assertEqual(request.full_url, 'https://openrouter.ai/api/v1/key')
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(request.get_header('Authorization'), 'Bearer ' + FAKE)

    def test_no_limit_and_missing_budget_are_reported_as_none(self):
        body = {'data': {'limit': None, 'limit_remaining': None, 'usage': 3, 'limit_reset': None}}
        with mock.patch('urllib.request.build_opener', return_value=opener_returning(body)):
            status = catalog.key_status(FAKE)
        self.assertIsNone(status['limit_usd'])
        self.assertIsNone(status['budget'])
        self.assertEqual(status['usage_usd'], 3.0)

    def test_invalid_response_is_an_error_not_a_guess(self):
        with mock.patch('urllib.request.build_opener', return_value=opener_returning({'data': []})), \
                self.assertRaises(catalog.CatalogError):
            catalog.key_status(FAKE)

    def test_provider_explanation_of_a_rejection_is_shown_without_the_key(self):
        from openrouter_client import provider_reason
        body = {'error': {'code': 402, 'message': f'This request requires more credits, or fewer max_tokens. '
                                                    f'You requested up to 65536 tokens, but can only afford 812. key {FAKE}'}}
        error = mock.Mock()
        error.read.return_value = json.dumps(body).encode('utf-8')
        reason = provider_reason(error, FAKE)
        self.assertIn('can only afford 812', reason)
        self.assertNotIn(FAKE, reason)
        self.assertNotIn('sk-or-v1', reason)
        error.read.return_value = json.dumps({'error': {'message': 'To increase, visit https://openrouter.ai/workspaces/default/keys/72f4dde9 and adjust'}}).encode('utf-8')
        self.assertEqual(provider_reason(error, FAKE), 'To increase, visit [OpenRouter settings] and adjust')
        error.read.return_value = b'<html>gateway error</html>'
        self.assertEqual(provider_reason(error, FAKE), '')
        error.read.return_value = json.dumps({'error': {'message': 'x' * 900}}).encode('utf-8')
        self.assertEqual(len(provider_reason(error, FAKE)), 300)

    def test_routes_and_ui(self):
        self.assertTrue(share_gateway.allowed_route('POST', 'key-status'))
        self.assertFalse(share_gateway.allowed_route('GET', 'key-status'))
        ui = (ROOT / 'ui.js').read_text(encoding='utf-8')
        self.assertIn("api('key-status',{})", ui)
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertIn('id="keyStatus"', html)


if __name__ == '__main__':
    unittest.main()
