"""Regression coverage for distribution, old diagnostics and honest resume guidance."""
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
import zipfile

import app_version
import job_progress
import pipeline
import security
import server
from scripts.build_local import build

ROOT = Path(__file__).resolve().parent
REVISION = 'f' * 40
PRIVATE_URL = 'https://openrouter.ai/workspaces/default/keys/private-fixture-id'
FAKE_KEY = 'sk-or-v1-' + 'not-a-real-key-fixture' * 2


class OldDiagnosticsTests(unittest.TestCase):
    def test_nested_old_errors_are_sanitized_without_changing_originals(self):
        text = f'HTTP 402 {PRIVATE_URL} {FAKE_KEY}'
        source = {'error':text,'job':{'report':{'review_note':text,'notes':[text]}},
                  'url':'https://openrouter.ai/docs/quickstart','markdown':'# 元の原稿'}
        original = json.dumps(source)
        clean = security.public_errors(source)
        self.assertNotIn('private-fixture-id', json.dumps(clean))
        self.assertNotIn(FAKE_KEY, json.dumps(clean))
        self.assertIn('HTTP 402', clean['error'])
        self.assertEqual(clean['url'],source['url'])
        self.assertEqual(clean['markdown'],source['markdown'])
        self.assertEqual(json.dumps(source),original)

    def test_status_and_old_report_downloads_never_return_management_urls(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            folder=root/'runs/20261109-120000-abc123'
            folder.mkdir(parents=True)
            report={'live_ai':True,'status':'failed','quality_pipeline':'quality-first-v3',
                    'review_note':'HTTP 402 '+PRIVATE_URL,'error':'HTTP 402 '+PRIVATE_URL}
            raw=json.dumps(report)
            (folder/'run.json').write_text(raw)
            (folder/'review-notes.txt').write_text('HTTP 402 '+PRIVATE_URL)
            state={**server.STATE,'api_key':'','job':{'folder':folder.name,'report':report,'status':'failed'},'key_saved':False}
            with patch.object(server,'ROOT',root),patch.object(server,'STATE',state),patch.object(server,'TOKEN','test-token'),patch.object(server,'resume_fingerprint',return_value='fixture'):
                httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
                thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
                try:
                    for route in ('status','files/'+folder.name+'/run.json','files/'+folder.name+'/review-notes.txt'):
                        connection=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
                        try:
                            connection.request('GET','/test-token/'+route)
                            response=connection.getresponse();data=response.read().decode('utf-8')
                            self.assertEqual(response.status,200)
                            self.assertIn('HTTP 402',data)
                            self.assertNotIn('private-fixture-id',data)
                        finally: connection.close()
                finally:
                    httpd.shutdown();thread.join(5);httpd.server_close()
            self.assertEqual((folder/'run.json').read_text(),raw)
            self.assertIn('private-fixture-id',(folder/'review-notes.txt').read_text())


class ResumeTests(unittest.TestCase):
    def make_run(self, root, checkpoint=False, restyle=False):
        folder=root/'runs/20261109-120000-abc123';folder.mkdir(parents=True)
        evidence=folder/'work/crv';evidence.mkdir(parents=True)
        (evidence/'MANIFEST.txt').write_text('fixture')
        (evidence/'frames.json').write_text('{"frames":[{}]}')
        (folder/'evidence.json').write_text('{"frames":[{}]}')
        (folder/'progress.json').write_text(json.dumps({'current':'document','stages':{'prepare':{'state':'complete'},'analyze':{'state':'complete'},'document':{'state':'stopped'}}}))
        if checkpoint:
            (folder/'checkpoint-content_plan.state.json').write_text('{"completed":true}')
        report={'quality_pipeline':'quality-first-v3','resume_fingerprint':'same','evidence_dir':str(evidence),'stop_code':'credit'}
        if restyle: report['restyle_from']='20261108-120000-abc123'
        return folder,{'status':'failed','report':report}

    def test_completed_plan_without_editor_checkpoint_resumes_at_document(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,job=self.make_run(Path(temp),checkpoint=True)
            resume=job_progress.describe(folder,job,'same')['resume']
            self.assertTrue(resume['available'])
            self.assertEqual(resume['from_stage'],'document')
            self.assertTrue(resume['saved_checkpoint'])

    def test_older_restyle_is_revalidated_and_does_not_claim_reanalysis(self):
        with tempfile.TemporaryDirectory() as temp:
            folder,job=self.make_run(Path(temp),restyle=True)
            with patch('restyle.restyle_source',return_value=(None,None,{})) as validate:
                resume=job_progress.describe(folder,job,'same')['resume']
                validate.assert_called_once()
                self.assertEqual(resume['from_stage'],'document')
            with patch('restyle.restyle_source',side_effect=ValueError('unverified')):
                resume=job_progress.describe(folder,job,'same')['resume']
                self.assertEqual(resume['from_stage'],'analyze')
                self.assertEqual(resume['restart_reason'],'plan_checkpoint_missing')


class RendererFailureTests(unittest.TestCase):
    def test_real_render_error_is_not_a_skip(self):
        import test_saved_drafts as drafts
        with tempfile.TemporaryDirectory() as temp:
            case=drafts.DraftCase()
            case.out=Path(temp)
            with patch.object(drafts,'require_renderer'),patch.object(case,'build',return_value=({},'<html/>')),patch.object(pipeline,'check_pages',side_effect=RuntimeError('broken renderer')):
                with self.assertRaisesRegex(RuntimeError,'broken renderer'):
                    case.check({})

    def test_missing_prerequisites_skip_locally_but_fail_required_ci(self):
        from render_test_support import require_renderer
        with patch.object(pipeline,'runtime',return_value={'node':'/missing/fixture-node'}):
            with patch.dict(os.environ,{'VIDEO_PDF_REQUIRE_RENDER_TESTS':'0'}):
                with self.assertRaises(unittest.SkipTest):require_renderer(self)
            with patch.dict(os.environ,{'VIDEO_PDF_REQUIRE_RENDER_TESTS':'1'}):
                with self.assertRaises(AssertionError):require_renderer(self)


class PackageTests(unittest.TestCase):
    def test_exact_current_sources_and_no_private_runtime_are_packaged(self):
        with tempfile.TemporaryDirectory() as temp:
            source=Path(temp)/'source';source.mkdir()
            for name in app_version.APP_FILES:
                shutil.copyfile(ROOT/name,source/name)
            shutil.copyfile(ROOT/'editor.txt',source/'editor.txt')
            shutil.copytree(ROOT/'distribution',source/'distribution')
            for name in ('requirements.txt','SECURITY.md'):shutil.copyfile(ROOT/name,source/name)
            (source/'runtime.local.json').write_text('{"node":"C:/Private Person/node"}')
            (source/'api_key.local.dpapi').write_bytes(b'private fixture')
            (source/'.env').write_text('PRIVATE=fixture')
            (source/'runs').mkdir();(source/'runs/private.json').write_text('{}')
            one,two=Path(temp)/'one.zip',Path(temp)/'two.zip'
            build(one,REVISION,source);build(two,REVISION,source)
            self.assertEqual(one.read_bytes(),two.read_bytes())
            with zipfile.ZipFile(one) as archive:
                names=archive.namelist()
                self.assertFalse(any('/runs/' in n or '.dpapi' in n or n.endswith('/.env') for n in names))
                self.assertEqual(archive.read('crv-pdf-local/app/runtime.local.json'),b'{}\n')
                for name in ('cost_estimate.py','markdown_export.py','prompt_cache.py','video_upload.py','key_store.py'):
                    self.assertEqual(archive.read('crv-pdf-local/app/'+name),(ROOT/name).read_bytes())
                manifest=json.loads(archive.read('crv-pdf-local/MANIFEST.json'))
                self.assertEqual(manifest['revision'],REVISION)
                for name,digest in manifest['sha256'].items():
                    self.assertEqual(hashlib.sha256(archive.read('crv-pdf-local/'+name)).hexdigest(),digest)
                extracted=Path(temp)/'extracted';archive.extractall(extracted)
                version=app_version.version_info(extracted/'crv-pdf-local/app')
                self.assertEqual(version['revision'],REVISION)
                self.assertEqual(version['source_hash'],app_version.source_hash(ROOT))
                # The shared gateway deliberately changes language/banner markup.
                app=extracted/'crv-pdf-local/app'
                (app/'index.html').write_text((app/'index.html').read_text(encoding='utf-8')+'<!-- shared banner -->',encoding='utf-8')
                info=json.loads((app/'build-info.json').read_text())
                info['runtime_source_hash']=app_version.source_hash(app)
                (app/'build-info.json').write_text(json.dumps(info))
                self.assertEqual(app_version.version_info(app)['revision'],REVISION)
                (app/'server.py').write_text('# changed local source',encoding='utf-8')
                self.assertIsNone(app_version.version_info(app)['revision'])


if __name__=='__main__':unittest.main()
