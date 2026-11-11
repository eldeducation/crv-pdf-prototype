"""Contrast check, content-check payload and restyle source list (no AI calls)."""
import inspect
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from render_test_support import require_renderer

ROOT = Path(__file__).resolve().parent


class ContrastCheckTest(unittest.TestCase):
    def test_render_checks_text_contrast_with_error_and_warning_levels(self):
        source = (ROOT / 'render.cjs').read_text(encoding='utf-8')
        self.assertIn('const contrastOf = el =>', source)
        self.assertIn("ratio < (critical ? required : (large ? 2 : 3))", source)
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


class ContrastRenderTest(unittest.TestCase):
    """Renders real pages (skipped where Node/Playwright/Chrome are not set up, e.g. CI)."""

    def render(self, body, design='editorial', theme='amber'):
        require_renderer(self)
        import pipeline
        from document_design import style_css
        from presentation_quality import theme_css
        css = (ROOT / 'layout.css').read_text(encoding='utf-8') + style_css(design) + theme_css(theme)
        folder = Path(self.tmp.name)
        (folder / 'document.html').write_text(
            f'<!doctype html><html lang="ja"><meta charset="utf-8"><style>{css}</style>'
            f'<body data-document-design="{design}" data-document-purpose="seminar">'
            f'<section class="page"><main class="page-content">{body}</main><footer class="page-foot"><span>t</span><span>01</span></footer></section>'
            f'</body></html>', encoding='utf-8')
        return pipeline.render(folder / 'document.html', folder)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_unreadable_text_is_an_error_and_low_contrast_a_note(self):
        result = self.render(
            '<div style="background:#6f4914;padding:5mm"><p style="color:#44403c">読めない灰色の行</p></div>'
            '<p style="color:#8a8a8a">やや薄い灰色の本文です</p>'
            '<p>普通の本文です。</p>')
        errors = ' '.join(result['errors'])
        self.assertIn('読めない灰色の行', errors)
        self.assertNotIn('普通の本文', errors)
        self.assertNotIn('やや薄い灰色', errors)
        warnings = ' '.join(w for d in result['design_diagnostics'] for w in d['warnings'])
        self.assertIn('コントラストが低い', warnings)

    def test_kit_cover_and_source_time_are_readable(self):
        result = self.render(
            '<div class="cover"><span class="kicker">SEMINAR</span><h1>題名<em>強調</em></h1>'
            '<p class="sub">副題 <small class="source-ref">[00:00–00:19]</small></p></div>'
            '<div class="tldr"><p class="label">ひとことで言うと</p><p class="line">要点の文。</p></div>'
            '<div class="chapter"><p class="no">01</p><div><p class="meta">PART 1　02:00 – 08:35</p><h2>見出し</h2></div></div>')
        self.assertEqual([e for e in result['errors'] if 'コントラスト' in e or '読めません' in e], [])

    def test_highlights_are_measurable_and_readable_on_every_theme(self):
        from presentation_quality import THEMES
        for theme in THEMES:
            with self.subTest(theme=theme):
                result = self.render(
                    '<div class="cover"><h1>題名</h1><p class="sub">説明の<mark>強調部分</mark></p></div>'
                    '<div class="tldr"><p class="line">ロープの先に<mark>大きさが変わらない輪</mark>を作る。</p></div>'
                    '<div class="point"><p>暗い枠の<mark><strong>重要な説明</strong></mark></p></div>', theme=theme)
                self.assertEqual(result['errors'], [])
                warnings = ' '.join(w for d in result['design_diagnostics'] for w in d['warnings'])
                self.assertNotIn('コントラストが低い', warnings)

    def test_a_gradient_highlight_cannot_silently_skip_colour_validation(self):
        result = self.render('<p><mark style="background:linear-gradient(transparent 58%,#333 58%);color:#222">暗い帯の強調</mark></p>')
        self.assertTrue(any('暗い帯の強調' in e and '検査できません' in e for e in result['errors']))

    def test_low_contrast_highlight_blocks_approval_instead_of_only_warning(self):
        result = self.render('<p><mark style="background:#fff;color:#8a8a8a">薄くて読みにくい強調</mark></p>')
        self.assertTrue(any('薄くて読みにくい強調' in e and '読めません' in e for e in result['errors']))

    def test_large_cover_title_with_nearby_blue_is_rejected(self):
        result = self.render('<div class="cover"><h1 style="color:#8da7c5">青い背景に近い青い題名</h1></div>', theme='blue')
        self.assertTrue(any('青い背景に近い青い題名' in e and '4.5以上' in e for e in result['errors']))

    def test_cover_title_and_nested_emphasis_stay_white_in_all_themes(self):
        require_renderer(self)
        import pipeline
        from document_design import style_css
        from presentation_quality import THEMES, theme_css
        css = style_css('editorial') + ''.join(theme_css(t).replace(':root', '.'+t) for t in THEMES)
        html = '<style>'+css+'</style>'+''.join(
            f'<div class="cover {t}"><h1>もやい結び<em><span>下・下・下・上</span></em></h1>'
            '<h2><strong>第2見出し</strong></h2><h3>第3見出し</h3></div>' for t in THEMES)
        script = r'''
const fs=require('fs'), p=require(process.argv[1]);
(async()=>{
  const browser=await p.chromium.launch({headless:true, ...(process.argv[2]?{executablePath:process.argv[2]}:{}),args:['--disable-background-networking']});
  try {
    const page=await browser.newPage({javaScriptEnabled:false});
    await page.setContent(fs.readFileSync(0,'utf8'));
    const result=await page.evaluate(()=>[...document.querySelectorAll('.cover')].map(el=>({
      colours:[...el.querySelectorAll('h1,h2,h3,em,strong,span')].map(x=>getComputedStyle(x).color),
      decoration:getComputedStyle(el.querySelector('em')).textDecorationLine,
      underlineOffset:getComputedStyle(el.querySelector('em')).textUnderlineOffset
    })));
    process.stdout.write(JSON.stringify(result));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
'''
        settings=pipeline.runtime()
        result=subprocess.run([settings.get('node') or 'node','-e',script,settings.get('playwright') or 'playwright',settings.get('browser','')],
                              input=html,text=True,encoding='utf-8',capture_output=True,cwd=ROOT,timeout=30,check=True)
        rows=json.loads(result.stdout)
        self.assertEqual(len(rows),len(THEMES))
        for row in rows:
            self.assertTrue(all(c=='rgb(255, 255, 255)' for c in row['colours']),row)
            self.assertEqual(row['decoration'],'underline')
            self.assertNotEqual(row['underlineOffset'],'auto')


class PromptTagsAllowedTest(unittest.TestCase):
    def test_every_tag_the_editor_prompt_shows_passes_the_html_filter(self):
        # The prompt recommended <mark> while the filter rejected it (found in a full manual run).
        import pipeline
        prompt = (ROOT / 'editor.txt').read_text(encoding='utf-8')
        tags = set(re.findall(r'<([a-z][a-z0-9]*)[\s>]', prompt))
        self.assertTrue(tags)
        self.assertEqual(tags - pipeline.ALLOWED_TAGS, set())

    def test_three_layout_only_fixes_are_allowed(self):
        import pipeline
        self.assertEqual(pipeline.Config().max_layout_retries, 3)


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
