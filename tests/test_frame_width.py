"""Extraction comparison changes width only; never calls AI or downloads video."""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pipeline
from security import child_environment


class FrameWidthTests(unittest.TestCase):
    def test_existing_positional_arguments_keep_their_meaning(self):
        self.assertEqual(pipeline.Config('model', 'high', 96, 5).max_rounds, 5)

    def test_default_environment_and_explicit_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(pipeline.Config().frame_width, 1280)
        with patch.dict(os.environ, {'VIDEO_PDF_FRAME_WIDTH': '640'}):
            self.assertEqual(pipeline.Config().frame_width, 640)
            self.assertEqual(pipeline.Config(frame_width=1280).frame_width, 1280)
            self.assertEqual(child_environment()['VIDEO_PDF_FRAME_WIDTH'], '640')

    def test_invalid_width_is_rejected(self):
        for width in [0, 320, 1920, True, '640', None]:
            with self.subTest(width=width), self.assertRaises(ValueError):
                pipeline.Config(frame_width=width)

    def test_width_is_the_only_changed_extraction_option(self):
        commands = []
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'video.mp4'
            source.write_bytes(b'fixture')
            with patch.object(pipeline.shutil, 'which', return_value='tool'), patch.object(
                    pipeline, 'run_preparation', side_effect=lambda args, **kw: commands.append(args)):
                for width in [1280, 640]:
                    pipeline.extract(source, Path(temp) / 'out',
                                     pipeline.Config(frame_width=width, no_transcribe=True), notify=lambda _: None)
        index = commands[0].index('--frame-width') + 1
        self.assertEqual(commands[0][index], '1280')
        self.assertEqual(commands[1][index], '640')
        commands[1][index] = '1280'
        self.assertEqual(commands[0], commands[1])
        for flag in ['--grid', '--adaptive', '--no-transcribe']:
            self.assertIn(flag, commands[0])
        self.assertEqual(commands[0][commands[0].index('--max-frames') + 1], '96')
