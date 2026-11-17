"""Speech-to-text through OpenRouter instead of local Whisper (offline: the API is faked)."""
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import cloud_transcribe
import pipeline

ROOT = Path(__file__).resolve().parent.parent
KEY = 'sk-or-v1-' + 'a' * 40


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def fake_api(replies):
    """opener that records each request and returns (or raises) the next reply."""
    calls = []

    def opener(request, timeout):
        calls.append({'url': request.full_url, 'headers': dict(request.header_items()),
                      'body': json.loads(request.data)})
        reply = replies[min(len(calls), len(replies)) - 1]
        if isinstance(reply, Exception):
            raise reply
        return FakeResponse(json.dumps(reply).encode())
    return opener, calls


def http_error(code):
    return urllib.error.HTTPError(cloud_transcribe.ENDPOINT, code, 'x', {}, io.BytesIO(b'{"error":"' + KEY.encode() + b'"}'))


def reply(*segments, seconds=3, cost=0.00002):
    return {'text': ' '.join(s[2] for s in segments), 'usage': {'seconds': seconds, 'cost': cost},
            'segments': [{'start': a, 'end': b, 'text': t} for a, b, t in segments]}


class RequestTest(unittest.TestCase):
    def test_segments_are_shifted_and_bad_ones_dropped(self):
        body = {'segments': [{'start': 0.5, 'end': 2.0, 'text': ' こんにちは '}, {'start': 3, 'end': 2, 'text': '逆'},
                             {'start': 'x', 'end': 4, 'text': '壊れ'}, {'start': 4, 'end': 5, 'text': '  '}]}
        self.assertEqual(cloud_transcribe.segments_from(body, 600), [{'start': 600.5, 'end': 602.0, 'text': 'こんにちは'}])

    def test_request_shape_needs_segment_times(self):
        opener, calls = fake_api([reply((0, 1, 'a'))])
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(b'ID3fake')
        try:
            cloud_transcribe.request(f.name, KEY, 'openai/whisper-large-v3', 'ja', opener)
        finally:
            os.unlink(f.name)
        sent = calls[0]
        self.assertEqual(sent['url'], 'https://openrouter.ai/api/v1/audio/transcriptions')
        self.assertEqual(sent['headers']['Authorization'], 'Bearer ' + KEY)
        self.assertEqual(sent['body']['response_format'], 'verbose_json')
        self.assertEqual(sent['body']['language'], 'ja')
        self.assertEqual(sent['body']['input_audio']['format'], 'mp3')
        self.assertTrue(set(cloud_transcribe.MODELS) <= {'openai/whisper-large-v3', 'openai/whisper-large-v3-turbo', 'openai/whisper-1'})

    def test_one_retry_for_busy_servers_none_for_refusals(self):
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(b'ID3fake')
        try:
            opener, calls = fake_api([http_error(503), reply((0, 1, 'a'))])
            cloud_transcribe.request(f.name, KEY, cloud_transcribe.DEFAULT_MODEL, None, opener, wait=0)
            self.assertEqual(len(calls), 2)
            self.assertNotIn('language', calls[0]['body'])
            opener, calls = fake_api([http_error(503), http_error(503), reply((0, 1, 'a'))])
            with self.assertRaises(cloud_transcribe.TranscribeError):
                cloud_transcribe.request(f.name, KEY, cloud_transcribe.DEFAULT_MODEL, None, opener, wait=0)
            self.assertEqual(len(calls), 2)                                   # never unlimited
            opener, calls = fake_api([http_error(402)])
            with self.assertRaises(cloud_transcribe.TranscribeError) as caught:
                cloud_transcribe.request(f.name, KEY, cloud_transcribe.DEFAULT_MODEL, None, opener, wait=0)
            self.assertEqual(len(calls), 1)
            self.assertIn('残高', str(caught.exception))
            self.assertNotIn(KEY, str(caught.exception))                      # provider body is not echoed
        finally:
            os.unlink(f.name)

    def test_model_choice_is_limited_to_models_with_times(self):
        with patch.dict(os.environ, {cloud_transcribe.MODEL_ENV: 'openai/gpt-4o-transcribe'}):
            with self.assertRaises(cloud_transcribe.TranscribeError):
                cloud_transcribe.model_from_env()
        with patch.dict(os.environ, {cloud_transcribe.MODEL_ENV: ''}):
            self.assertEqual(cloud_transcribe.model_from_env(), 'openai/whisper-large-v3')


@unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'ffmpeg is not installed')
class AudioTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.video = self.folder / 'tone.mp4'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=25',
                        '-f', 'lavfi', '-i', 'color=c=black:s=64x64:d=25', '-shortest', str(self.video)], check=True)

    def tearDown(self):
        self.tmp.cleanup()

    def test_writes_crv_transcript_files_and_a_record_without_the_key(self):
        opener, calls = fake_api([reply((0.0, 1.5, '最初の文'), (1.5, 3.0, '次の文'), seconds=25, cost=0.0002)])
        path = cloud_transcribe.transcribe(self.video, self.folder, 'ja', key=KEY, model='openai/whisper-large-v3', opener=opener)
        self.assertEqual(Path(path).read_text(encoding='utf-8'), '最初の文\n次の文\n')
        segments = json.loads((self.folder / 'transcript.json').read_text(encoding='utf-8'))['segments']
        self.assertEqual(segments[1], {'start': 1.5, 'end': 3.0, 'text': '次の文'})
        record = (self.folder / 'cloud-transcribe.json').read_text(encoding='utf-8')
        self.assertNotIn(KEY, record)
        self.assertEqual(json.loads(record)['cost_usd'], 0.0002)
        self.assertEqual(len(calls), 1)
        self.assertEqual(cloud_transcribe.summary(self.folder)['model'], 'openai/whisper-large-v3')
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()),
                         ['cloud-transcribe.json', 'tone.mp4', 'transcript.json', 'transcript.txt'])  # no audio left behind

    def test_long_audio_is_sent_in_pieces_with_source_times(self):
        opener, calls = fake_api([reply((1.0, 2.0, 'a')), reply((1.0, 2.0, 'b')), reply((1.0, 2.0, 'c'))])
        with patch.object(cloud_transcribe, 'CHUNK_SECONDS', 10):
            cloud_transcribe.transcribe(self.video, self.folder, None, key=KEY, model=cloud_transcribe.DEFAULT_MODEL, opener=opener)
        segments = json.loads((self.folder / 'transcript.json').read_text(encoding='utf-8'))['segments']
        self.assertEqual([(s['start'], s['text']) for s in segments], [(1.0, 'a'), (11.0, 'b'), (21.0, 'c')])
        self.assertEqual(len(calls), 3)

    def test_no_speech_returns_none_but_keeps_the_record(self):
        opener, _ = fake_api([{'text': '', 'segments': [], 'usage': {'seconds': 25, 'cost': 0.0002}}])
        self.assertIsNone(cloud_transcribe.transcribe(self.video, self.folder, None, key=KEY, model=cloud_transcribe.DEFAULT_MODEL, opener=opener))
        self.assertFalse((self.folder / 'transcript.json').exists())
        self.assertTrue((self.folder / 'cloud-transcribe.json').exists())


class WorkerTest(unittest.TestCase):
    def test_install_reads_the_key_from_stdin_only(self):
        import types
        core = types.SimpleNamespace(_transcribe_impl=lambda *a, **k: 'local', _whisper_available=lambda: False)
        with patch.dict(os.environ, {cloud_transcribe.FLAG_ENV: ''}):
            self.assertEqual(cloud_transcribe.install(core), [])
        with patch.dict(os.environ, {cloud_transcribe.FLAG_ENV: '1', cloud_transcribe.MODEL_ENV: ''}), \
                patch('sys.stdin', io.StringIO(KEY + '\n')):
            patches = cloud_transcribe.install(core)
            self.assertNotIn(KEY, os.environ.values())
        with patches[0], patches[1]:
            self.assertTrue(core._whisper_available())
            with patch.object(cloud_transcribe, 'transcribe', return_value='done') as call:
                self.assertEqual(core._transcribe_impl('v.mp4', 'out', 'ja', 'base', 5.0, None), 'done')
            self.assertEqual(call.call_args.kwargs, {'key': KEY, 'model': 'openai/whisper-large-v3'})
            with patch.object(cloud_transcribe, 'transcribe', side_effect=cloud_transcribe.TranscribeError('x')):
                self.assertIsNone(core._transcribe_impl('v.mp4', 'out', 'ja'))
        self.assertEqual(core._transcribe_impl(), 'local')
        with patch.dict(os.environ, {cloud_transcribe.FLAG_ENV: '1'}), patch('sys.stdin', io.StringIO('')):
            with self.assertRaises(cloud_transcribe.TranscribeError):
                cloud_transcribe.install(core)

    def test_worker_installs_before_crv_runs(self):
        source = (ROOT / 'crv_worker.py').read_text(encoding='utf-8')
        self.assertLess(source.index('cloud_transcribe.install(core)'), source.index('main()'))


class PipelineTest(unittest.TestCase):
    def extract(self, key, **config):
        captured = {}

        def fake_preparation(args, *, env, log, notify, secret=None):
            captured.update(args=[str(a) for a in args], env=dict(env), secret=secret)
        with tempfile.TemporaryDirectory() as tmp:
            video = Path(tmp) / 'v.mp4'
            video.write_bytes(b'x')
            with patch.object(pipeline.shutil, 'which', return_value='/bin/tool'), \
                    patch.object(pipeline, 'run_preparation', fake_preparation):
                pipeline.extract(video, Path(tmp) / 'run' / 'work' / 'crv', pipeline.Config(**config), notify=lambda m: None, api_key=key)
        return captured

    def test_key_only_on_stdin_and_only_when_chosen(self):
        sent = self.extract(KEY, cloud_transcribe=True)
        self.assertEqual(sent['secret'], KEY)
        self.assertEqual(sent['env'][cloud_transcribe.FLAG_ENV], '1')
        self.assertNotIn(KEY, ' '.join(sent['args']) + ' '.join(sent['env'].values()))
        self.assertIsNone(self.extract(KEY)['secret'])
        self.assertNotIn(cloud_transcribe.FLAG_ENV, self.extract(KEY)['env'])
        self.assertIsNone(self.extract(KEY, cloud_transcribe=True, no_transcribe=True)['secret'])

    def test_needs_an_openrouter_key(self):
        with self.assertRaises(pipeline.PrototypeError) as caught:
            self.extract('sk-ant-' + 'b' * 40, cloud_transcribe=True)
        self.assertIn('OpenRouter', str(caught.exception))

    def test_worker_environment_passes_the_flag_but_never_a_key(self):
        from security import child_environment
        env = child_environment({cloud_transcribe.FLAG_ENV: '1', cloud_transcribe.MODEL_ENV: 'm', 'OPENROUTER_API_KEY': KEY})
        self.assertEqual(env, {cloud_transcribe.FLAG_ENV: '1', cloud_transcribe.MODEL_ENV: 'm'})

    def test_secret_goes_to_stdin(self):
        source = (ROOT / 'pipeline.py').read_text(encoding='utf-8')
        self.assertIn("stdin=subprocess.PIPE if secret else subprocess.DEVNULL", source)
        self.assertIn("process.stdin.write(secret + '\\n')", source)
        self.assertIn("if step == 'transcribe' and secret:", source)        # no 'slow on a small CPU' warning
        self.assertNotIn('CPU', pipeline.CLOUD_TRANSCRIBE_STEP)

    def test_option_is_a_strict_bool(self):
        with self.assertRaises(ValueError):
            pipeline.Config(cloud_transcribe='yes')
        server = (ROOT / 'server.py').read_text(encoding='utf-8')
        self.assertIn("cloud_transcribe=body.get('cloud_transcribe', False) is True", server)
        self.assertIn("'cloud_transcribe': config.cloud_transcribe", (ROOT / 'pipeline.py').read_text(encoding='utf-8'))

    def test_screen_option(self):
        ui = (ROOT / 'ui.js').read_text(encoding='utf-8')
        self.assertIn("cloud_transcribe:$('cloudTranscribe').checked&&!$('silent').checked", ui)
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertIn('id="cloudTranscribe"', html)
        self.assertIn('映像は送らない', html)
        from app_version import APP_FILES
        self.assertIn('cloud_transcribe.py', APP_FILES)


if __name__ == '__main__':
    unittest.main()
