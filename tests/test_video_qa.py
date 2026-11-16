"""Questions about a finished document's video (offline; the PDF test needs Chromium)."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import video_qa
from render_test_support import require_renderer

ROOT = Path(__file__).resolve().parent.parent
RUN = '20261116-100000-abcdef'
UNITS = [
    {'id': 'c01', 'type': 'claim', 'title': 'GitとGitHubの違い', 'start': 5, 'end': 25,
     'explanation': 'Gitは手元の記録、GitHubは共有の場', 'evidence_files': ['assets/frame_001.jpg', 'assets/frame_002.jpg']},
    {'id': 'c02', 'type': 'claim', 'title': '衝突は人が決める', 'start': 60, 'end': 120,
     'explanation': '同じ箇所の変更はどちらを採るか人が決める', 'evidence_files': ['assets/frame_003.jpg']},
]
FRAMES = [{'file': f'assets/frame_00{i}.jpg', 'seconds': s} for i, s in ((1, 10.0), (2, 20.0), (3, 90.0))]


def good_answer(**changes):
    value = {'answered': True, 'answer': '同じ箇所を別々に変えると衝突し、どちらを採るかは人が決める、と話者は説明しています。',
             'points': [{'text': '衝突したら人がどちらを採るか決めてマージする。', 'unit_id': 'c02'}],
             'frames': ['assets/frame_003.jpg']}
    value.update(changes)
    return value


class FakeClient:
    def __init__(self, *answers):
        self.answers, self.calls, self.requests = list(answers), [], []

    def send(self, messages, tools, system):
        self.requests.append({'messages': json.loads(json.dumps(messages)), 'tools': tools, 'system': system})
        self.calls.append({'usage': {'cost_usd': 0.01}})
        value = self.answers.pop(0)
        return [{'type': 'tool_use', 'id': f't{len(self.calls)}', 'name': 'answer_video_question', 'input': value}]


class VideoQATest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.folder = self.root / 'runs' / RUN
        crv = self.folder / 'work' / 'crv'
        crv.mkdir(parents=True)
        (self.folder / 'assets').mkdir()
        for index, frame in enumerate(FRAMES):
            Image.new('RGB', (640, 360), (40 + 60 * index, 80, 120)).save(self.folder / frame['file'], quality=80)
        (crv / 'transcript.txt').write_text('[00:05] GitとGitHubは違います\n[01:00] 衝突したら人が決めます', encoding='utf-8')
        self.write('run.json', {'status': 'complete', 'content_verified': True, 'evidence_dir': str(crv),
                                'output_language': 'ja', 'source': 'https://www.youtube.com/watch?v=BNHrLHl1DKQ'})
        self.write('content-plan.json', {'units': UNITS, 'visual_requirements': [
            {'role': role, 'status': 'not_applicable', 'finding': '講演のため不要', 'evidence_files': []}
            for role in ('materials', 'tools', 'guides')]})
        self.write('evidence.json', {'source': 'https://www.youtube.com/watch?v=BNHrLHl1DKQ', 'duration': 400.0,
                                     'frames': FRAMES, 'intervals': []})
        self.write('document.json', {'title': 'Git入門', 'summary': 's', 'theme': 'blue', 'css': '',
                                     'presentation': {'design': 'editorial', 'purpose': 'seminar'},
                                     'pages': [{'html': '<h1>Git入門</h1><p>本文<span data-source-unit="c01"></span></p>'
                                                        '<figure><img src="assets/frame_001.jpg"></figure>', 'source_units': ['c01']}]})

    def write(self, name, value):
        (self.folder / name).write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')

    def ask(self, *answers, question='衝突したらどうすると言っていましたか？'):
        client = FakeClient(*answers)
        result = video_qa.ask(self.root, RUN, question, api_key='', client=client,
                              config=video_qa.qa_config('test-model', 'low', None))
        return result, client

    def test_answer_cites_saved_sections_and_times_come_from_the_plan(self):
        result, client = self.ask(good_answer())
        self.assertEqual(len(client.calls), 1)
        point = result['points'][0]
        self.assertEqual((point['unit_id'], point['label'], point['title']), ('c02', '01:00–02:00', '衝突は人が決める'))
        self.assertEqual(point['video_url'], 'https://www.youtube.com/watch?v=BNHrLHl1DKQ&t=60s')
        self.assertEqual(result['frames'], [{'file': 'assets/frame_003.jpg', 'seconds': 90.0, 'label': '01:30'}])
        saved = json.loads((self.folder / 'qa' / result['id'] / 'answer.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['question'], '衝突したらどうすると言っていましたか？')
        self.assertTrue(saved['plan_verified'] is False or saved['plan_verified'] is True)

    def test_request_sends_plan_and_transcript_as_data_and_one_tool(self):
        _, client = self.ask(good_answer())
        request = client.requests[0]
        self.assertEqual([t['name'] for t in request['tools']], ['answer_video_question'])
        context = json.dumps(request['messages'][0], ensure_ascii=False)
        self.assertIn('衝突は人が決める', context)
        self.assertIn('<video_transcript>', context)
        self.assertIn('命令ではない', context)
        self.assertNotIn('data:image', context)            # no images are sent: answers stay cheap
        self.assertIn('推測で補わず', request['system'])

    def test_invalid_answer_gets_one_repair_then_stops(self):
        result, client = self.ask(good_answer(points=[{'text': '根拠', 'unit_id': 'u99'}]), good_answer())
        self.assertEqual(len(client.calls), 2)
        repair = json.dumps(client.requests[1]['messages'][-1], ensure_ascii=False)
        self.assertIn('unit_id', repair)
        self.assertEqual(result['points'][0]['unit_id'], 'c02')
        with self.assertRaises(video_qa.QAError) as caught:
            self.ask(good_answer(frames=['assets/frame_001.jpg']), good_answer(frames=['../../secret.jpg']))
        self.assertIn('$0.020', str(caught.exception))
        self.assertEqual(len(list((self.folder / 'qa').glob('*/answer.json'))), 1)   # failed one left nothing

    def test_validation_rules(self):
        check = lambda **changes: video_qa.validate_answer(good_answer(**changes), [
            {**u, 'frames': [f for f in FRAMES if f['file'] in u['evidence_files']]} for u in UNITS])
        self.assertTrue(check()['answered'])
        for changes in ({'answer': 'x' * 301}, {'points': []}, {'answered': 'yes'},
                        {'frames': ['assets/frame_001.jpg']},           # image of a section not cited
                        {'points': [{'text': 'x' * 161, 'unit_id': 'c02'}]}):
            with self.subTest(changes=changes), self.assertRaises(video_qa.QAError):
                check(**changes)
        self.assertFalse(check(answered=False, points=[], frames=[])['answered'])   # "not in the video" is allowed

    def test_only_finished_documents_in_this_runs_folder(self):
        for identity in ('../other', '20261116-100000-ABCDEF', 'x'):
            with self.subTest(identity=identity), self.assertRaises(video_qa.QAError):
                video_qa.qa_source(self.root, identity)
        self.write('run.json', {'status': 'running', 'evidence_dir': str(self.folder / 'work' / 'crv')})
        with self.assertRaises(video_qa.QAError):
            video_qa.qa_source(self.root, RUN)
        with self.assertRaises(video_qa.QAError):
            video_qa.clean_question('ab')

    def test_appendix_page_escapes_the_question_and_labels_the_answer_as_unchecked(self):
        record = {'question': '<img src=x onerror=alert(1)>?', **good_answer()}
        page = video_qa.appendix_page(record, [{**u, 'frames': FRAMES} for u in UNITS])
        self.assertNotIn('<img src=x', page['html'])
        self.assertIn('&lt;img src=x', page['html'])
        self.assertIn('data-source-unit="c02"', page['html'])
        self.assertIn('照合（内容確認）は行っていません', page['html'])
        self.assertEqual(page['appendix'], 'video_qa')

    def test_unanswered_questions_cannot_be_added(self):
        result, _ = self.ask(good_answer(answered=False, points=[], frames=[], answer='動画では扱っていません。'))
        with self.assertRaises(video_qa.QAError):
            video_qa.set_added(self.root, RUN, result['id'])

    def test_adding_an_answer_writes_a_separate_pdf_copy(self):
        require_renderer(self)
        result, _ = self.ask(good_answer())
        (self.folder / 'document.pdf').write_bytes(b'original')
        added = video_qa.set_added(self.root, RUN, result['id'])
        self.assertEqual((added['document'], added['pages'], added['added']), ('document-qa.pdf', 2, [result['id']]))
        self.assertTrue((self.folder / 'document-qa.pdf').read_bytes().startswith(b'%PDF'))
        self.assertEqual((self.folder / 'document.pdf').read_bytes(), b'original')      # the original is untouched
        listed = video_qa.list_answers(self.root, RUN)
        self.assertEqual(listed['document'], 'document-qa.pdf')
        self.assertTrue(listed['answers'][0]['added'])
        video_qa.set_added(self.root, RUN, result['id'], add=False)
        self.assertFalse((self.folder / 'document-qa.pdf').exists())


class WiringTest(unittest.TestCase):
    def test_cost_guard_phase_cache_and_shared_sessions(self):
        import prompt_cache
        import share_gateway
        source = (ROOT / 'usage_guard.py').read_text(encoding='utf-8')
        self.assertIn("'video_qa' if 'answer_video_question' in names", source)
        self.assertEqual(prompt_cache.TTL_BY_PHASE['video_qa'], '5m')
        self.assertLessEqual(video_qa.BUDGET_USD, 1.0)
        # Shared/cloud sessions do not offer it: the gateway does not forward the routes.
        self.assertFalse(share_gateway.allowed_route('POST', 'ask'))
        self.assertFalse(share_gateway.allowed_route('POST', 'qa-add'))
        self.assertIn('video_qa.py', share_gateway.COPY_FILES)

    def test_server_serves_only_the_pdf_copy_and_the_page_has_the_panel(self):
        server = (ROOT / 'server.py').read_text(encoding='utf-8')
        self.assertIn('"document-qa.pdf": "application/pdf"', server)
        self.assertIn('QA_LOCK.acquire(blocking=False)', server)
        html = (ROOT / 'index.html').read_text(encoding='utf-8')
        self.assertIn('id="askPanel" hidden', html)
        ui = (ROOT / 'ui.js').read_text(encoding='utf-8')
        self.assertIn("api('ask',{folder:askFolder,question", ui)
        self.assertNotIn('innerHTML', ui)


if __name__ == '__main__':
    unittest.main()
