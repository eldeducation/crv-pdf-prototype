"""Every document ends with a summary (.wrapup) on its last page (offline; render test needs Chromium)."""
import tempfile
import unittest
from pathlib import Path

import pipeline
from markdown_export import document_markdown
from render_test_support import require_renderer

ROOT = Path(__file__).resolve().parent.parent

WRAPUP = ('<div class="wrapup"><p class="label">まとめ</p><h2>Gitは手元のセーブ、GitHubは共有の場</h2><ol>'
          '<li>Gitは手元の編集履歴を残すセーブ機能。<span data-source-unit="u01"></span></li>'
          '<li>まず覚えるのはbranch・commit・push・pull request・pullの5操作。</li>'
          '<li>変更が衝突したら、どちらを採るかは人が決める。</li></ol>'
          '<p class="next">次は実践編で、実際のリポジトリで試す。</p></div>')


def doc(*pages):
    return {'title': 'T', 'pages': [{'html': html} for html in pages]}


class WrapupCheckTest(unittest.TestCase):
    def test_last_page_with_a_summary_of_three_to_five_points_passes(self):
        self.assertIsNone(pipeline.wrapup_problem(doc('<p>本文</p>', '<p>本文</p>' + WRAPUP)))

    def test_missing_summary_is_one_clear_problem(self):
        message = pipeline.wrapup_problem(doc('<p>本文</p>', '<p>次回予告</p>'))
        self.assertIn('最後のページにまとめ', message)
        self.assertIn('class="wrapup"', message)

    def test_summary_must_be_on_the_last_page(self):
        self.assertIsNotNone(pipeline.wrapup_problem(doc(WRAPUP, '<p>次回予告</p>')))

    def test_summary_needs_three_to_five_points(self):
        two = '<div class="wrapup"><p class="label">まとめ</p><h2>結論</h2><ol><li>一</li><li>二</li></ol></div>'
        self.assertIn('現在2項目', pipeline.wrapup_problem(doc(two)))
        self.assertIsNone(pipeline.wrapup_problem(doc("<div class='card wrapup'><ol>" + '<li>x</li>' * 4 + '</ol></div>')))
        self.assertIsNotNone(pipeline.wrapup_problem(doc('<div class="wrapups"><ol>' + '<li>x</li>' * 4 + '</ol></div>')))

    def test_gate_reports_it_with_the_other_problems(self):
        import inspect
        source = inspect.getsource(pipeline.build_document)
        self.assertLess(source.index('wrapup_problem'), source.index('document_html('))

    def test_prompt_checklist_and_kit_describe_the_same_part(self):
        prompt = (ROOT / 'editor.txt').read_text(encoding='utf-8')
        self.assertIn('<div class="wrapup">', prompt)
        self.assertIn('class="wrapup"', pipeline.submission_checklist({'units': []}, 7, True))
        from document_design import KIT_CLASSES
        self.assertIn('wrapup', KIT_CLASSES)        # authored CSS for it is dropped like other kit parts
        self.assertIn('.wrapup li::before', (ROOT / 'layout.css').read_text(encoding='utf-8'))

    def test_markdown_keeps_the_label_heading_and_numbered_points(self):
        text = document_markdown(doc('<p>本文</p>', WRAPUP))
        self.assertIn('まとめ', text)
        self.assertIn('## Gitは手元のセーブ、GitHubは共有の場', text)
        self.assertIn('5操作', text)
        self.assertIn('次は実践編', text)


class WrapupRenderTest(unittest.TestCase):
    def test_summary_renders_readably_in_every_theme(self):
        require_renderer(self)
        from document_design import style_css
        from presentation_quality import theme_css
        for theme in ('green', 'red', 'blue', 'amber', 'purple', 'slate'):
            with self.subTest(theme=theme), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                css = (ROOT / 'layout.css').read_text(encoding='utf-8') + style_css('editorial') + theme_css(theme)
                (folder / 'document.html').write_text(
                    f'<!doctype html><html lang="ja"><meta charset="utf-8"><style>{css}</style>'
                    '<body data-document-design="editorial" data-document-purpose="seminar">'
                    f'<section class="page"><main class="page-content"><p>本文</p>{WRAPUP.replace("<span data-source-unit=\"u01\"></span>", "")}</main>'
                    '<footer class="page-foot"><span>t</span><span>01</span></footer></section></body></html>',
                    encoding='utf-8')
                result = pipeline.render(folder / 'document.html', folder)
                self.assertEqual(result['errors'], [])


if __name__ == '__main__':
    unittest.main()
