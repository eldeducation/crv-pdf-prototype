import unittest

import pipeline
from openrouter_client import convert_messages


def names(tools):
    return {t['name'] for t in tools}


class EditorRoundReserveTest(unittest.TestCase):
    def test_inspection_closes_while_rounds_remain_to_compose_and_approve(self):
        self.assertTrue(pipeline.inspection_open(5, False, 0))
        self.assertTrue(pipeline.inspection_open(4, False, 1))
        for left in (3, 2, 1):
            self.assertFalse(pipeline.inspection_open(left, False, 0))

    def test_first_draft_is_due_after_two_inspection_rounds_even_with_rounds_to_spare(self):
        self.assertTrue(pipeline.inspection_open(7, False, 1))
        self.assertFalse(pipeline.inspection_open(5, False, 2))
        self.assertEqual(pipeline.Config().max_rounds, 7)

    def test_feedback_points_fixes_to_revise_pages(self):
        self.assertIn('revise_pages', pipeline.FIX_GUIDANCE)
        self.assertIn('revise_pages', pipeline.INSPECTION_CLOSED_AFTER_DRAFT)
        self.assertNotIn('compose_document', pipeline.INSPECTION_CLOSED_AFTER_DRAFT)

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
        self.assertTrue(pipeline.inspection_open(3, True))
        self.assertFalse(pipeline.inspection_open(2, True))

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

    def test_exhausted_balance_stops_the_run_instead_of_another_turn(self):
        import tempfile
        from pathlib import Path
        from usage_guard import BudgetStop, GuardedClient

        class Inner:
            calls = []

            def send(self, messages, tools, system):
                self.calls.append({'usage': {'cost_usd': 0.0}, 'http_status': 402})
                raise pipeline.PrototypeError('OpenRouter HTTP 402: 残高またはキーの利用上限が不足しています。')

        config = pipeline.Config()
        config.budget_usd = 100
        with tempfile.TemporaryDirectory() as folder:
            guard = GuardedClient(Inner(), config, Path(folder))
            guard.rates = (0.0, 0.0)
            with self.assertRaises(BudgetStop) as caught:
                guard.send([{'role': 'user', 'content': 'x'}], pipeline.TOOLS, 'system')
            self.assertEqual(caught.exception.code, 'credit')
            self.assertIn('402', str(caught.exception))
            self.assertIn('最大約$', str(caught.exception))     # says what one request needs
            self.assertIsNone(guard.pending)

    def test_402_is_retried_once_with_the_expected_output_cap(self):
        import tempfile
        from pathlib import Path
        from usage_guard import GuardedClient
        seen = []

        class Inner:
            calls = []

            def send(self, messages, tools, system):
                seen.append(config.max_tokens)
                if len(seen) == 1:
                    self.calls.append({'usage': {'cost_usd': 0.0}, 'http_status': 402})
                    raise pipeline.PrototypeError('OpenRouter HTTP 402: 残高またはキーの利用上限が不足しています。')
                self.calls.append({'usage': {'cost_usd': 0.5}, 'stop_reason': 'tool_calls'})
                return []

        config = pipeline.Config()
        config.budget_usd, config.expected_output = 100, {'document_edit': 40800}
        with tempfile.TemporaryDirectory() as folder:
            guard = GuardedClient(Inner(), config, Path(folder))
            guard.rates = (4e-6, 2e-5)
            guard.send([{'role': 'user', 'content': 'x'}], pipeline.TOOLS, 'system')
        self.assertEqual(seen, [65536, 40800])
        self.assertEqual(guard.calls[-1]['max_output_tokens'], 40800)
        self.assertEqual(config.max_tokens, 65536)                  # restored after the request

    def test_token_limit_counts_cached_prompt_tokens(self):
        import tempfile
        from pathlib import Path
        from usage_guard import BudgetStop, GuardedClient

        class Inner:
            calls = [{'usage': {'input_tokens': 1000, 'output_tokens': 100, 'cache_read_input_tokens': 50000, 'cost_usd': 0.1}}]

            def send(self, messages, tools, system):
                raise AssertionError('must stop before sending')

        config = pipeline.Config()
        config.budget_usd, config.max_total_tokens = 100, 60000
        with tempfile.TemporaryDirectory() as folder:
            guard = GuardedClient(Inner(), config, Path(folder))
            guard.rates = (0.0, 0.0)
            with self.assertRaises(BudgetStop) as caught:
                guard.send([{'role': 'user', 'content': 'x'}], pipeline.TOOLS, 'system')
        self.assertEqual(caught.exception.code, 'token_limit')

    def test_json_repair_request_is_not_cached(self):
        import tempfile
        from pathlib import Path
        from usage_guard import GuardedClient
        seen = []

        class Inner:
            calls = []

            def send(self, messages, tools, system):
                seen.append(config.cache_ttl)
                if len(seen) == 1:
                    self.calls.append({'usage': {'cost_usd': 0.1}, 'stop_reason': 'tool_calls'})
                    error = pipeline.PrototypeError('broken JSON')
                    error.tool_output = {'name': 'compose_document', 'arguments': '{"title": "t"'}
                    raise error
                self.calls.append({'usage': {'cost_usd': 0.01}, 'stop_reason': 'tool_calls'})
                return []

        config = pipeline.Config()
        config.budget_usd = 100
        with tempfile.TemporaryDirectory() as folder:
            guard = GuardedClient(Inner(), config, Path(folder))
            guard.rates = (0.0, 0.0)
            guard.send([{'role': 'user', 'content': 'x'}], pipeline.TOOLS, 'system')
        self.assertEqual(seen, ['1h', None])


if __name__ == '__main__':
    unittest.main()
