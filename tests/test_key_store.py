"""Optional 'save the key on this PC' (Windows DPAPI) and the fixed local address (offline)."""
import contextlib
import http.client
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

import key_store
import server
import share_gateway

FAKE = 'sk-or-v1-not-a-real-key-fixture-only'
REPO = Path(__file__).resolve().parent.parent


@unittest.skipUnless(os.name == 'nt', 'DPAPI is Windows-only')
class KeyStoreTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / 'repository'
        self.root.mkdir()

    def test_round_trip_is_encrypted_on_disk(self):
        key_store.save(self.root, FAKE)
        raw = (self.root / key_store.FILE_NAME).read_bytes()
        self.assertNotIn(FAKE.encode('utf-8'), raw)
        self.assertNotIn(b'sk-or-v1', raw)
        self.assertEqual(key_store.load(self.root), FAKE)
        key_store.delete(self.root)
        self.assertEqual(key_store.load(self.root), '')
        key_store.delete(self.root)                  # deleting twice is fine

    def test_damaged_file_reads_as_no_key(self):
        (self.root / key_store.FILE_NAME).write_bytes(b'not a dpapi blob')
        self.assertEqual(key_store.load(self.root), '')

    def test_never_available_in_shared_sessions_or_when_disabled(self):
        shared = self.root / 'work' / 'share-sessions' / 'abc'
        shared.mkdir(parents=True)
        self.assertFalse(key_store.available(shared))
        with self.assertRaises(OSError):
            key_store.save(shared, FAKE)
        self.assertFalse((shared / key_store.FILE_NAME).exists())
        with mock.patch.dict(os.environ, {'VIDEO_PDF_DISABLE_KEY_STORE': '1'}):
            self.assertFalse(key_store.available(self.root))


@unittest.skipUnless(os.name == 'nt', 'DPAPI is Windows-only')
class ServerKeyPersistenceTest(unittest.TestCase):
    def setUp(self):
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory())) / 'repository'
        self.root.mkdir()
        stack.enter_context(mock.patch.object(server, 'ROOT', self.root))
        saved = dict(server.STATE)
        stack.callback(lambda: (server.STATE.clear(), server.STATE.update(saved)))
        with server.LOCK:
            server.clear_connection()
            server.STATE['job'] = None
        service = server.LocalServer(('127.0.0.1', 0), server.Handler)
        service.daemon_threads = True
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        stack.callback(lambda: (service.shutdown(), service.server_close(), thread.join(5)))
        self.port = service.server_port

    def call(self, method, route, body=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        data = json.dumps(body).encode('utf-8') if body is not None else None
        headers = {'Host': f'127.0.0.1:{self.port}', 'X-CSRF-Token': server.CSRF_TOKEN,
                   'Content-Type': 'application/json'}
        try:
            connection.request(method, f'/{server.TOKEN}/{route}', data, headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def saved_file(self):
        return self.root / key_store.FILE_NAME

    def test_key_is_saved_only_when_asked(self):
        code, _ = self.call('POST', 'configure', {'api_key': FAKE})
        self.assertEqual(code, 200)
        self.assertFalse(self.saved_file().exists())
        code, status = self.call('GET', 'status')
        self.assertTrue(status['configured'])
        self.assertFalse(status['key_saved'])
        self.assertTrue(status['key_store_available'])

        code, _ = self.call('POST', 'configure', {'api_key': FAKE, 'remember': True})
        self.assertEqual(code, 200)
        self.assertTrue(self.saved_file().exists())
        self.assertTrue(self.call('GET', 'status')[1]['key_saved'])

        # A truthy value that is not exactly true is not consent.
        self.call('POST', 'configure', {'api_key': FAKE, 'remember': 'yes'})
        self.assertFalse(self.saved_file().exists())

    def test_disconnect_forgets_the_saved_key(self):
        self.call('POST', 'configure', {'api_key': FAKE, 'remember': True})
        self.assertTrue(self.saved_file().exists())
        code, _ = self.call('POST', 'disconnect', {})
        self.assertEqual(code, 200)
        self.assertFalse(self.saved_file().exists())
        status = self.call('GET', 'status')[1]
        self.assertFalse(status['configured'])
        self.assertFalse(status['key_saved'])

    def test_restart_restores_the_saved_key_and_idle_does_not_drop_it(self):
        key_store.save(self.root, FAKE)
        with server.LOCK:
            server.restore_saved_key()
            self.assertEqual(server.STATE['api_key'], FAKE)
            self.assertTrue(server.STATE['key_saved'])
            server.STATE['key_used_at'] = time.monotonic() - server.KEY_IDLE_SECONDS - 5
            server.expire_key()
            self.assertEqual(server.STATE['api_key'], FAKE)
            server.STATE['key_saved'] = False          # an unsaved key still expires
            server.expire_key()
            self.assertEqual(server.STATE['api_key'], '')

    def test_damaged_or_invalid_saved_key_is_ignored(self):
        key_store.save(self.root, 'not-a-key')
        with server.LOCK:
            server.restore_saved_key()
            self.assertEqual(server.STATE['api_key'], '')
            self.assertFalse(server.STATE.get('key_saved'))

    def test_shared_session_never_saves(self):
        shared = self.root / 'work' / 'share-sessions' / 'abc'
        shared.mkdir(parents=True)
        with mock.patch.object(server, 'ROOT', shared):
            code, _ = self.call('POST', 'configure', {'api_key': FAKE, 'remember': True})
            self.assertEqual(code, 200)
            self.assertFalse((shared / key_store.FILE_NAME).exists())
            status = self.call('GET', 'status')[1]
            self.assertFalse(status['key_saved'])
            self.assertFalse(status['key_store_available'])


class FixedAddressTest(unittest.TestCase):
    def test_second_server_cannot_take_a_port_in_use(self):
        first = server.LocalServer(('127.0.0.1', 0), server.Handler)
        self.addCleanup(first.server_close)
        with self.assertRaises(OSError):
            server.LocalServer(('127.0.0.1', first.server_port), server.Handler).server_close()

    def test_launcher_reuses_the_address_and_secret_files_are_ignored(self):
        launcher = (REPO / 'start_local.cmd').read_text(encoding='utf-8')
        self.assertIn('server.py --reuse-address', launcher)
        self.assertTrue(launcher.isascii())             # cmd.exe reads it before chcp
        ignored = (REPO / '.gitignore').read_text(encoding='utf-8').split()
        for name in ('server.local.json', key_store.FILE_NAME):
            self.assertIn(name, ignored)

    def test_shared_sessions_get_the_module(self):
        self.assertIn('key_store.py', share_gateway.COPY_FILES)

    def test_ui_sends_remember_only_from_the_checkbox(self):
        ui = (REPO / 'ui.js').read_text(encoding='utf-8')
        self.assertIn("remember:!$('rememberKeyLabel').hidden&&$('rememberKey').checked", ui)
        html = (REPO / 'index.html').read_text(encoding='utf-8')
        self.assertIn('id="rememberKeyLabel" hidden', html)


if __name__ == '__main__':
    unittest.main()
