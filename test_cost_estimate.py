"""Automatic cost estimate and ceiling (no AI calls)."""
import base64
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

import cost_estimate
import pipeline
from usage_guard import BudgetStop, GuardedClient

OPUS = (4e-6, 2e-5)  # USD per token measured on 2026-11-06 (input, output)


def estimate(**changes):
    values = dict(analysis_input=60000, editor_input=39000, plan_tokens=20000, plan_ready=True,
                  detail_level='detailed', editorial=True, rates=OPUS)
    values.update(changes)
    return cost_estimate.estimate_run(**values)


class CountTokensTest(unittest.TestCase):
    def test_japanese_counts_about_one_token_per_character_and_ascii_about_a_third(self):
        self.assertEqual(cost_estimate.count_tokens('あ' * 1000), 1100)
        self.assertEqual(cost_estimate.count_tokens('a' * 900), 300)

    def test_images_count_by_pixels_with_a_cap(self):
        buffer = io.BytesIO()
        Image.new('RGB', (1536, 520)).save(buffer, 'JPEG')
        block = {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/jpeg',
                                             'data': base64.b64encode(buffer.getvalue()).decode()}}
        self.assertEqual(cost_estimate.count_tokens([block]), 1065)
        big = io.BytesIO()
        Image.new('RGB', (3000, 3000)).save(big, 'JPEG')
        block['source']['data'] = base64.b64encode(big.getvalue()).decode()
        self.assertEqual(cost_estimate.count_tokens([block]), cost_estimate.IMAGE_TOKEN_CAP)


class EstimateRunTest(unittest.TestCase):
    def test_restyle_estimate_matches_measured_runs(self):
        # Measured (uncached) document-stage spend for this video: about $1.9 (no fix) to $3.5 (one fix).
        result = estimate(cache=False)
        self.assertTrue(1.5 <= result['low_usd'] <= 2.5, result)
        self.assertTrue(2.8 <= result['high_usd'] <= 5.0, result)
        self.assertGreater(result['high_usd'], result['low_usd'])

    def test_prompt_cache_lowers_the_estimate(self):
        cached, plain = estimate(model='anthropic/claude-opus-5.5'), estimate(cache=False)
        self.assertLess(cached['high_usd'], plain['high_usd'])
        self.assertLess(cached['low_usd'], plain['low_usd'])
        self.assertTrue(cached['basis']['prompt_cache'])

    def test_session_cost_writes_the_prefix_once_and_reads_it_back(self):
        rates = (1.0, 0.0)
        self.assertEqual(cost_estimate.session_cost([(100, 0), (150, 0)], rates), 250)
        # 1h, prefix 80: write 80 at 2x + 20 full; then read 80 at 0.05x + 70 full.
        self.assertAlmostEqual(cost_estimate.session_cost([(100, 0), (150, 0)], rates, '1h', 0.05, prefix=80),
                               160 + 20 + 4 + 70)

    def test_full_run_adds_analysis_and_detail_changes_cost(self):
        self.assertGreater(estimate(plan_ready=False)['low_usd'], estimate()['low_usd'])
        self.assertLess(estimate(detail_level='compact')['high_usd'], estimate()['high_usd'])

    def test_ceiling_is_automatic_and_bounded(self):
        result = estimate(spent=1.0)
        self.assertAlmostEqual(result['ceiling_usd'], 1.0 + result['high_usd'] * 1.3, delta=0.02)
        with mock.patch.dict(os.environ, {'VIDEO_PDF_MAX_RUN_USD': '2'}):
            capped = estimate()
        self.assertEqual(capped['ceiling_usd'], 2.0)
        self.assertTrue(capped['exceeds_max'])

    def test_confirmation_only_when_the_estimate_is_high(self):
        self.assertFalse(estimate(detail_level='compact', editorial=False)['needs_confirmation'])
        with mock.patch.dict(os.environ, {'VIDEO_PDF_CONFIRM_USD': '1'}):
            self.assertTrue(estimate()['needs_confirmation'])


class GuardTest(unittest.TestCase):
    def guard(self, folder, budget, expected=None):
        class Inner:
            calls = []

            def send(self, messages, tools, system):
                self.calls.append({'usage': {'cost_usd': 0.1}})
                return []

        config = pipeline.Config()
        config.budget_usd, config.expected_output = budget, expected
        guard = GuardedClient(Inner(), config, Path(folder))
        guard.rates = OPUS
        return guard

    def test_config_defaults_to_an_automatic_limit(self):
        self.assertIsNone(pipeline.Config().budget_usd)
        with self.assertRaises(ValueError):
            pipeline.Config(budget_usd=50)

    def test_reserve_uses_expected_output_not_the_provider_maximum(self):
        messages = [{'role': 'user', 'content': 'x' * 3000}]
        with tempfile.TemporaryDirectory() as folder:
            # 65,536 reserved output tokens alone cost $1.31 at these rates.
            with self.assertRaises(BudgetStop):
                self.guard(folder, 1.2).send(messages, pipeline.TOOLS, 'system')
        with tempfile.TemporaryDirectory() as folder:
            self.guard(folder, 1.2, {'document_edit': 40800}).send(messages, pipeline.TOOLS, 'system')

    def test_estimate_is_published_with_usage(self):
        import json
        with tempfile.TemporaryDirectory() as folder:
            guard = self.guard(folder, 3.0)
            guard.estimate = {'low_usd': 1.0, 'high_usd': 2.0}
            guard.snapshot()
            self.assertEqual(json.loads((Path(folder) / 'usage.json').read_text(encoding='utf-8'))['estimate']['high_usd'], 2.0)


class EncodedImageReuseTest(unittest.TestCase):
    def test_estimate_and_real_requests_share_encoded_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / 'assets').mkdir()
            Image.new('RGB', (64, 48), 'red').save(out / 'assets' / 'a.jpg')
            evidence = pipeline.Evidence.__new__(pipeline.Evidence)
            evidence.out, evidence.assets = out, (out / 'assets').resolve()
            first = evidence.image_block('assets/a.jpg')
            self.assertIs(evidence.image_block('assets/a.jpg'), first)
            records = [{'file': 'assets/a.jpg', 'seconds': 1.0}]
            sheet = evidence.contact_content(records)
            again = evidence.contact_content(records)
            self.assertEqual(sheet, again)
            self.assertIsNot(sheet, again)            # callers may extend the returned list
            self.assertIs(sheet[1], again[1])         # the encoded sheet itself is reused


class ServerBudgetTest(unittest.TestCase):
    def test_blank_budget_means_automatic(self):
        import server
        self.assertIsNone(server.requested_budget(None))
        self.assertIsNone(server.requested_budget(''))
        self.assertEqual(server.requested_budget('4.5'), 4.5)


class ResumeAfterEstimateTest(unittest.TestCase):
    def test_estimate_pause_is_resumable_and_shows_the_estimate(self):
        import json
        from job_progress import describe
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            crv = root / 'work' / 'crv'
            crv.mkdir(parents=True)
            (crv / 'MANIFEST.txt').write_text('x', encoding='utf-8')
            (crv / 'frames.json').write_text(json.dumps({'frames': [1]}), encoding='utf-8')
            (root / 'evidence.json').write_text(json.dumps({'frames': [1]}), encoding='utf-8')
            (root / 'usage.json').write_text(json.dumps({'api_calls': [], 'call_count': 0, 'max_calls': 12,
                                                         'estimate': {'low_usd': 4.1, 'high_usd': 7.2, 'spent_usd': 0}}), encoding='utf-8')
            report = {'quality_pipeline': 'quality-first-v3', 'stop_code': 'estimate_confirm', 'evidence_dir': str(crv)}
            resume = describe(root, {'status': 'failed', 'report': report})['resume']
        self.assertTrue(resume['available'])
        self.assertEqual(resume['reason'], 'estimate_confirm')
        self.assertEqual(resume['estimate']['high_usd'], 7.2)


if __name__ == '__main__':
    unittest.main()
