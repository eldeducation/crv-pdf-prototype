import re
import unittest
from pathlib import Path

from document_design import style_css
from presentation_quality import THEMES, theme_css

ROOT = Path(__file__).resolve().parent
KIT_CLASSES_EXPECTED = KIT_CLASSES = ['cover', 'kicker', 'cover-media', 'shot', 'tldr', 'keypoints', 'chapter', 'chevrons',
               'quote-xl', 'bigstat', 'point', 'versus', 'qa', 'lede', 'tiles']


class EditorialKitTest(unittest.TestCase):
    def test_editorial_css_defines_every_kit_class(self):
        css = style_css('editorial')
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


if __name__ == '__main__':
    unittest.main()
