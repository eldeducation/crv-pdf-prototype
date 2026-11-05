"""CRV adapter: keep evidence extraction, omit the optional full-rate speed scan.

CRV's temporal_hint decodes every full-resolution frame with signalstats. This
prototype does not make playback-speed claims; the optional scan is unrelated
to choosing the scene-aware evidence frames. No installed package is modified.
Set VIDEO_PDF_SPEED_CHECK=1 to restore CRV's original optional speed scan.
"""
import functools
import os
import sys
from contextlib import ExitStack
from unittest.mock import patch
from claude_real_video.cli import main
from youtube_support import is_youtube, youtube_context

# One fixed line before each CRV step, so the app can show where preparation
# is (pipeline.PREPARE_STEPS). Only step names and the duration are printed.
PROGRESS = '@@crv-progress '
STEPS = (('fetch_video', 'fetch'), ('extract_frames_adaptive', 'frames'), ('extract_frames', 'frames'),
         ('dedup_frames', 'select'), ('existing_subtitles', 'captions'), ('transcribe', 'transcribe'))


def announce(core, name, step):
    original = getattr(core, name)

    @functools.wraps(original)
    def wrapper(*args, **kwargs):
        detail = ''
        if step == 'frames' and args:
            try:
                detail = ' %d' % round(core._duration(args[0]) or 0)
            except Exception:
                pass
        print(PROGRESS + step + detail, flush=True)
        return original(*args, **kwargs)
    return patch.object(core, name, wrapper)


if __name__ == '__main__':
    import claude_real_video.core as core
    with ExitStack() as stack:
        if len(sys.argv) > 1 and is_youtube(sys.argv[1]):
            stack.enter_context(youtube_context())
        # After youtube_context, so the YouTube importer is the wrapped fetch.
        for name, step in STEPS:
            if hasattr(core, name):
                stack.enter_context(announce(core, name, step))
        if len(sys.argv) > 1 and sys.argv[1].startswith('https://x.com/'):
            # CRV's preliminary caption probe ignores yt-dlp passthrough flags.
            # Avoid that unrestricted duplicate fetch for X. Speech still uses
            # the normal local transcription path after the download.
            stack.enter_context(patch('claude_real_video.core.remote_subtitle_lang', return_value=None))
        if os.getenv('VIDEO_PDF_SPEED_CHECK') != '1':
            print('補助的な再生速度判定は省略。映像・字幕・時刻の抽出は通常どおり実行します。', flush=True)
            stack.enter_context(patch('claude_real_video.temporal_check.temporal_hint', return_value=None))
        main()
