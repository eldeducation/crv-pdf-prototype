"""Regression tests on draft fixtures, using the same build/check steps as the editor loop.

The fixtures mirror patterns from real editor drafts (2026-11-06 runs) with
synthetic text and generated images, so no video content is stored in the repo.
Tests that render pages need Node/Playwright/Chrome and are skipped where those
are not set up (e.g. CI); the build/Markdown/revise tests always run.
"""
import copy
import json
import re
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

import pipeline
from presentation_quality import THEMES
from render_test_support import require_renderer

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'drafts'
PLAN = json.loads((FIXTURES / 'plan.json').read_text(encoding='utf-8'))
PRESENTATION = {'design': 'editorial', 'purpose': 'seminar'}
IMAGES = ('frame_001.jpg', 'frame_002.jpg', 'frame_003.jpg', 'frame_004.jpg')


def fixture(name):
    return json.loads((FIXTURES / f'{name}.json').read_text(encoding='utf-8'))['draft']


class DraftCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name)
        (self.out / 'assets').mkdir()
        for index, name in enumerate(IMAGES):
            picture = Image.new('RGB', (1280, 720), (40 + index * 40, 60, 90))
            ImageDraw.Draw(picture).text((40, 40), f'slide {index + 1}', fill='white')
            picture.save(self.out / 'assets' / name, quality=80)
        evidence = pipeline.Evidence.__new__(pipeline.Evidence)
        evidence.out, evidence.assets, evidence.source = self.out, (self.out / 'assets').resolve(), 'upload.mp4'
        evidence.records = [{'file': f'assets/{name}', 'seconds': 10.0 * (i + 1)} for i, name in enumerate(IMAGES)]
        self.evidence = evidence

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, draft):
        return pipeline.build_document(copy.deepcopy(draft), PLAN, PRESENTATION, self.evidence, 'ja')

    def check(self, draft):
        require_renderer(self)
        doc, markup = self.build(draft)
        (self.out / 'document.html').write_text(markup, encoding='utf-8')
        return pipeline.check_pages(self.out, doc)


def pages_of(markup):
    return markup.split('<section class="page">')


class BuildTest(DraftCase):
    def test_both_fixtures_pass_the_submission_gates(self):
        for name in ('kit_magazine', 'editor_own_classes'):
            doc, markup = self.build(fixture(name))
            self.assertEqual(len(pages_of(markup)) - 1, len(fixture(name)['pages']), name)

    def test_an_editor_written_markdown_field_does_not_change_the_pdf_source(self):
        draft = fixture('kit_magazine')
        _, plain = self.build(draft)
        _, with_markdown = self.build({**draft, 'markdown': '# 別の原稿\n\n内容が違う'})
        self.assertEqual(plain, with_markdown)

    def test_revising_one_page_changes_only_that_page(self):
        draft = fixture('kit_magazine')
        _, before = self.build(draft)
        same = pipeline.revised_draft(draft, {'pages': [{'page': 2, 'html': draft['pages'][1]['html']}]})
        self.assertEqual(self.build(same)[1], before)
        changed = pipeline.revised_draft(draft, {'pages': [{'page': 2, 'html': draft['pages'][1]['html'].replace('最初の試行', '最初の試行（改）')}],
                                                 'design_plan_pages': [{**draft['design_plan']['pages'][1], 'focus_excerpt': '最初の試行（改）'}]})
        differing = [i for i, (a, b) in enumerate(zip(pages_of(before), pages_of(self.build(changed)[1]))) if a != b]
        self.assertEqual(differing, [2])

    def test_generated_markdown_keeps_images_tags_and_lists(self):
        doc, markup = self.build(fixture('kit_magazine'))
        text = doc['markdown']
        self.assertEqual(set(re.findall(r'\]\((assets/[^)]+)\)', text)), set(re.findall(r'src="(assets/[^"]+)"', markup)))
        self.assertIn('&lt;final_verdict&gt;', text)
        self.assertIn('- 最終判定を', text)
        self.assertIn('## 01 最初の試行（PART 1　01:00 – 03:00）', text)
        self.assertNotIn('data-source-unit', text)

    def test_gate_problems_are_reported_together(self):
        draft = fixture('kit_magazine')
        broken = copy.deepcopy(draft)
        broken['design_plan']['pages'][0]['focus_excerpt'] = '本文にない要約'
        broken['pages'][1]['html'] += '<script>alert(1)</script>'
        with self.assertRaises(pipeline.PrototypeError) as caught:
            self.build(broken)
        message = str(caught.exception)
        self.assertIn('1ページ', message)
        self.assertIn('script', message)


class RenderTest(DraftCase):
    def test_kit_draft_renders_cleanly_in_every_theme(self):
        draft = fixture('kit_magazine')
        for theme in THEMES:
            qa = self.check({**draft, 'theme': theme})
            self.assertEqual(qa['errors'], [], theme)
            notes = [w for d in qa['design_diagnostics'] for w in d['warnings'] if '部品' in w or 'コントラスト' in w]
            self.assertEqual(notes, [], theme)

    def test_editor_style_draft_gets_the_findings_seen_in_real_runs(self):
        qa = self.check(fixture('editor_own_classes'))
        errors = ' '.join(qa['errors'])
        # The gray line inside the dark cover is unreadable (real run 6, contrast 1.6).
        self.assertIn('登壇者', errors)
        # A 30pt number with line-height .95 at the top of the page is not an overflow (real run 5).
        self.assertNotIn('はみ出し', errors)
        notes = {d['page']: ' '.join(d['warnings']) for d in qa['design_diagnostics']}
        self.assertIn('.kp→.keypoints', notes[1])
        self.assertIn('.flowh→.chevrons', notes[1])
        self.assertIn('.chap→.chapter', notes[2])
        self.assertIn('.vs→.versus', notes[2])
        self.assertNotIn('.ver→', notes[2])
        self.assertNotIn('.big→', notes[2])


if __name__ == '__main__':
    unittest.main()
