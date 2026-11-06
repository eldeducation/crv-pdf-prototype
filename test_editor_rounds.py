import unittest

import pipeline
from openrouter_client import convert_messages


def names(tools):
    return {t['name'] for t in tools}


class EditorRoundReserveTest(unittest.TestCase):
    def test_inspection_closes_while_rounds_remain_to_compose_and_approve(self):
        self.assertIn('inspect_frames', names(pipeline.editor_tools(5, False)))
        self.assertIn('inspect_interval', names(pipeline.editor_tools(4, False)))
        for left in (3, 2, 1):
            tools = names(pipeline.editor_tools(left, False))
            self.assertNotIn('inspect_frames', tools)
            self.assertNotIn('inspect_interval', tools)
            self.assertIn('compose_document', tools)
            self.assertIn('approve_document', tools)

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
