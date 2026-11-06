import unittest

import pipeline
from openrouter_client import convert_messages


def names(tools):
    return {t['name'] for t in tools}


class EditorRoundReserveTest(unittest.TestCase):
    def test_inspection_closes_while_rounds_remain_to_compose_and_approve(self):
        self.assertIn('inspect_frames', names(pipeline.editor_tools(5, False, 0)))
        self.assertIn('inspect_interval', names(pipeline.editor_tools(4, False, 1)))
        for left in (3, 2, 1):
            tools = names(pipeline.editor_tools(left, False, 0))
            self.assertNotIn('inspect_frames', tools)
            self.assertNotIn('inspect_interval', tools)
            self.assertIn('compose_document', tools)
            self.assertIn('approve_document', tools)

    def test_first_draft_is_due_after_two_inspection_rounds_even_with_rounds_to_spare(self):
        self.assertIn('inspect_frames', names(pipeline.editor_tools(7, False, 1)))
        self.assertNotIn('inspect_frames', names(pipeline.editor_tools(5, False, 2)))
        self.assertEqual(pipeline.Config().max_rounds, 7)

    def test_checklist_names_the_exact_images_and_rules_from_the_plan(self):
        plan = {'units': [{'id': 'u01', 'type': 'action'}, {'id': 'c01', 'type': 'claim'}],
                'visual_requirements': [
                    {'role': 'tools', 'status': 'visible', 'evidence_files': ['assets/frame_012.jpg', 'assets/d.jpg']},
                    {'role': 'guides', 'status': 'not_applicable', 'evidence_files': []}]}
        text = pipeline.submission_checklist(plan, 7, True)
        self.assertIn('最大7回', text)
        self.assertIn('assets/frame_012.jpg、assets/d.jpg', text)
        self.assertNotIn('guides', text)
        self.assertIn('action（u01）', text)
        self.assertIn('focus_excerpt', text)
        self.assertNotIn('focus_excerpt', pipeline.submission_checklist(plan, 7, False))

    def test_design_plan_reports_every_page_problem_at_once(self):
        from editorial_quality import validate_design_plan
        pages = [{'html': '<h2>見出しA</h2><p>本文の一文目です</p>', 'source_units': ['c01']},
                 {'html': '<h2>見出しB</h2><p>二ページ目の本文です</p>', 'source_units': ['c01']}]
        record = lambda n, excerpt: {'page': n, 'message': '中心メッセージ', 'layout': '上に見出し', 'focus_excerpt': excerpt,
                                     'rationale': '理由を書く', 'source_units': ['c01']}
        doc = {'pages': pages, 'design_plan': {'reader_goal': '読者の目的', 'visual_direction': '配色の方針',
                                              'pages': [record(1, '言い換えた文'), record(2, '別の要約文')]}}
        with self.assertRaises(ValueError) as caught:
            validate_design_plan(doc, {'units': [{'id': 'c01'}]})
        self.assertIn('1ページ', str(caught.exception))
        self.assertIn('2ページ', str(caught.exception))
        doc['design_plan']['pages'] = [record(1, '見出しA'), record(2, '二ページ目の本文です')]
        validate_design_plan(doc, {'units': [{'id': 'c01'}]})

    def test_a_composed_document_keeps_inspection_one_round_longer(self):
        self.assertIn('inspect_frames', names(pipeline.editor_tools(3, True)))
        self.assertNotIn('inspect_frames', names(pipeline.editor_tools(2, True)))

    def test_openrouter_forwards_notes_sent_with_tool_results(self):
        messages = [
            {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 't1', 'name': 'inspect_frames', 'input': {}}]},
            {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 't1', 'content': 'ok'},
                                         {'type': 'text', 'text': pipeline.INSPECTION_CLOSED}]},
        ]
        converted = convert_messages(messages, 'system')
        self.assertEqual(converted[2], {'role': 'tool', 'tool_call_id': 't1', 'content': 'ok'})
        self.assertEqual(converted[3]['role'], 'user')
        self.assertIn(pipeline.INSPECTION_CLOSED, [b.get('text') for b in converted[3]['content']])

    def test_document_edit_gets_room_for_reasoning_and_an_editorial_document(self):
        import tempfile
        from pathlib import Path
        from usage_guard import GuardedClient

        class Inner:
            calls = []

            def send(self, messages, tools, system):
                self.seen = config.max_tokens
                self.calls.append({'usage': {'cost_usd': 0.0}})
                return []

        config = pipeline.Config()
        config.budget_usd = 100
        with tempfile.TemporaryDirectory() as folder:
            inner = Inner()
            guard = GuardedClient(inner, config, Path(folder))
            guard.rates = (0.0, 0.0)
            guard.send([{'role': 'user', 'content': 'x'}], pipeline.TOOLS, 'system')
        self.assertEqual(inner.seen, 65536)
        self.assertEqual(config.max_tokens, 65536)


if __name__ == '__main__':
    unittest.main()
