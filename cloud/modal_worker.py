"""CRV worker with the tested extraction settings; no AI provider credentials."""
import functools
import json
import os
from pathlib import Path
import runpy
import sys
from contextlib import ExitStack
from unittest.mock import patch

from balanced_select import balance_command


def main():
    import claude_real_video.core as core
    from claude_real_video.cli import main as cli
    original_run = core._run
    with ExitStack() as stack:
        stack.enter_context(patch.object(core, '_run', lambda command: original_run(balance_command(command))))
        stack.enter_context(patch('claude_real_video.temporal_check.temporal_hint', return_value=None))
        for name, phase in (('fetch_video', 'fetch'), ('extract_frames_adaptive', 'frames'),
                            ('extract_frames', 'frames'), ('dedup_frames', 'select'),
                            ('existing_subtitles', 'captions'), ('transcribe', 'transcribe')):
            if not hasattr(core, name):
                continue
            original = getattr(core, name)
            def wrap(*args, _original=original, _phase=phase, **kwargs):
                print('@@crv-progress ' + _phase, flush=True)
                return _original(*args, **kwargs)
            stack.enter_context(patch.object(core, name, wrap))
        provided = os.environ.pop('CRV_PROVIDED_TRANSCRIPT', '')
        if provided:
            data = json.loads(Path(provided).read_text(encoding='utf-8'))
            def transcript(video, out_dir, *args, **kwargs):
                for name in ('transcript.json', 'transcript.txt', 'cloud-transcribe.json'):
                    if name in data:
                        (Path(out_dir) / name).write_text(data[name], encoding='utf-8')
                target = Path(out_dir) / 'transcript.txt'
                return str(target) if target.is_file() else None
            stack.enter_context(patch.object(core, '_whisper_available', lambda: True))
            stack.enter_context(patch.object(core, '_transcribe_impl', transcript))
            if data.get('source_subtitles'):
                stack.enter_context(patch.object(core, 'existing_subtitles', transcript))
        cli()


if __name__ == '__main__':
    main()
