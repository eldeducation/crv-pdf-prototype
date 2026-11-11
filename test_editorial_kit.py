import json
import re
import unittest
from pathlib import Path

from document_design import style_css
from presentation_quality import THEMES, theme_css

ROOT = Path(__file__).resolve().parent
KIT_CLASSES_EXPECTED = KIT_CLASSES = ['cover', 'kicker', 'cover-media', 'shot', 'tldr', 'keypoints', 'chapter', 'chevrons',
               'quote-xl', 'bigstat', 'point', 'versus', 'qa', 'lede', 'tiles', 'wrapup']


class EditorialKitTest(unittest.TestCase):
    def test_editorial_css_defines_every_kit_class(self):
        # .wrapup (the required closing summary) is in the base layout so every design styles it.
        css = style_css('editorial') + (ROOT / 'layout.css').read_text(encoding='utf-8')
        for name in KIT_CLASSES:
            self.assertRegex(css, r'\.' + re.escape(name) + r'[\s,{.:>]', name)

    def test_editor_prompt_only_names_defined_kit_classes(self):
        prompt = (ROOT / 'editor.txt').read_text(encoding='utf-8')
        css = style_css('editorial') + (ROOT / 'layout.css').read_text(encoding='utf-8')
        for name in KIT_CLASSES:
            self.assertIn(name, prompt)
        for name in set(re.findall(r'class="([a-z-]+)', prompt)):
            self.assertRegex(css, r'\.' + re.escape(name) + r'[\s,{.:>]', name)

    def test_authored_rules_for_kit_classes_are_dropped(self):
        from document_design import KIT_CLASSES, split_kit_rules
        self.assertEqual(sorted(KIT_CLASSES), sorted(KIT_CLASSES_EXPECTED))
        kept, removed = split_kit_rules('.chapter .num{font-size:24pt}\n.cover-sub{color:#444}'
                                        '.point{display:grid}.my-box,.tldr p{margin:0}.grid3{display:grid}')
        self.assertEqual(removed, ['.chapter .num', '.point', '.my-box,.tldr p'])
        self.assertIn('.cover-sub{color:#444}', kept)
        self.assertIn('.grid3{display:grid}', kept)
        self.assertNotIn('.point', kept)

    def test_flexible_kit_boxes_do_not_squeeze_unexpected_children(self):
        css = style_css('editorial')
        for name in ('point', 'chapter', 'qa'):
            self.assertRegex(css, r'\.' + name + r' \{ display: flex;')

    def test_authored_highlight_rules_cannot_restore_the_old_transparent_band(self):
        from document_design import split_kit_rules
        kept, removed = split_kit_rules('mark{background:linear-gradient(transparent,#333)}'
                                       'p > mark strong{color:white}.landmark{padding:1mm}')
        self.assertEqual(removed, ['mark', 'p > mark strong'])
        self.assertIn('.landmark', kept)

    def test_lookalikes_of_kit_components_are_found_per_page(self):
        from document_design import kit_lookalikes
        base = (ROOT / 'layout.css').read_text(encoding='utf-8') + style_css('editorial')
        css = ('.chap{display:flex}.chap .no{font-size:30pt}.kp{display:grid}.vs{display:grid}'
               '.flowh div{clip-path:polygon(0 0,90% 0,100% 50%,90% 100%,0 100%)}'
               '.ver{font-weight:700}.big{font-size:18pt}.grid3{display:grid}')
        pages = [{'html': '<div class="chap"><span class="no">01</span><h2>見出し</h2></div><div class="kp"><div>a</div></div>'},
                 {'html': '<div class="vs"><div>a</div><div>b</div></div><div class="flowh"><div>1</div></div>'},
                 {'html': '<table><tr><td class="ver">v1</td></tr></table><p class="big">強調</p><div class="grid3"></div>'
                          '<div class="chapter"><p class="no">02</p><div><h2>部品</h2></div></div>'}]
        found = kit_lookalikes(pages, css, base)
        self.assertEqual(found[0], [('chap', 'chapter'), ('kp', 'keypoints')])
        self.assertEqual(found[1], [('flowh', 'chevrons'), ('vs', 'versus')])
        self.assertNotIn(2, found)          # short generic names and real kit usage are not flagged

    def test_lookalike_note_is_added_to_page_diagnostics(self):
        import tempfile
        import pipeline
        qa = {'design_diagnostics': [{'page': 1, 'warnings': []}, {'page': 2, 'warnings': []}]}
        doc = {'css': '.chev div{clip-path:polygon(0 0,1% 0,0 1%)}',
               'pages': [{'html': '<p>本文</p>'}, {'html': '<div class="chev"><div>v1</div></div>'}]}
        with tempfile.TemporaryDirectory() as tmp:
            pipeline.note_kit_lookalikes(qa, doc, Path(tmp))
            saved = json.loads((Path(tmp) / 'layout-check.json').read_text(encoding='utf-8'))
        self.assertEqual(qa['design_diagnostics'][0]['warnings'], [])
        self.assertIn('.chev→.chevrons', qa['design_diagnostics'][1]['warnings'][0])
        self.assertEqual(saved, qa)

    def test_every_theme_sets_kit_colors(self):
        for theme in THEMES:
            css = theme_css(theme)
            for var in ('--heading-color', '--accent-soft', '--accent-strong', '--accent-mark'):
                self.assertIn(var, css, theme)

    def test_render_reports_sparse_pages_and_small_screenshots(self):
        source = (ROOT / 'render.cjs').read_text(encoding='utf-8')
        self.assertIn('occupied < 55', source)
        self.assertIn('bounds.width * 0.45', source)
        self.assertIn('.cover,.tldr,.keypoints', source)
        # Large digits with a tight line-height must not fail layout without visible overflow,
        # and an overflow error must say which element and text to fix.
        self.assertIn('parseFloat(style.fontSize) * 0.25', source)
        self.assertIn('文字「${text.slice(0,20)}」', source)

    def test_big_numbers_have_line_height_for_their_glyph_box(self):
        css = style_css('editorial')
        for selector in ('.chapter .no', '.bigstat .num', '.keypoints .no', '.tiles .num'):
            rule = css[css.index(selector + ' {'):]
            self.assertIn('line-height: 1.15;', rule[:rule.index('}')], selector)


if __name__ == '__main__':
    unittest.main()
