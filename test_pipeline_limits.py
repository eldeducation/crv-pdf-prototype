"""Editor prompt location and the document redo budget (no AI calls)."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import pipeline
import share_gateway
from checkpoints import Checkpoint


class EditorPromptPathTests(unittest.TestCase):
    def test_repository_and_docker_layouts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'editor.txt').write_text('top', encoding='utf-8')
            self.assertEqual(pipeline.editor_prompt_path(root), root / 'editor.txt')
            (root / 'prompts').mkdir()
            (root / 'prompts' / 'editor.txt').write_text('placed', encoding='utf-8')
            self.assertEqual(pipeline.editor_prompt_path(root), root / 'prompts' / 'editor.txt')

    def test_this_checkout_has_a_readable_prompt(self):
        self.assertTrue(pipeline.editor_prompt_path().is_file())
        self.assertTrue(pipeline.resume_fingerprint())

    def test_shared_session_gets_prompts_in_both_layouts(self):
        with tempfile.TemporaryDirectory() as temp:
            root, session = Path(temp) / 'repo', Path(temp) / 'session'
            root.mkdir(); session.mkdir()
            (root / 'editor.txt').write_text('top', encoding='utf-8')
            share_gateway.copy_prompts(root, session)
            self.assertEqual((session / 'prompts' / 'editor.txt').read_text(encoding='utf-8'), 'top')
            share_gateway.copy_prompts(root, session, restore=True)
            other = Path(temp) / 'other'; other.mkdir()
            (root / 'prompts').mkdir()
            (root / 'prompts' / 'editor.txt').write_text('placed', encoding='utf-8')
            share_gateway.copy_prompts(root, other)
            self.assertEqual((other / 'prompts' / 'editor.txt').read_text(encoding='utf-8'), 'placed')


class RedoBudgetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.out = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def make(self, **config):
        p = pipeline.Pipeline.__new__(pipeline.Pipeline)
        p.config = pipeline.Config(**config)
        p.revisions, p.layout_failures, p.approved = 0, 0, False
        p.qa = p.document = p.content_qa = None
        p.presentation = {'design': 'standard'}
        p.notify = lambda message: None
        p.evidence = SimpleNamespace(out=self.out, source='https://x.com/a/status/1/video/1')
        p.quality = SimpleNamespace(plan={'units': [], 'visual_requirements': []}, plan_review=None,
                                    research=SimpleNamespace(markdown=lambda *args: ''),
                                    review_document=Mock(return_value={'approved': False, 'unit_checks': []}))
        return p

    def compose_with(self, p, layout_errors):
        with patch.object(pipeline, 'materialize_visuals', side_effect=lambda doc, *a: doc), \
                patch.object(pipeline, 'document_html', return_value='<html></html>'), \
                patch.object(pipeline, 'markdown_references', return_value=''), \
                patch.object(pipeline, 'render', return_value={'errors': layout_errors, 'previews': []}):
            return p.compose({'markdown': '# t', 'pages': []})

    def test_layout_rejection_does_not_use_the_content_redo(self):
        p = self.make()
        self.compose_with(p, ['3ページ: はみ出し'])      # layout only, content not checked
        self.compose_with(p, [])                          # first content check: revise
        self.assertTrue(p.can_compose())                  # the one content redo is still available
        self.compose_with(p, [])                          # the redo
        self.assertEqual((p.revisions, p.layout_failures), (3, 1))
        self.assertEqual(p.quality.review_document.call_count, 2)
        self.assertFalse(p.can_compose())
        with self.assertRaises(pipeline.PrototypeError) as caught:
            self.compose_with(p, [])
        self.assertEqual(caught.exception.code, 'revision_limit')

    def test_layout_fixes_are_capped(self):
        p = self.make(max_layout_retries=2)
        self.compose_with(p, ['overflow'])
        self.compose_with(p, ['overflow'])
        self.assertFalse(p.can_compose())
        with self.assertRaises(pipeline.PrototypeError):
            self.compose_with(p, [])
        p.quality.review_document.assert_not_called()

    def test_finished_document_is_accepted_even_when_budget_is_spent(self):
        p = self.make(max_revisions=1)
        p.quality.review_document.return_value = {'approved': True, 'unit_checks': []}
        self.compose_with(p, [])
        self.assertFalse(p.can_compose())
        self.assertTrue(p.document_ready())

    def resume_with(self, layout_failures):
        p = self.make()
        p.client = SimpleNamespace(calls=[], send=Mock(side_effect=LookupError('stop: would ask the AI')))
        p.initial_content = lambda prompt: [{'type': 'text', 'text': 'x'}]
        p.config.resume = True
        system = pipeline.editor_prompt_path().read_text(encoding='utf-8')
        Checkpoint(self.out, 'editor', {'prompt': 'p', 'plan': p.quality.plan, 'system': system}).save(
            messages=[{'role': 'user', 'content': 'x'}], round=1, pending=None, revisions=2,
            layout_failures=layout_failures, document={'markdown': '# t'}, qa={'errors': []},
            content_qa={'approved': False}, approved=False)
        with patch.object(pipeline, 'select_design', return_value={'design': 'standard'}):
            p.generate('p')
        return p

    def test_resume_restores_layout_counter(self):
        # 2 passes, 1 of them layout-only: one content redo remains, so the
        # editor is asked again instead of stopping at the limit.
        with self.assertRaises(LookupError):
            self.resume_with(layout_failures=1)
        # Without the layout-only pass, both passes were content checks: stop.
        with self.assertRaises(pipeline.PrototypeError) as caught:
            self.resume_with(layout_failures=0)
        self.assertEqual(caught.exception.code, 'revision_limit')


if __name__ == '__main__':
    unittest.main()
