"""No cloud/AI calls: preservation, isolation, idempotency and bounded uploads."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import modal_bridge as bridge
from modal_contract import VERSION, identity


class BridgeTests(unittest.TestCase):
    def test_credentials_only_reach_session_client_not_decoders(self):
        from security import child_environment
        env = {'VIDEO_PDF_MODAL_URL': 'https://example.modal.run', 'VIDEO_PDF_MODAL_KEY': 'wk-test',
               'VIDEO_PDF_MODAL_SECRET': 'ws-test', 'VIDEO_PDF_MODAL_PROFILE': 'windows-compatible',
               'OPENROUTER_API_KEY': 'never-forward', 'PATH': 'test'}
        session = bridge.session_environment(env)
        self.assertEqual(session['VIDEO_PDF_MODAL_SECRET'], 'ws-test')
        self.assertNotIn('OPENROUTER_API_KEY', session)
        self.assertNotIn('VIDEO_PDF_MODAL_SECRET', child_environment(session))
        self.assertNotIn('VIDEO_PDF_MODAL_KEY', child_environment(session))

    def test_server_keeps_modal_credentials_out_of_its_environment(self):
        env = {'VIDEO_PDF_MODAL_URL': 'https://example.us-east.modal.run', 'VIDEO_PDF_MODAL_KEY': 'wk-test',
               'VIDEO_PDF_MODAL_SECRET': 'ws-test'}
        with patch.dict(os.environ, env), patch.dict(bridge._CREDENTIALS, {}, clear=True):
            bridge.take_credentials()
            self.assertNotIn('VIDEO_PDF_MODAL_KEY', os.environ)
            self.assertNotIn('VIDEO_PDF_MODAL_SECRET', os.environ)
            self.assertEqual(bridge.connection()[1], {'Modal-Key': 'wk-test', 'Modal-Secret': 'ws-test'})
        server = (ROOT / 'server.py').read_text(encoding='utf-8')
        self.assertLess(server.index('modal_bridge.take_credentials()'), server.index('LocalServer(('))
        self.assertNotIn('take_credentials', (ROOT / 'share_gateway.py').read_text(encoding='utf-8'))
        self.assertNotIn('take_credentials', (ROOT / 'cloud_entry.py').read_text(encoding='utf-8'))
        source = (ROOT / 'cloud_transcribe.py').read_text(encoding='utf-8')
        self.assertEqual(source.count('env=child_environment()'), 2)

    def test_https_target_cannot_redirect_secrets_to_arbitrary_hosts(self):
        values = {'VIDEO_PDF_MODAL_KEY': 'wk-test', 'VIDEO_PDF_MODAL_SECRET': 'ws-test'}
        for url in ('http://example.modal.run', 'https://example.com', 'https://example.modal.run@evil.com',
                    'https://example.modal.run:444', 'https://example.modal.run/other'):
            with self.subTest(url=url), patch.dict(os.environ, {**values, 'VIDEO_PDF_MODAL_URL': url}), self.assertRaises(bridge.ModalError):
                bridge.connection()
        with patch.dict(os.environ, {**values, 'VIDEO_PDF_MODAL_URL': 'https://example.us-east.modal.run'}):
            self.assertEqual(bridge.connection()[0], 'example.us-east.modal.run')

    def test_identity_preserves_all_extraction_and_speech_settings(self):
        options = {'version': VERSION, 'frame_width': 1280, 'max_frames': 96, 'no_transcribe': True,
                   'profile': 'windows-compatible'}
        original = identity('a'*64, options)
        self.assertEqual(original, identity('a'*64, dict(options)))
        for key, value in (('frame_width', 640), ('max_frames', 95), ('no_transcribe', False), ('profile', 'adaptive')):
            self.assertNotEqual(original, identity('a'*64, {**options, key: value}))

    def test_zip_traversal_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('../escape.txt', '/escape.txt', 'C:/escape.txt', '..\\escape.txt'):
                with self.subTest(name=name):
                    archive = root / 'test.zip'
                    with zipfile.ZipFile(archive, 'w') as bundle:
                        entry = zipfile.ZipInfo('fixture')
                        entry.filename = name  # preserve a hostile backslash even on Windows
                        bundle.writestr(entry, b'bad')
                    with self.assertRaises(bridge.ModalError):
                        bridge.unpack(archive, root / 'out')
            self.assertFalse((root / 'escape.txt').exists())
            archive = root / 'link.zip'
            info = zipfile.ZipInfo('link')
            info.create_system = 3
            info.external_attr = 0o120777 << 16
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr(info, '../escape')
            with self.assertRaises(bridge.ModalError):
                bridge.unpack(archive, root / 'out')

    def test_no_local_fallback_after_remote_error(self):
        import pipeline
        with patch.dict(os.environ, {'VIDEO_PDF_MODAL_URL': 'https://example.modal.run'}), patch.object(
                bridge, 'prepare', side_effect=bridge.ModalError('無料検証の上限です。')), patch.object(
                pipeline, 'run_preparation') as local:
            with tempfile.TemporaryDirectory() as temp, self.assertRaises(pipeline.PrototypeError):
                pipeline.extract('video.mp4', Path(temp) / 'evidence', pipeline.Config(no_transcribe=True))
            local.assert_not_called()

    def test_links_keep_the_existing_import_path(self):
        import pipeline
        with patch.dict(os.environ, {'VIDEO_PDF_MODAL_URL': 'https://example.modal.run'}),                 patch.object(bridge, 'prepare') as remote, patch.object(pipeline, 'run_preparation') as local,                 patch.object(pipeline.shutil, 'which', return_value='/bin/tool'):
            with tempfile.TemporaryDirectory() as temp:
                pipeline.extract('https://www.youtube.com/watch?v=N1P4VpXhrfo', Path(temp) / 'evidence',
                                 pipeline.Config(no_transcribe=True))
            remote.assert_not_called()
            local.assert_called_once()

    def test_reference_zip_is_unpacked_without_changing_image_bytes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'test.zip'
            payload = b'unchanged-evidence'
            with zipfile.ZipFile(archive, 'w') as bundle:
                bundle.writestr('frames/frame_001.jpg', payload)
            bridge.unpack(archive, root / 'out')
            self.assertEqual((root / 'out/frames/frame_001.jpg').read_bytes(), payload)


class FakeLedger(dict):
    def __getitem__(self, key):
        return copy.deepcopy(super().__getitem__(key))

    def __setitem__(self, key, value):
        super().__setitem__(key, copy.deepcopy(value))

    def get(self, key, default=None):
        return copy.deepcopy(super().get(key, default))

    def put(self, key, value, skip_if_exists=False):
        if skip_if_exists and key in self:
            return False
        self[key] = value
        return True


class BackendTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Modal/FastAPI are optional development dependencies, not required on Render.
        try:
            import modal
            import fastapi
        except ImportError:
            raise unittest.SkipTest('Install Modal and FastAPI to run backend API tests')
        sys.path.insert(0, str(ROOT / 'cloud'))
        import modal_backend
        from fastapi.testclient import TestClient
        cls.backend, cls.TestClient = modal_backend, TestClient

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.ledger = FakeLedger()
        self.volume = Mock()
        self.process = Mock()
        self.process.spawn.return_value = SimpleNamespace(object_id='fc-test')
        self.patches = [patch.object(self.backend, 'ledger', self.ledger),
                        patch.object(self.backend, 'volume', self.volume),
                        patch.object(self.backend, 'process', self.process),
                        patch.object(self.backend, 'job_path', lambda job: Path(self.temporary.name) / job)]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)
        self.client = self.TestClient(self.backend.make_api())
        self.addCleanup(self.client.close)

    def new_job(self, payload=b'video'):
        options = {'version': VERSION, 'frame_width': 1280, 'max_frames': 96,
                   'no_transcribe': True, 'profile': 'windows-compatible'}
        sha = hashlib.sha256(payload).hexdigest()
        job = identity(sha, options)
        body = {'id': job, 'sha256': sha, 'bytes': len(payload), 'extension': '.mp4', 'options': options}
        return job, body

    def test_submit_upload_and_start_are_idempotent(self):
        job, body = self.new_job()
        self.assertEqual(self.client.post('/jobs', json=body).status_code, 200)
        self.assertEqual(self.client.post('/jobs', json=body).status_code, 200)
        self.assertEqual(self.client.put(f'/jobs/{job}/source', content=b'video').status_code, 200)
        self.assertEqual(self.client.post(f'/jobs/{job}/start', json={}).status_code, 200)
        self.assertEqual(self.client.post(f'/jobs/{job}/start', json={}).status_code, 200)
        self.process.spawn.assert_called_once_with(job)
        self.assertEqual(self.ledger['call:' + job], 'fc-test')

    def test_wrong_uploaded_content_is_rejected_before_start(self):
        job, body = self.new_job()
        self.client.post('/jobs', json=body)
        self.assertEqual(self.client.put(f'/jobs/{job}/source', content=b'wrong').status_code, 400)
        self.assertEqual(self.client.post(f'/jobs/{job}/start', json={}).status_code, 409)
        self.process.spawn.assert_not_called()

    def test_monthly_quota_is_enforced_before_upload(self):
        from modal_contract import PREPARE_JOBS_PER_MONTH
        for n in range(PREPARE_JOBS_PER_MONTH):
            job, body = self.new_job(('video-' + str(n)).encode())
            self.assertEqual(self.client.post('/jobs', json=body).status_code, 200)
        job, body = self.new_job(b'fourth')
        self.assertEqual(self.client.post('/jobs', json=body).status_code, 429)
        self.assertNotIn(job, self.ledger)
        self.process.spawn.assert_not_called()

    def test_result_is_saved_before_the_job_reads_complete(self):
        source = (ROOT / 'cloud' / 'modal_backend.py').read_text(encoding='utf-8')
        body = source[source.index("partial.replace(folder / 'result.zip')"):source.index('except Exception as error:')]
        self.assertLess(body.index('volume.commit()'), body.index("status='complete'"))

    def test_stt_model_cannot_silently_switch_to_another_engine(self):
        job, body = self.new_job()
        body['options'].update(no_transcribe=False, stt_model='openai/whisper-1')
        body['id'] = job = identity(body['sha256'], body['options'])
        self.client.post('/jobs', json=body)
        self.client.put(f'/jobs/{job}/source', content=b'video')
        self.assertEqual(self.client.post(f'/jobs/{job}/start', json={}).status_code, 400)
        self.process.spawn.assert_not_called()


if __name__ == '__main__':
    unittest.main()
