from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import pipeline
import job_progress

CHILD = r'''
import sys, time
print("@@crv-progress fetch", flush=True)
print("@@crv-progress frames 775", flush=True)
print("@@crv-progress bogus", flush=True)
print("@@crv-progress transcribe", flush=True)
if sys.argv[1] == "hang":
    time.sleep(60)
if sys.argv[1] == "fail":
    print("real failure detail", file=sys.stderr, flush=True)
    sys.exit(3)
'''


class PreparationTests(unittest.TestCase):
    def run_child(self, mode, timeout=30):
        messages = []
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / 'child.py'
            script.write_text(CHILD, encoding='utf-8')
            log = Path(temp) / 'extraction.log'
            try:
                pipeline.run_preparation([sys.executable, script, mode], env=None, log=log,
                                         notify=messages.append, timeout=timeout)
                return messages, None, log.read_text(encoding='utf-8')
            except pipeline.PrototypeError as error:
                return messages, error, log.read_text(encoding='utf-8')

    def test_steps_are_shown_in_order_with_duration(self):
        messages, error, log = self.run_child('ok')
        self.assertIsNone(error)
        self.assertEqual(len(messages), 3)
        self.assertTrue(messages[0].startswith('動画の準備 1/4'))
        self.assertIn('動画の長さ 12分55秒', messages[1])
        self.assertTrue(messages[2].startswith('動画の準備 4/4：音声を文字に起こしています'))
        self.assertIn('@@crv-progress bogus', log)  # kept in the private log, not shown

    def test_failure_keeps_previous_error_text(self):
        _, error, _ = self.run_child('fail')
        self.assertIn('real failure detail', str(error))
        self.assertIsNone(getattr(error, 'code', None))

    def test_timeout_names_the_step_and_is_not_an_api_problem(self):
        messages, error, _ = self.run_child('hang', timeout=3)
        self.assertEqual(error.code, 'prepare_timeout')
        self.assertIn('音声を文字に起こしています', str(error))
        self.assertIn('API料金は発生していません', str(error))
        self.assertEqual(job_progress.stop_code(error), 'prepare_timeout')

    def test_old_timeout_text_is_no_longer_reported_as_network(self):
        old = RuntimeError("Command '['/usr/local/bin/python', '[workspace]/crv_worker.py', 'https://x.com/a/status/1/video/1']' timed out after 1800 seconds")
        self.assertEqual(job_progress.stop_code(old), 'prepare_timeout')
        self.assertEqual(job_progress.stop_code(RuntimeError('Request timed out')), 'network')


class WorkerMarkerTests(unittest.TestCase):
    def test_wrapped_crv_steps_print_only_step_names(self):
        import crv_worker
        import claude_real_video.core as core
        printed = []
        with patch.object(core, 'dedup_frames', return_value='kept'), \
                patch('builtins.print', side_effect=lambda *a, **k: printed.append(' '.join(map(str, a)))):
            with crv_worker.announce(core, 'dedup_frames', 'select'):
                self.assertEqual(core.dedup_frames('frames-dir', 8), 'kept')
        self.assertEqual(printed, ['@@crv-progress select'])

    def test_every_step_maps_to_a_screen_message(self):
        import crv_worker
        self.assertTrue({step for _, step in crv_worker.STEPS} <= set(pipeline.PREPARE_STEPS))


if __name__ == '__main__':
    unittest.main()
