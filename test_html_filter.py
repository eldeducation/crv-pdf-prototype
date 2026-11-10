"""Page HTML filter: one rejection lists every problem; static SVG diagrams pass (offline).

On 2026-11-10 a run spent about $3 on three full rewrites, each rejected for one SVG
detail at a time (xmlns, then <marker>, then stroke-dasharray).
"""
import re
import tempfile
import unittest
from pathlib import Path

from PIL import Image

import pipeline

ROOT = Path(__file__).resolve().parent

ARROW_DIAGRAM = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 60" width="200" height="60">'
    '<defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto" markerUnits="strokeWidth">'
    '<path d="M0,0 L8,4 L0,8 z" fill="#235"/></marker>'
    '<linearGradient id="g"><stop offset="0" stop-color="#fff" stop-opacity="0.5"/><stop offset="1" stop-color="#235"/></linearGradient></defs>'
    '<rect x="0" y="0" width="60" height="40" fill="url(#g)" rx="4"/>'
    '<line x1="70" y1="20" x2="190" y2="20" stroke="#235" stroke-width="2" stroke-dasharray="6 4" '
    'stroke-linecap="round" marker-end="url(#arrow)"/>'
    '<text x="100" y="50" text-anchor="middle" dominant-baseline="middle" font-style="italic">main</text></svg>')


class Evidence:
    def __init__(self, out):
        self.out, self.source, self.records = out, 'https://www.youtube.com/watch?v=x', []
        self.assets = (out / 'assets').resolve()

    def safe_asset(self, relative):
        candidate = (self.out / relative).resolve()
        if not candidate.is_relative_to(self.assets) or not candidate.is_file():
            raise pipeline.PrototypeError('指定できる画像は、この資料のassetsフォルダ内だけです。')
        return candidate


class HtmlFilterTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        out = Path(tmp.name)
        (out / 'assets').mkdir()
        Image.new('RGB', (64, 48), 'red').save(out / 'assets' / 'a.jpg')
        self.evidence = Evidence(out)

    def page(self, markup):
        return pipeline.Fragment(self.evidence).result(markup)

    def rejection(self, markup):
        with self.assertRaises(pipeline.PrototypeError) as caught:
            self.page(markup)
        return str(caught.exception)

    def test_static_svg_diagram_with_arrows_dashes_and_gradients_passes(self):
        result = self.page(ARROW_DIAGRAM)
        self.assertIn('marker-end="url(#arrow)"', result)
        self.assertIn('stroke-dasharray="6 4"', result)
        self.assertIn('fill="url(#g)"', result)
        self.assertNotIn('xmlns', result)               # implied for inline SVG

    def test_external_and_active_svg_parts_stay_blocked(self):
        for markup, expected in [
                ('<svg><rect fill="url(https://example.com/x.svg#a)"/></svg>', 'SVGの外部参照'),
                ('<svg><line marker-end="url(data:image/svg+xml,x)"/></svg>', 'SVGの外部参照'),
                ('<svg><use href="#a"/></svg>', 'HTMLの use'),
                ('<svg><a href="https://example.com"><text>x</text></a></svg>', 'HTMLの a'),
                ('<svg><foreignObject><p>x</p></foreignObject></svg>', 'HTMLの foreignobject'),
                ('<svg><rect onclick="alert(1)"/></svg>', 'HTML属性 onclick'),
                ('<svg xmlns="http://example.com/other"></svg>', 'HTML属性 xmlns'),
                ('<p style="background:url(https://example.com/x.png)">x</p>', 'CSSに外部参照'),
                ('<script>alert(1)</script>', 'HTMLの script')]:
            with self.subTest(markup=markup):
                self.assertIn(expected, self.rejection(markup))

    def test_one_rejection_lists_every_problem_on_the_page(self):
        message = self.rejection('<svg><foo/><rect bar="1" baz="2"/></svg><iframe></iframe><p onclick="x">t</p>')
        for expected in ('HTMLの foo', 'HTML属性 bar', 'HTML属性 baz', 'HTMLの iframe', 'HTML属性 onclick'):
            self.assertIn(expected, message)
        self.assertNotIn('閉じタグ', message)          # a rejected tag does not cascade

    def test_problems_on_several_pages_are_reported_together_with_page_numbers(self):
        doc = {'title': 'T', 'pages': [
            {'html': '<svg><rect bar="1"/></svg><img src="assets/a.jpg">', 'source_units': []},
            {'html': '<p>ok</p><img src="assets/a.jpg">', 'source_units': []},
            {'html': '<svg><rect bar="1"/><foo></foo></svg>', 'source_units': []}]}
        with self.assertRaises(pipeline.PrototypeError) as caught:
            pipeline.document_html(doc, self.evidence, [])
        message = str(caught.exception)
        self.assertIn('1・3ページ: HTML属性 bar は使用できません。', message)
        self.assertIn('3ページ: HTMLの foo は使用できません。', message)

    def test_every_svg_part_the_editor_prompt_names_is_allowed(self):
        prompt = (ROOT / 'editor.txt').read_text(encoding='utf-8')
        line = next(l for l in prompt.splitlines() if l.startswith('SVGは'))
        tags = {t.lower() for t in re.findall(r'\b([a-zA-Z]+)\b', line.split('と、')[0]) if t != 'SVG'}
        self.assertEqual(tags - pipeline.ALLOWED_TAGS, set())
        for attribute in re.findall(r'\b(stroke-dasharray|marker-end)\b', prompt):
            self.assertIn(attribute, pipeline.ALLOWED_ATTRS)


if __name__ == '__main__':
    unittest.main()
