"""Offline upload regressions, including a real 200 MiB gateway transfer."""
import contextlib
import hashlib
import http.client
import io
import json
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch

import server
import share_gateway as gateway
from video_upload import (UploadReceiver, upload_metadata, body_chunks, SHARED_MAX_BYTES,
                          CHUNK_BYTES, COPY_BYTES)


def headers(identity='a' * 24, offset=0, total=6):
    return {'X-Filename': 'sample.mp4', 'X-Upload-ID': identity,
            'X-Upload-Offset': str(offset), 'X-Upload-Size': str(total)}


class BoundedReader(io.BytesIO):
    def read(self, size=-1):
        if not 0 < size <= COPY_BYTES:
            raise AssertionError('An upload must be read in bounded blocks')
        return super().read(size)


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.completed = {}
        self.receiver = UploadReceiver(self.folder, self.completed)

    def tearDown(self):
        self.temp.cleanup()

    def test_only_complete_video_is_registered(self):
        first = self.receiver.receive(headers(), BoundedReader(b'abc'), 3)
        self.assertEqual(first, {'received': 3, 'complete': False})
        self.assertEqual(self.completed, {})
        final = self.receiver.receive(headers(offset=3), BoundedReader(b'def'), 3)
        self.assertTrue(final['complete'])
        self.assertEqual(self.completed[final['upload_id']].read_bytes(), b'abcdef')
        self.assertEqual(list(self.folder.glob('*.part')), [])
        with self.assertRaises(ValueError):
            self.receiver.receive(headers(), BoundedReader(b'xxx'), 3)
        self.assertEqual(self.completed[final['upload_id']].read_bytes(), b'abcdef')

    def test_wrong_order_or_changed_file_does_not_corrupt_saved_part(self):
        self.receiver.receive(headers(), BoundedReader(b'abc'), 3)
        for changed in (headers(offset=0), headers(offset=4), headers(offset=3, total=7),
                        {**headers(offset=3), 'X-Filename': 'other.mov'}):
            with self.assertRaises(ValueError):
                self.receiver.receive(changed, BoundedReader(b'def'), 3)
        self.receiver.receive(headers(offset=3), BoundedReader(b'def'), 3)
        self.assertEqual(next(iter(self.completed.values())).read_bytes(), b'abcdef')

    def test_truncated_upload_removes_only_its_partial_file(self):
        existing = self.folder / 'existing.mp4'
        existing.write_bytes(b'keep this')
        with self.assertRaisesRegex(ValueError, '中断'):
            self.receiver.receive(headers(), BoundedReader(b'ab'), 3)
        self.assertEqual(self.receiver.pending, {})
        self.assertEqual(self.completed, {})
        self.assertEqual(list(self.folder.iterdir()), [existing])
        self.assertEqual(existing.read_bytes(), b'keep this')

    def test_legacy_whole_file_upload_is_also_streamed(self):
        data = b'video' * 50000
        result = self.receiver.receive({'X-Filename': 'legacy.webm'}, BoundedReader(data), len(data))
        self.assertEqual(self.completed[result['upload_id']].read_bytes(), data)

    def test_metadata_rejects_oversize_missing_headers_and_traversal(self):
        invalid = [headers(total=SHARED_MAX_BYTES + 1), headers(identity='../bad'),
                   headers(offset=-1), {**headers(), 'X-Upload-Size': None},
                   {**headers(), 'Transfer-Encoding': 'chunked'},
                   {**headers(), 'X-Filename': 'bad.exe'}]
        for row in invalid:
            with self.subTest(row=row), self.assertRaises(ValueError):
                upload_metadata(row, 3, SHARED_MAX_BYTES)
        with self.assertRaises(ValueError):
            upload_metadata(headers(total=CHUNK_BYTES + 1), CHUNK_BYTES + 1, SHARED_MAX_BYTES)
        self.assertEqual(list(self.folder.iterdir()), [])

    def test_quota_reserves_remaining_bytes_of_incomplete_uploads(self):
        self.receiver.receive(headers(total=8), BoundedReader(b'ab'), 2, quota=10)
        with self.assertRaisesRegex(ValueError, '容量'):
            self.receiver.receive(headers(identity='b' * 24, total=4), BoundedReader(b'cd'), 2, quota=10)
        self.receiver.receive(headers(offset=2, total=8), BoundedReader(b'cdefgh'), 6, quota=10)
        self.assertEqual(next(iter(self.completed.values())).read_bytes(), b'abcdefgh')

    def test_abandoned_parts_expire_without_deleting_completed_files(self):
        self.receiver.receive(headers(), BoundedReader(b'abc'), 3)
        self.receiver.pending['a' * 24]['updated'] = time.monotonic() - 3601
        existing = self.folder / 'existing.mp4'
        existing.write_bytes(b'keep')
        self.receiver.receive(headers(identity='b' * 24, total=3), BoundedReader(b'new'), 3)
        self.assertEqual(existing.read_bytes(), b'keep')
        self.assertFalse((self.folder / ('a' * 24 + '.part')).exists())


class TrackingReader:
    max_read = 0

    def __init__(self, reader):
        self.reader = reader

    def read(self, size=-1):
        if size < 0:
            raise AssertionError('Unbounded gateway upload read')
        type(self).max_read = max(type(self).max_read, size)
        return self.reader.read(size)

    def __getattr__(self, name):
        return getattr(self.reader, name)


class TrackingGateway(gateway.Handler):
    def setup(self):
        super().setup()
        self.rfile = TrackingReader(self.rfile)


class GatewayHTTPTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.folder = root / 'work' / 'share-sessions' / 'fixture'
        self.folder.mkdir(parents=True)
        self.completed = {}
        self.receiver = UploadReceiver(self.folder / 'uploads', self.completed)
        self.stack.enter_context(patch.object(server, 'ROOT', self.folder))
        self.stack.enter_context(patch.object(server, 'UPLOAD_RECEIVER', self.receiver))
        self.stack.enter_context(patch.object(gateway, 'ROOT', root))
        self.backend = self.start_server(server.Handler)
        session = {'url': urllib.parse.urlsplit(f'http://127.0.0.1:{self.backend.server_port}/{server.TOKEN}/'),
                   'folder': self.folder, 'csrf_token': server.CSRF_TOKEN, 'process': Mock(poll=lambda: None),
                   'created_at': time.monotonic(), 'last_seen': time.monotonic()}
        self.stack.enter_context(patch.object(gateway, 'SESSIONS', {'test-session': session}))
        self.stack.enter_context(patch.object(gateway, 'audit_request'))
        (root / 'work' / 'sharing.local.json').write_text('{}', encoding='utf-8')
        self.front = self.start_server(TrackingGateway)
        TrackingReader.max_read = 0

    def start_server(self, handler):
        service = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        service.daemon_threads = True
        thread = threading.Thread(target=service.serve_forever, daemon=True)
        thread.start()
        def stop():
            service.shutdown()
            service.server_close()
            thread.join(5)
        self.stack.callback(stop)
        return service

    def post(self, body=b'abc', extra=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.front.server_port, timeout=30)
        request_headers = {'Origin': f'http://127.0.0.1:{self.front.server_port}',
                           'Cookie': 'video_session=test-session', 'X-CSRF-Token': server.CSRF_TOKEN,
                           **headers(), **(extra or {})}
        try:
            connection.request('POST', '/' + gateway.TOKEN + '/upload', body, request_headers)
            response = connection.getresponse()
            return response.status, json.loads(response.read())
        finally:
            connection.close()

    def test_real_200_mib_transfer_through_gateway_and_session_server(self):
        block = b'video-test-block' * (CHUNK_BYTES // 16)
        self.assertEqual(len(block), CHUNK_BYTES)
        expected = hashlib.sha256()
        for offset in range(0, SHARED_MAX_BYTES, len(block)):
            code, result = self.post(block, headers(offset=offset, total=SHARED_MAX_BYTES))
            self.assertEqual(code, 200, result)
            self.assertEqual(result['received'], offset + len(block))
            expected.update(block)
        self.assertTrue(result['complete'])
        path = self.completed[result['upload_id']]
        self.assertEqual(path.stat().st_size, SHARED_MAX_BYTES)
        actual = hashlib.sha256()
        with path.open('rb') as stream:
            for part in iter(lambda: stream.read(1024 * 1024), b''):
                actual.update(part)
        self.assertEqual(actual.hexdigest(), expected.hexdigest())
        self.assertLessEqual(TrackingReader.max_read, COPY_BYTES)
        self.assertEqual(list(path.parent.glob('*.part')), [])

    def test_gateway_rejects_declared_total_above_200_mib_before_writing(self):
        code, result = self.post(extra=headers(total=SHARED_MAX_BYTES + 1))
        self.assertEqual(code, 400, result)
        self.assertEqual(self.receiver.pending, {})
        self.assertEqual(self.completed, {})
        self.assertFalse((self.folder / 'uploads').exists())

    def test_csrf_and_session_checks_still_apply(self):
        code, _ = self.post(extra={'X-CSRF-Token': 'wrong'})
        self.assertEqual(code, 403)
        code, _ = self.post(extra={'Cookie': 'video_session=another-session'})
        self.assertEqual(code, 401)
        self.assertEqual(self.receiver.pending, {})

    def test_streaming_body_fails_on_early_eof(self):
        with self.assertRaises(ValueError):
            list(body_chunks(BoundedReader(b'abc'), 4))

    def test_ui_and_embedded_script_match(self):
        root = Path(__file__).resolve().parent
        html = (root / 'index.html').read_text(encoding='utf-8')
        script = html.split('<script>', 1)[1].split('</script>', 1)[0]
        self.assertEqual(script.strip(), (root / 'ui.js').read_text(encoding='utf-8').strip())
        self.assertIn('video_upload.py', gateway.COPY_FILES)


if __name__ == '__main__':
    unittest.main()
