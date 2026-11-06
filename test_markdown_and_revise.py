"""Generated Markdown and page-level revisions (no AI calls)."""
import unittest

import pipeline
from markdown_export import document_markdown, page_markdown


class MarkdownExportTest(unittest.TestCase):
    def test_structure_images_tables_and_lists(self):
        text = page_markdown(
            '<div class="chapter"><p class="no">02</p><div><p class="meta">02:00 – 08:35</p><h2>見出し</h2></div></div>'
            '<p>本文<strong>強調</strong>です。<span data-source-unit="c01"></span></p>'
            '<figure class="shot"><img src="assets/a.jpg" alt="説明"><figcaption><strong>07:06</strong>　画面</figcaption></figure>'
            '<table><tr><th>版</th><th>結果</th></tr><tr><td>v1</td><td>誤解 | 注意</td></tr></table>'
            '<div class="tiles"><div><b>17</b>チェック欄</div><div><b>2</b>印のある欄</div><div><b>0</b>temperature</div></div>'
            '<ol><li>一つ目</li><li>二つ目</li></ol>')
        self.assertIn('## 02 見出し（02:00 – 08:35）', text)
        self.assertIn('本文**強調**です。', text)
        self.assertNotIn('data-source-unit', text)
        self.assertIn('![説明](assets/a.jpg)', text)
        self.assertIn('*07:06', text)
        self.assertIn('| 版 | 結果 |', text)
        self.assertIn('| v1 | 誤解 \\| 注意 |', text)
        self.assertIn('- **17** チェック欄', text)
        self.assertIn('1. 一つ目\n2. 二つ目', text)

    def test_document_has_title_page_breaks_and_every_image(self):
        doc = {'title': '題名', 'pages': [{'html': '<p>一</p><img src="assets/1.jpg">'}, {'html': '<p>二</p><img src="assets/2.jpg">'}]}
        text = document_markdown(doc)
        self.assertTrue(text.startswith('# 題名'))
        self.assertIn('\n---\n', text)
        self.assertIn('](assets/1.jpg)', text)
        self.assertIn('](assets/2.jpg)', text)

    def test_captions_and_sentences_stay_out_of_lists(self):
        # Found in a full run: a caption, a label and a summary sentence were merged into one list.
        text = page_markdown(
            '<figure><img src="assets/a.jpg"><figcaption><strong>00:11</strong>　登壇者</figcaption></figure>'
            '<div class="tldr"><p class="label">ひとことで言うと</p><p class="line">短い指示では状況を取り違える。</p></div>'
            '<div class="chevrons"><div>v1<small>誤解</small></div><div>v2<small>認識</small></div>'
            '<div class="on">最終版<small>タグで判定</small></div></div>')
        self.assertIn('*00:11　登壇者*', text)
        self.assertNotIn('- *00:11', text)
        self.assertNotIn('- 短い指示', text)
        self.assertIn('- v1 誤解\n- v2 認識\n- 最終版 タグで判定', text)

    def test_svg_content_is_skipped(self):
        self.assertNotIn('path', page_markdown('<p>図</p><svg><text>path</text></svg>'))


class ReviseDraftTest(unittest.TestCase):
    def draft(self):
        return {'title': 't', 'summary': 's', 'css': '.a{}', 'pages': [
            {'html': '<p>1</p>', 'source_units': ['c1'], 'visual_roles': ['tools']},
            {'html': '<p>2</p>', 'source_units': ['c2']}],
            'design_plan': {'reader_goal': 'g', 'visual_direction': 'v', 'pages': [{'page': 1, 'message': 'm1'}, {'page': 2, 'message': 'm2'}]}}

    def test_only_named_pages_change_and_unsent_fields_are_kept(self):
        draft = self.draft()
        doc = pipeline.revised_draft(draft, {'pages': [{'page': 1, 'html': '<p>新</p>'}],
                                             'design_plan_pages': [{'page': 1, 'message': '新しい'}], 'css': '.b{}'})
        self.assertEqual(doc['pages'][0], {'html': '<p>新</p>', 'source_units': ['c1'], 'visual_roles': ['tools']})
        self.assertEqual(doc['pages'][1], draft['pages'][1])
        self.assertEqual(doc['design_plan']['pages'][0]['message'], '新しい')
        self.assertEqual(doc['design_plan']['pages'][1]['message'], 'm2')
        self.assertEqual(doc['css'], '.b{}')
        self.assertEqual(draft['pages'][0]['html'], '<p>1</p>')   # the saved draft is not modified

    def test_page_numbers_must_exist_and_a_draft_is_required(self):
        with self.assertRaises(pipeline.PrototypeError):
            pipeline.revised_draft(self.draft(), {'pages': [{'page': 3, 'html': 'x'}]})
        with self.assertRaises(pipeline.PrototypeError):
            pipeline.revised_draft(self.draft(), {'pages': [{'page': 1, 'html': 'x'}, {'page': 1, 'html': 'y'}]})
        with self.assertRaises(pipeline.PrototypeError):
            pipeline.revised_draft(None, {'pages': [{'page': 1, 'html': 'x'}]})

    def test_editor_no_longer_writes_markdown(self):
        compose = next(t for t in pipeline.TOOLS if t['name'] == 'compose_document')['input_schema']
        self.assertNotIn('markdown', compose['required'])
        self.assertNotIn('markdown', compose['properties'])
        self.assertIn('revise_pages', {t['name'] for t in pipeline.TOOLS})
        self.assertIn('revise_pages', {t['name'] for t in pipeline.editor_tools(1, True, 6)})


class SharedCopyTest(unittest.TestCase):
    def test_every_local_module_imported_by_the_app_is_copied(self):
        import ast
        from pathlib import Path
        import share_gateway
        root = Path(__file__).resolve().parent
        copied = {n[:-3] for n in share_gateway.COPY_FILES if n.endswith('.py')}
        local = {p.stem for p in root.glob('*.py')}
        missing = set()
        for name in copied:
            for node in ast.walk(ast.parse((root / (name + '.py')).read_text(encoding='utf-8'))):
                if isinstance(node, ast.Import):
                    modules = [a.name.split('.')[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modules = [node.module.split('.')[0]]
                else:
                    continue
                missing.update(m for m in modules if m in local and m not in copied)
        self.assertEqual(missing, set())


if __name__ == '__main__':
    unittest.main()
