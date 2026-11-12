"""Prompt caching markers, TTL per stage and cost accounting (no AI calls)."""
import json
import tempfile
import unittest
from pathlib import Path

import pipeline
import prompt_cache
from openrouter_client import convert_messages
from usage_guard import GuardedClient


def markers(value):
    return json.dumps(value, ensure_ascii=False).count('"cache_control"')


CONVERSATION = [
    {'role': 'user', 'content': [{'type': 'text', 'text': 'plan'},
                                 {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': 'eA=='}}]},
    {'role': 'assistant', 'content': [{'type': 'tool_use', 'id': 't1', 'name': 'inspect_frames', 'input': {}}]},
    {'role': 'user', 'content': [{'type': 'tool_result', 'tool_use_id': 't1', 'content': [
        {'type': 'text', 'text': 'frame'}, {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg', 'data': 'eA=='}}]}]},
]


class MarkerTest(unittest.TestCase):
    def test_anthropic_markers_only_on_the_stable_prefix(self):
        payload = prompt_cache.anthropic_request({'system': 'rules', 'messages': CONVERSATION}, '1h')
        self.assertEqual(payload['system'][0]['cache_control'], {'type': 'ephemeral', 'ttl': '1h'})
        self.assertIn('cache_control', payload['messages'][0]['content'][-1])
        self.assertNotIn('cache_control', json.dumps(payload['messages'][1:]))   # the growing tail is not cached
        self.assertEqual(markers(payload), 2)
        self.assertEqual(markers(CONVERSATION), 0)          # the stored conversation is not modified
        self.assertNotIn('cache_control', {k for k in payload if k != 'system' and k != 'messages'})

    def test_openrouter_markers_are_content_parts_only(self):
        converted = {'messages': convert_messages(CONVERSATION, 'rules')}
        payload = prompt_cache.openrouter_request(converted, '5m')
        self.assertEqual(payload['messages'][0]['content'][0]['cache_control'], {'type': 'ephemeral'})
        users = [m for m in payload['messages'] if m['role'] == 'user']
        self.assertIn('cache_control', users[0]['content'][0])   # last text part of the first message
        self.assertNotIn('cache_control', json.dumps(users[1:]))
        self.assertNotIn('cache_control', payload)                 # no top-level request parameter
        self.assertEqual(markers(payload), 2)

    def test_no_caching_without_ttl(self):
        payload = {'system': 'rules', 'messages': CONVERSATION}
        self.assertIs(prompt_cache.anthropic_request(payload, None), payload)

    def test_ttl_by_stage(self):
        self.assertEqual(prompt_cache.TTL_BY_PHASE['document_edit'], '1h')   # page writing runs past 5 minutes
        self.assertEqual(prompt_cache.TTL_BY_PHASE['content_plan'], '5m')
        # Every measured check was two calls about a minute apart (frames, then review).
        self.assertEqual(prompt_cache.TTL_BY_PHASE['content_review'], '5m')


class StablePrefixTest(unittest.TestCase):
    def test_editor_sends_the_same_tool_list_every_turn(self):
        # Tools come first in the cached prefix; dropping inspection tools mid-run would
        # invalidate the cache, so closure is enforced on the call instead.
        import inspect
        source = inspect.getsource(pipeline.Pipeline.generate)
        self.assertIn('self.client.send(messages, TOOLS, system)', source)
        self.assertIn('raise PrototypeError(note)', source)


class AnalysisStagePrefixTest(unittest.TestCase):
    def test_analysis_rounds_keep_the_same_tool_list(self):
        # The final (largest) analysis round used to drop to the submit tool only,
        # which invalidated the cached prefix and resent every evidence image.
        import inspect
        from content_quality import ContentQuality
        source = inspect.getsource(ContentQuality.session)
        self.assertIn('current_tools = available', source)
        self.assertNotIn('[submit_tool] if finalizing', source)
        self.assertIn('if finalizing:', source)       # closed inspection is still enforced per call


class CostTest(unittest.TestCase):
    def test_call_cost_prices_reads_and_writes(self):
        usage = {'input_tokens': 100, 'output_tokens': 10, 'cache_read_input_tokens': 1000,
                 'cache_creation_input_tokens': 300, 'cache_creation': {'ephemeral_1h_input_tokens': 200, 'ephemeral_5m_input_tokens': 100}}
        cost = prompt_cache.call_cost(usage, (1.0, 10.0), 'claude-opus-5-5')
        self.assertAlmostEqual(cost, 100 + 100 * 1.25 + 200 * 2 + 1000 * 0.05 + 100)
        self.assertEqual(prompt_cache.read_multiplier('anthropic/claude-opus-5.5'), 0.05)
        self.assertEqual(prompt_cache.read_multiplier('anthropic/claude-sonnet-5.5'), 0.1)

    def test_guard_sets_ttl_per_phase_and_prices_direct_anthropic_calls(self):
        seen = []

        class Inner:
            calls = []

            def send(self, messages, tools, system):
                seen.append(config.cache_ttl)
                self.calls.append({'usage': {'input_tokens': 1000, 'output_tokens': 100}, 'stop_reason': 'tool_use'})
                return []

        config = pipeline.Config()
        config.budget_usd = 10
        with tempfile.TemporaryDirectory() as folder:
            guard = GuardedClient(Inner(), config, Path(folder))
            guard.rates = (4e-6, 2e-5)
            guard.send([{'role': 'user', 'content': 'x'}], pipeline.TOOLS, 'system')
            guard.send([{'role': 'user', 'content': 'x'}], pipeline.TOOLS, 'system')   # not blocked as "cost unconfirmed"
        self.assertEqual(seen, ['1h', '1h'])
        self.assertIsNone(config.cache_ttl)
        self.assertAlmostEqual(guard.calls[0]['usage']['cost_usd'], 1000 * 4e-6 + 100 * 2e-5)
        self.assertEqual(guard.calls[0]['cache_ttl'], '1h')


if __name__ == '__main__':
    unittest.main()
