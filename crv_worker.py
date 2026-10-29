"""CRV adapter: keep evidence extraction, omit the optional full-rate speed scan.

CRV's temporal_hint decodes every full-resolution frame with signalstats. This
prototype does not make playback-speed claims; the optional scan is unrelated
to choosing the scene-aware evidence frames. No installed package is modified.
Set VIDEO_PDF_SPEED_CHECK=1 to restore CRV's original optional speed scan.
"""
import os
import sys
from contextlib import ExitStack
from unittest.mock import patch
from claude_real_video.cli import main

if __name__ == '__main__':
    with ExitStack() as stack:
        if len(sys.argv) > 1 and sys.argv[1].startswith('https://x.com/'):
            # CRV's preliminary caption probe ignores yt-dlp passthrough flags.
            # Avoid that unrestricted duplicate fetch for X. Speech still uses
            # the normal local transcription path after the download.
            stack.enter_context(patch('claude_real_video.core.remote_subtitle_lang', return_value=None))
        if os.getenv('VIDEO_PDF_SPEED_CHECK') != '1':
            print('補助的な再生速度判定は省略。映像・字幕・時刻の抽出は通常どおり実行します。', flush=True)
            stack.enter_context(patch('claude_real_video.temporal_check.temporal_hint', return_value=None))
        main()
