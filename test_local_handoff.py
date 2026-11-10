"""Offline distribution checks. Fixtures do not measure AI-generated quality."""
import argparse
import base64
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

import app_version
import server
from manual_client import ManualClient
from scripts.build_local import build
from usage_guard import BudgetStop

ROOT = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location('distribution_' + name, ROOT / 'distribution' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


handoff = load('ai_handoff')
setup = load('setup_local')
startup = load('start')


class PackageTests(unittest.TestCase):
    def test_handoff_included_and_generation_files_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp) / 'local.zip'
            build(target, 'a' * 40)
            with zipfile.ZipFile(target) as archive:
                for name in ('start.py', 'ai_handoff.py', 'START-HERE.md', 'AGENTS.md', 'CLAUDE.md'):
                    self.assertEqual(archive.read('crv-pdf-local/' + name), (ROOT / 'distribution' / name).read_bytes())
                baseline = json.loads(archive.read('crv-pdf-local/QUALITY-BASELINE.json'))
                self.assertEqual(baseline['source_hash'], app_version.source_hash(ROOT))
                for name in app_version.APP_FILES:
                    if name == 'runtime.local.json':
                        continue
                    data = archive.read('crv-pdf-local/app/' + name)
                    self.assertEqual(data, (ROOT / name).read_bytes())
                    self.assertEqual(hashlib.sha256(data).hexdigest(), baseline['sha256']['app/' + name])
                self.assertEqual(archive.read('crv-pdf-local/app/prompts/editor.txt'), (ROOT / 'editor.txt').read_bytes())

    def test_partial_setup_does_not_count_as_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'app').mkdir()
            py = setup.python_path(root); py.parent.mkdir(parents=True); py.touch()
            (root / 'app/runtime.local.json').write_text('{}')
            self.assertFalse(setup.is_ready(root))
            node = root / 'node'; node.touch()
            playwright = root / 'playwright'; playwright.mkdir(); (playwright / 'cli.js').touch()
            (root / 'app/runtime.local.json').write_text(json.dumps({'node':str(node), 'playwright':str(playwright)}))
            self.assertTrue(setup.is_ready(root))

    def test_first_start_sets_up_before_launch_and_check_only_never_installs(self):
        with patch.dict('sys.modules', {'setup_local':setup}), patch.object(setup, 'prerequisites'), \
                patch.object(setup, 'is_ready', return_value=False), patch.object(startup.subprocess, 'run') as run:
            with patch('sys.argv', ['start.py', '--no-browser']):
                startup.main()
            self.assertEqual(len(run.call_args_list), 2)
            self.assertIn('setup_local.py', run.call_args_list[0].args[0][1])
            self.assertEqual(run.call_args_list[1].args[0][-1], '--no-browser')
            run.reset_mock()
            with patch('sys.argv', ['start.py', '--check-only']):
                startup.main()
            run.assert_not_called()


class HandoffTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.app_root = self.root / 'app'; self.app_root.mkdir()
        self.folder = self.app_root / 'runs/20261110-120000-abcdef'
        self.cancel = threading.Event()
        self.client = ManualClient(self.folder, self.cancel)
        self.result = []
        self.worker_errors = []
        self.tools = [{'name':'record_fixture', 'description':'Test fixture only',
                       'input_schema':{'type':'object', 'properties':{'note':{'type':'string'}},
                                       'required':['note'], 'additionalProperties':False}}]
        self.image = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jvWQAAAAASUVORK5CYII=')
        def respond():
            try:
                self.result.append(self.client.send([{'role':'user','content':[
                    {'type':'text','text':'Fixture; not a video evaluation.'},
                    {'type':'image','source':{'type':'base64','media_type':'image/png',
                                            'data':base64.b64encode(self.image).decode()}}]}], self.tools, 'Fixture system.'))
            except BudgetStop as error:
                if not self.cancel.is_set(): self.worker_errors.append(error)
            except Exception as error:
                self.worker_errors.append(error)
        self.worker = threading.Thread(target=respond, daemon=True)
        self.worker.start()
        for _ in range(100):
            if self.client.status(): break
            self.cancel.wait(.01)
        self.assertTrue(self.client.status())
        state = {**server.STATE, 'api_key':'', 'job':{'status':'running', 'folder':self.folder.name, 'manual_mode':True}, 'key_saved':False}
        self.patches = [patch.object(server,'ROOT',self.app_root), patch.object(server,'STATE',state),
                        patch.object(server,'MANUAL_CLIENT',self.client), patch.object(server,'TOKEN','a'*24),
                        patch.object(server,'resume_fingerprint',return_value='fixture')]
        for item in self.patches: item.start()
        self.httpd = server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever,daemon=True); self.thread.start()
        self.record = self.app_root / 'server.local.json'
        self.record.write_text(json.dumps({'url':f'http://127.0.0.1:{self.httpd.server_port}/'+ 'a'*24 + '/'}))
        self.app = handoff.LocalApp(self.root)

    def tearDown(self):
        self.cancel.set(); self.worker.join(3)
        self.httpd.shutdown(); self.thread.join(3); self.httpd.server_close()
        for item in reversed(self.patches): item.stop()
        self.temp.cleanup()
        self.assertFalse(self.worker.is_alive())
        self.assertEqual(self.worker_errors, [])

    def reply(self, rid=None, tools=None):
        value = {'request_id':rid or self.client.status()['request_id'],
                 'tool_calls':tools if tools is not None else [{'name':'record_fixture','input':{'note':'offline fixture'}}]}
        path = self.root / 'reply.json'; path.write_text(json.dumps(value),encoding='utf-8-sig')
        return path

    def test_real_server_handoff_returns_identical_request_and_validated_reply(self):
        request = self.app.request()
        self.assertEqual(json.loads(Path(request['request_json']).read_text())['system'], 'Fixture system.')
        self.assertEqual(len(request['images']), 1)
        self.assertEqual(Path(request['images'][0]).read_bytes(), self.image)
        self.assertNotIn('csrf_token', json.dumps(request))
        self.assertNotIn('configured', self.app.status())
        self.assertEqual(self.app.submit(self.reply()), {'accepted':True})
        self.worker.join(3)
        self.assertEqual(self.result[0][0]['name'], 'record_fixture')
        self.assertIsNone(self.client.status())

    def test_stale_reply_rejected_without_consuming_pending_request(self):
        with self.assertRaises(ValueError): self.app.submit(self.reply(rid='b'*24))
        self.assertTrue(self.client.status())

    def test_server_still_rejects_unpermitted_tools_and_bad_schema(self):
        for calls in ([{'name':'invent_approval','input':{}}], [{'name':'record_fixture','input':{'note':42}}]):
            with self.assertRaises(ValueError): self.app.submit(self.reply(tools=calls))
            self.assertTrue(self.client.status())

    def test_no_relaunch_while_running_and_no_premature_results(self):
        with self.assertRaises(ValueError): self.app.start(argparse.Namespace())
        self.assertEqual(self.app.results()['files'], [])

    def test_only_loopback_record_is_accepted_and_traversal_is_rejected(self):
        for address in ('https://example.com/'+'a'*24+'/', 'http://127.0.0.1:80@evil.test/'+'a'*24+'/',
                        'http://localhost:80/'+'a'*24+'/', 'http://127.0.0.1:80/'+'a'*24+'/?next=evil'):
            self.record.write_text(json.dumps({'url':address}))
            with self.assertRaises(ValueError): handoff.LocalApp(self.root)
        with self.assertRaises(ValueError): self.app.run_folder('../../private')

    def test_start_uses_manual_mode_and_same_quality_settings(self):
        args = argparse.Namespace(url='https://www.youtube.com/watch?v=Q2w4-mluYo0', purpose='training',
                                  language='ja', detail='standard', mode=[], notes='', silent=False, no_research=False)
        with patch.object(self.app,'status',return_value={'status':'idle'}),patch.object(self.app,'call',return_value={}) as call:
            self.app.start(args)
        body = call.call_args.args[1]
        self.assertEqual(body['execution_mode'],'manual')
        self.assertEqual(body['design'],'editorial')
        self.assertEqual(body['detail_level'],'standard')
        self.assertTrue(body['external_research'])
        self.assertFalse(body['no_transcribe'])
        self.assertNotIn('api_key',body)


if __name__ == '__main__':
    unittest.main()
