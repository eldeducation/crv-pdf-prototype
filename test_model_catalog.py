"""Offline catalogue/security regression tests; never invoke paid inference."""
import copy
import io
import json
import sys
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

MODULE_ROOT = Path(__file__).resolve().parent
if not (MODULE_ROOT / 'model_catalog.py').is_file(): MODULE_ROOT = MODULE_ROOT.parent
sys.path.insert(0, str(MODULE_ROOT))
import model_catalog as catalog
import server
from pipeline import Config

FAKE = 'sk-or-v1-not-a-real-key-fixture-only'


def router_model(mid='vendor/visual', **changes):
    return dict({'id': mid, 'name': mid, 'architecture': {'input_modalities': ['image', 'text'], 'output_modalities': ['text']},
                 'supported_parameters': ['tools', 'reasoning'], 'top_provider': {'max_completion_tokens': 64000}}, **changes)


class CatalogTests(unittest.TestCase):
    def test_all_provider_results_are_preserved_with_compatibility(self):
        rows = [router_model(), router_model('text/only', architecture={'input_modalities': ['text'], 'output_modalities': ['text']}),
                router_model('image/generate', architecture={'input_modalities': ['image'], 'output_modalities': ['image']}),
                router_model('no/tools', supported_parameters=[]), {'id': 'unknown/model'}]
        with patch.object(catalog, 'read_catalog', return_value={'data': rows}) as request:
            result = catalog.fetch_models(FAKE, 'openrouter')
        self.assertEqual(len(result['models']), 5)
        models = {m['id']: m for m in result['models']}
        self.assertEqual(models['vendor/visual']['compatibility'], 'supported')
        self.assertEqual(models['text/only']['reasons'], ['no_image'])
        self.assertEqual(models['image/generate']['reasons'], ['no_text'])
        self.assertEqual(models['no/tools']['reasons'], ['no_tools'])
        self.assertEqual(models['unknown/model']['compatibility'], 'unknown')
        self.assertEqual(request.call_args.args[0], 'https://openrouter.ai/api/v1/models/user?output_modalities=all')
        self.assertNotIn(FAKE, json.dumps(result))

    def test_anthropic_pagination_and_capabilities(self):
        first = {'data': [{'id': 'new-claude', 'display_name': 'New Claude', 'capabilities': {
            'image_input': {'supported': True}, 'thinking': {'supported': True, 'types': {'adaptive': {'supported': True}}},
            'effort': {'high': {'supported': True}, 'max': {'supported': True}}}}], 'has_more': True, 'last_id': 'a/b?c'}
        with patch.object(catalog, 'read_catalog', side_effect=[first, {'data': [{'id': 'older-claude'}], 'has_more': False}]) as request:
            models = catalog.fetch_models('sk-ant-not-real', 'anthropic')['models']
        self.assertEqual(len(models), 2)
        self.assertEqual(request.call_args.args[0], 'https://api.anthropic.com/v1/models?limit=1000&after_id=a%2Fb%3Fc')
        new = next(m for m in models if m['id'] == 'new-claude')
        self.assertEqual(new['efforts'], ['high', 'max'])
        self.assertTrue(new['adaptive'])

    def test_malformed_and_repeating_pagination_fail_without_partial_list(self):
        for response in ({'data': [{'id': ''}]}, {'data': [], 'has_more': True, 'last_id': ''}):
            with patch.object(catalog, 'read_catalog', return_value=response), self.assertRaises(catalog.CatalogError):
                catalog.fetch_models(FAKE, 'anthropic')
        with patch.object(catalog, 'read_catalog', return_value={'data': [], 'has_more': True, 'last_id': 'same'}), self.assertRaises(catalog.CatalogError):
            catalog.fetch_models(FAKE, 'anthropic')

    def test_credentials_only_in_fixed_provider_header_and_get_only(self):
        opener = unittest.mock.Mock()
        opener.open.return_value = io.BytesIO(b'{"data":[]}')
        with patch('urllib.request.build_opener', return_value=opener):
            catalog.read_catalog('https://openrouter.ai/api/v1/models/user', FAKE, 'openrouter', 4)
        req = opener.open.call_args.args[0]
        self.assertEqual(req.get_method(), 'GET')
        self.assertEqual(req.get_header('Authorization'), 'Bearer ' + FAKE)
        self.assertNotIn(FAKE, req.full_url)
        self.assertIsNone(req.data)

    def test_redirects_never_forward_credentials(self):
        with self.assertRaises(catalog.CatalogError):
            catalog.NoRedirect().redirect_request(None, None, 302, 'redirect', {}, 'https://untrusted.invalid')
        with patch('urllib.request.build_opener', side_effect=AssertionError('Must not send credentials')), self.assertRaises(catalog.CatalogError):
            catalog.read_catalog('https://untrusted.invalid/v1/models', FAKE, 'openrouter', 4)

    def test_extra_fees_are_not_advertised_as_supported(self):
        model = catalog.normalize(router_model(pricing={'prompt': '0.0001', 'image': '0.01'}), 'openrouter')
        self.assertEqual(model['compatibility'], 'unsupported')
        self.assertIn('extra_pricing', model['reasons'])

    def test_provider_error_body_and_key_are_never_exposed(self):
        opener = unittest.mock.Mock()
        opener.open.side_effect = urllib.error.HTTPError('https://openrouter.ai/api/v1/models/user', 401, FAKE, {}, io.BytesIO(FAKE.encode()))
        with patch('urllib.request.build_opener', return_value=opener), self.assertRaises(catalog.CatalogError) as error:
            catalog.read_catalog('https://openrouter.ai/api/v1/models/user', FAKE, 'openrouter', 4)
        self.assertEqual(error.exception.code, 'authentication')
        self.assertNotIn(FAKE, str(error.exception))

    def test_oversized_and_invalid_response_rejected(self):
        for raw in (b'x' * 32, b'[]', b'{"data":{}}'):
            opener = unittest.mock.Mock();opener.open.return_value = io.BytesIO(raw)
            with patch('urllib.request.build_opener', return_value=opener), patch.object(catalog, 'MAX_BYTES', 24), self.assertRaises(catalog.CatalogError):
                catalog.read_catalog('https://openrouter.ai/api/v1/models/user', FAKE, 'openrouter', 4)

    def test_default_generation_payload_is_unchanged(self):
        payload = {'max_tokens': 32768, 'thinking': {'type': 'adaptive'}, 'output_config': {'effort': 'xhigh'}}
        before = copy.deepcopy(payload)
        catalog.apply_model_options(payload, None, 'anthropic', 'xhigh')
        self.assertEqual(payload, before)
        options = {'adaptive': True, 'reasoning': True, 'efforts': ['high', 'xhigh', 'max'], 'max_output_tokens': 128000}
        catalog.apply_model_options(payload, options, 'anthropic', 'xhigh')
        self.assertEqual(payload, before)

    def test_non_reasoning_router_and_provider_output_limit(self):
        payload = {'reasoning': {'effort': 'xhigh'}, 'max_tokens': 32768, 'tools': ['unchanged'], 'messages': ['unchanged']}
        catalog.apply_model_options(payload, {'reasoning': False, 'max_output_tokens': 16000}, 'openrouter', 'xhigh')
        self.assertNotIn('reasoning', payload)
        self.assertEqual(payload['max_tokens'], 16000)
        self.assertEqual(payload['tools'], ['unchanged'])
        self.assertEqual(payload['messages'], ['unchanged'])

    def test_anthropic_classic_thinking_and_effort_compatibility(self):
        payload = {'max_tokens': 16000, 'thinking': {'type': 'adaptive'}, 'output_config': {'effort': 'high'}}
        catalog.apply_model_options(payload, {'adaptive': False, 'thinking_enabled': True, 'reasoning': True}, 'anthropic', 'high')
        self.assertEqual(payload['thinking'], {'type': 'enabled', 'budget_tokens': 8192})
        self.assertNotIn('output_config', payload)
        with self.assertRaises(ValueError):
            catalog.apply_model_options({}, {'efforts': ['high']}, 'anthropic', 'max')


class CatalogSessionTests(unittest.TestCase):
    def setUp(self):
        self.old = server.STATE
        server.STATE = {'api_key': FAKE, 'job': None, 'key_used_at': time.monotonic(), 'key_revision': 1, 'catalog': None, 'catalog_attempt': 0}

    def tearDown(self):
        server.STATE = self.old

    def result(self):
        return {'models': [catalog.normalize(router_model(), 'openrouter')], 'provider': 'openrouter', 'fetched_at': time.time()}

    def test_catalogue_is_cached_and_provider_call_does_not_hold_job_lock(self):
        def provider(*_):
            self.assertTrue(server.LOCK.acquire(False))
            server.LOCK.release()
            return self.result()
        with patch.object(server, 'fetch_models', side_effect=provider) as request:
            first = server.model_catalog()
            self.assertEqual(server.model_catalog(), first)
            self.assertEqual(request.call_count, 1)
        self.assertNotIn(FAKE, json.dumps(first))

    def test_disconnect_and_expiry_invalidate_catalogue(self):
        server.STATE['catalog'] = self.result()
        with server.LOCK: server.clear_connection()
        self.assertIsNone(server.STATE['catalog'])
        self.assertEqual(server.STATE['key_revision'], 2)
        with self.assertRaises(catalog.CatalogError): server.model_catalog()
        server.STATE.update(api_key=FAKE, key_used_at=0, catalog=self.result())
        with server.LOCK: server.expire_key()
        self.assertFalse(server.STATE['api_key'])
        self.assertIsNone(server.STATE['catalog'])

    def test_in_flight_old_key_result_is_discarded_after_key_change(self):
        started, finish = threading.Event(), threading.Event()
        errors = []
        def provider(*_):
            started.set();self.assertTrue(finish.wait(2));return self.result()
        def request():
            try: server.model_catalog()
            except catalog.CatalogError as error: errors.append(error.code)
        with patch.object(server, 'fetch_models', side_effect=provider):
            thread = threading.Thread(target=request);thread.start();self.assertTrue(started.wait(2))
            with server.LOCK:
                server.clear_connection();server.STATE['api_key'] = FAKE + '-new'
            finish.set();thread.join(2)
        self.assertEqual(errors, ['changed'])
        self.assertIsNone(server.STATE['catalog'])

    def test_failed_authentication_does_not_become_available_or_retry_on_poll(self):
        with patch.object(server, 'fetch_models', side_effect=catalog.CatalogError('authentication', 400)) as request:
            with self.assertRaises(catalog.CatalogError): server.model_catalog()
            with self.assertRaises(catalog.CatalogError): server.model_catalog()
            self.assertEqual(request.call_count, 1)
        self.assertIsNone(server.STATE['catalog'])

    def test_session_gateway_copies_module_and_allows_only_post(self):
        import share_gateway
        self.assertIn('model_catalog.py', share_gateway.COPY_FILES)
        self.assertTrue(share_gateway.allowed_route('POST', 'models'))
        self.assertFalse(share_gateway.allowed_route('GET', 'models'))


if __name__ == '__main__': unittest.main()
