"""Contrast check, content-check payload and restyle source list (no AI calls)."""
import inspect
import json
import re
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent


class ContrastCheckTest(unittest.TestCase):
    def test_render_checks_text_contrast_with_error_and_warning_levels(self):
        source = (ROOT / 'render.cjs').read_text(encoding='utf-8')
        self.assertIn('const contrastOf = el =>', source)
        self.assertIn("ratio < (large ? 2 : 3)", source)          # unreadable: blocks approval
        self.assertIn("ratio < (large ? 3 : 4.5)", source)        # low: design note
        self.assertIn("cs.backgroundImage !== 'none') return null", source)   # unknown background is skipped

    def test_kit_small_labels_use_the_dark_heading_colour(self):
        from document_design import style_css
        css = style_css('editorial')
        for selector in ('.tldr .label {', '.chapter .meta {', '.versus .tagline {', '.chevrons > .on {'):
            rule = css[css.index(selector):]
            self.assertIn('var(--heading-color)', rule[:rule.index('}')], selector)

    def test_inserted_source_time_follows_the_surrounding_text_colour(self):
        layout = (ROOT / 'layout.css').read_text(encoding='utf-8')
        rule = re.search(r'\.source-ref \{[^}]*\}', layout).group(0)
        self.assertIn('color: inherit', rule)
        self.assertNotIn('opacity', rule)


class ContentCheckPayloadTest(unittest.TestCase):
    def test_document_check_does_not_resend_generated_markdown(self):
        from content_quality import ContentQuality
        source = inspect.getsource(ContentQuality.review_document)
        self.assertNotIn('"markdown"', source)
        self.assertIn('"pages": document["pages"]', source)


class RestyleSourcesTest(unittest.TestCase):
    def test_lists_only_runs_that_pass_the_restyle_check(self):
        import server
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ('20261101-000000-aaaaaa', '20261102-000000-bbbbbb'):
                (root / 'runs' / name).mkdir(parents=True)
                (root / 'runs' / name / 'run.json').write_text('{}', encoding='utf-8')
                (root / 'runs' / name / 'document.json').write_text(json.dumps({'title': 'T ' + name}), encoding='utf-8')

            def check(base, identity):
                if identity.endswith('aaaaaa'):
                    raise ValueError('not verified')
                return Path(base) / 'runs' / identity, {'purpose': 'seminar', 'detail_level': 'detailed'}, {}

            with mock.patch.object(server, 'ROOT', root), mock.patch.object(server, 'restyle_source', side_effect=check):
                sources = server.restyle_sources()
        self.assertEqual([s['folder'] for s in sources], ['20261102-000000-bbbbbb'])
        self.assertEqual(sources[0]['title'], 'T 20261102-000000-bbbbbb')
        self.assertEqual(sources[0]['purpose'], 'seminar')

    def test_shared_gateway_allows_the_list_route(self):
        import share_gateway
        self.assertTrue(share_gateway.allowed_route('GET', 'restyle-sources'))
        self.assertFalse(share_gateway.allowed_route('POST', 'restyle-sources'))

    def test_ui_rebuilds_from_the_selected_source(self):
        ui = (ROOT / 'ui.js').read_text(encoding='utf-8')
        self.assertIn("restyle_from:source", ui)
        self.assertIn("fetch('restyle-sources')", ui)


if __name__ == '__main__':
    unittest.main()
