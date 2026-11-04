from pathlib import Path
import http.client
import http.server
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import home_fetch
import home_fetch_agent as agent

URL = 'https://www.youtube.com/watch?v=Q2w4-mluYo0'
TOKEN = 'test-only-token-' + 'x' * 32


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.queue = home_fetch.HomeFetchQueue(Path(self.temp.name) / 'queue')

    def tearDown(self):
        self.temp.cleanup()

    def test_disabled_without_switch_or_env(self):
        self.assertIsNone(home_fetch.queue_dir({}))
        self.assertIsNone(home_fetch.queue_dir({home_fetch.QUEUE_ENV: self.temp.name}))
        self.assertEqual(home_fetch.queue_dir({home_fetch.QUEUE_ENV: str(self.queue.root)}), self.queue.root)

    def test_offline_agent_fails_fast_with_clear_message(self):
        with self.assertRaises(RuntimeError) as caught:
            home_fetch.request_download(self.queue.root, URL, self.temp.name)
        self.assertIn('自宅PC', str(caught.exception))
        self.assertEqual(list((self.queue.root / 'requests').iterdir()), [])

    def test_round_trip_places_files_where_crv_expects_them(self):
        self.queue.heartbeat()
        out = Path(self.temp.name) / 'crv'

        def pc():
            job = None
            while not job:
                job = self.queue.next(wait_seconds=0)
            self.assertEqual((job['url'], job['sub']), (URL, 'agent:auto'))
            data = b'v' * 3000
            self.assertEqual(self.queue.append(job['id'], 'source.mp4', 0, iter_reader(data[:2000]), 2000), 2000)
            # A retried part with a stale offset is ignored, not duplicated.
            self.assertEqual(self.queue.append(job['id'], 'source.mp4', 0, iter_reader(data[:2000]), 2000), 2000)
            self.queue.append(job['id'], 'source.mp4', 2000, iter_reader(data[2000:]), 1000)
            self.queue.append(job['id'], 'source.ja.vtt', 0, iter_reader(b'WEBVTT'), 6)
            self.queue.finish(job['id'], True)

        worker = threading.Thread(target=pc)
        worker.start()
        video = home_fetch.request_download(self.queue.root, URL, out, 'agent:auto', sleep=lambda s: time.sleep(0.01))
        worker.join()
        self.assertEqual(Path(video), out / 'source.mp4')
        self.assertEqual((out / 'source.mp4').stat().st_size, 3000)
        self.assertTrue((out / 'source.ja.vtt').is_file())
        self.assertEqual(list((self.queue.root / 'results').iterdir()), [])

    def test_failure_code_is_reported_without_details(self):
        self.queue.heartbeat()

        def pc():
            job = None
            while not job:
                job = self.queue.next(wait_seconds=0)
            self.queue.finish(job['id'], False, 'youtube_verification')

        threading.Thread(target=pc).start()
        with self.assertRaises(RuntimeError) as caught:
            home_fetch.request_download(self.queue.root, URL, self.temp.name, sleep=lambda s: time.sleep(0.01))
        self.assertIn('youtube_verification', str(caught.exception))

    def test_unclaimed_request_times_out_as_offline(self):
        self.queue.heartbeat()
        clock = iter([0, 0, 0, home_fetch.CLAIM_SECONDS + 1, home_fetch.CLAIM_SECONDS + 1])
        self.queue.heartbeat()
        with patch.object(home_fetch, 'agent_online', return_value=True), self.assertRaises(RuntimeError) as caught:
            home_fetch.request_download(self.queue.root, URL, self.temp.name, sleep=lambda s: None,
                                        now=lambda: next(clock, 10**9))
        self.assertIn('自宅PC', str(caught.exception))
        self.assertEqual(list((self.queue.root / 'requests').iterdir()), [])

    def test_uploads_reject_unknown_ids_names_and_sizes(self):
        with self.assertRaises(KeyError):
            self.queue.append('0' * 24, 'source.mp4', 0, iter_reader(b'x'), 1)
        (self.queue.root / 'requests' / ('a' * 24 + '.json')).write_text(json.dumps({'url': URL}), encoding='utf-8')
        job = self.queue.next(wait_seconds=0)
        for name in ('../escape.mp4', 'source.exe', 'other.mp4', 'source.ja.vtt.exe'):
            with self.assertRaises(ValueError):
                self.queue.append(job['id'], name, 0, iter_reader(b'x'), 1)
        with self.assertRaises(ValueError):
            self.queue.append(job['id'], 'source.mp4', 0, iter_reader(b''), home_fetch.MAX_PART_BYTES + 1)


def iter_reader(data):
    view = memoryview(data)
    position = [0]

    def read(n):
        chunk = bytes(view[position[0]:position[0] + n])
        position[0] += len(chunk)
        return chunk
    return read


class EndpointTests(unittest.TestCase):
    """Real HTTP against the cloud gateway handler on loopback."""

    @classmethod
    def setUpClass(cls):
        import cloud_entry
        cls.temp = tempfile.TemporaryDirectory()
        cls.queue = home_fetch.HomeFetchQueue(Path(cls.temp.name) / 'queue')
        handler = cloud_entry.CloudHandler
        cls.patches = [patch.object(handler, 'fetch_queue', cls.queue), patch.object(handler, 'fetch_digest', home_fetch.token_digest(TOKEN)),
                       patch.object(handler, 'fetch_failures', [])]
        for item in cls.patches:
            item.start()
        cls.server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        handler.public_origin = 'https://127.0.0.1:%d' % cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.origin = 'http://127.0.0.1:%d' % cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        for item in cls.patches:
            item.stop()
        cls.temp.cleanup()

    def call(self, path, token=TOKEN, body=b'', method='POST'):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=60)
        headers = {'Content-Length': str(len(body))}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        return response.status, json.loads(response.read() or b'{}')

    def test_token_required_and_invitation_login_not_bypassed(self):
        self.assertEqual(self.call('/home-fetch/next', token=None)[0], 401)
        self.assertEqual(self.call('/home-fetch/next', token='wrong-' + TOKEN)[0], 401)
        self.assertEqual(self.call('/home-fetch/next', method='GET')[0], 401)
        # The fetch token is not an app login.
        self.assertEqual(self.call('/' + 'status', method='GET')[0], 401)

    def test_agent_client_round_trip_over_http(self):
        self.queue.heartbeat()
        client = agent.Client(self.origin, TOKEN)
        out = Path(self.temp.name) / 'crv'
        result = {}
        waiter = threading.Thread(target=lambda: result.update(video=home_fetch.request_download(
            self.queue.root, URL, out, 'agent:auto', sleep=lambda s: time.sleep(0.05))))
        waiter.start()
        job = None
        for _ in range(5):
            job = client.next_job()
            if job:
                break
        self.assertEqual(job['url'], URL)
        folder = Path(self.temp.name) / 'pc'
        folder.mkdir()
        (folder / 'source.mp4').write_bytes(os.urandom(40_000))
        with patch.object(agent, 'PART', 16_000):
            client.upload(job['id'], folder / 'source.mp4')
        client.finish(job['id'], True)
        waiter.join(timeout=30)
        self.assertEqual(Path(result['video']).read_bytes(), (folder / 'source.mp4').read_bytes())


class CrvHookTests(unittest.TestCase):
    def test_youtube_context_routes_to_home_pc_only_when_enabled(self):
        import youtube_support
        import claude_real_video.core as core
        with tempfile.TemporaryDirectory() as temp:
            queue = home_fetch.HomeFetchQueue(Path(temp) / 'q')
            with patch.dict(os.environ, {home_fetch.QUEUE_ENV: str(queue.root)}), \
                    patch.object(home_fetch, 'request_download', return_value='source.mp4') as remote, \
                    patch.object(core, 'fetch_video', side_effect=AssertionError('no cloud download')):
                with youtube_support.youtube_context():
                    sub = core.remote_subtitle_lang(URL, 'ja')
                    self.assertEqual(sub, 'agent:ja')
                    self.assertEqual(core.fetch_video('https://youtu.be/Q2w4-mluYo0', temp, sub_lang=sub), 'source.mp4')
            remote.assert_called_once_with(queue.root, URL, temp, 'agent:ja')
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(home_fetch.QUEUE_ENV, None)
            with patch.object(core, 'fetch_video', return_value='direct.mp4'), youtube_support.youtube_context():
                self.assertEqual(core.fetch_video(URL, '.'), 'direct.mp4')

    def test_agent_finds_winget_ffmpeg_and_refuses_without_it(self):
        with tempfile.TemporaryDirectory() as temp:
            env = {'LOCALAPPDATA': temp, 'PATH': 'C:/other'}
            self.assertFalse(agent.ensure_ffmpeg(env, which=lambda name: None))
            folder = Path(temp) / 'Microsoft/WinGet/Packages/Gyan.FFmpeg_x/ffmpeg-9/bin'
            folder.mkdir(parents=True)
            (folder / 'ffmpeg.exe').touch(); (folder / 'ffprobe.exe').touch()
            self.assertTrue(agent.ensure_ffmpeg(env, which=lambda name: None))
            self.assertTrue(env['PATH'].startswith(str(folder)))

    def test_agent_rejects_unmerged_fragment(self):
        client = unittest.mock.Mock()
        with patch.object(agent, 'fetch', return_value=(Path('source.f136.mp4'), [])):
            agent.handle(client, {'id': 'c' * 24, 'url': URL, 'sub': 'agent:auto'})
        client.finish.assert_called_once_with('c' * 24, False, 'download_failed')
        client.upload.assert_not_called()

    def test_agent_rejects_non_youtube_requests(self):
        client = unittest.mock.Mock()
        agent.handle(client, {'id': 'b' * 24, 'url': 'https://example.com/watch?v=Q2w4-mluYo0'})
        client.finish.assert_called_once_with('b' * 24, False, 'rejected')


if __name__ == '__main__':
    unittest.main()
