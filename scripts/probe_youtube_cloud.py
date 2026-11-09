"""One bounded, anonymous import test; no AI SDKs, keys, cookies or proxies.

Only safe result metadata survives. Media and subtitles are removed at exit.
This is a manual network integration test, not a production download service.
"""
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

SOURCE = 'https://www.youtube.com/watch?v=Q2w4-mluYo0'
MAX_BYTES = 200 * 1024 * 1024


def error_code(error):
    message = str(error).lower()
    if any(word in message for word in ('not a bot', 'confirm your identity', 'login_required')):
        return 'youtube_verification'
    if any(word in message for word in ('private video', 'members-only', 'age-restricted', 'not available in your country')):
        return 'access_restricted'
    if any(word in message for word in ('403', 'no video formats', 'signature', 'challenge solving failed')):
        return 'youtube_client'
    if 'size_limit' in message:
        return 'size_limit'
    if 'timed out' in message or isinstance(error, subprocess.TimeoutExpired):
        return 'timeout'
    return 'download_failed'


class QuietLogger:
    def debug(self, message):
        pass
    warning = error = info = debug


def bounded_progress(data):
    if data.get('downloaded_bytes', 0) > MAX_BYTES:
        raise RuntimeError('size_limit')


def probe():
    import yt_dlp
    from yt_dlp.version import __version__
    report = {'source': SOURCE, 'yt_dlp': __version__, 'ai_calls': 0,
              'success': False, 'stage': 'setup', 'verdict': 'not_started',
              'subtitles': 'not_attempted'}
    started = time.monotonic()
    try:
        if not shutil.which('ffprobe') or not shutil.which('ffmpeg') or not shutil.which('node'):
            raise RuntimeError('missing_runtime')
        with tempfile.TemporaryDirectory(prefix='youtube-cloud-probe-') as temporary:
            folder = Path(temporary)
            # Match the app's pinned downloader and 1080p ceiling, with retries
            # disabled so an authentication refusal ends this experiment.
            options = yt_dlp.parse_options([
                '--ignore-config', '--no-plugin-dirs', '--no-playlist',
                '--use-extractors', '^youtube$', '--js-runtimes', 'node:' + shutil.which('node'),
                '--socket-timeout', '20', '--retries', '0', '--extractor-retries', '0',
                '--fragment-retries', '0', '--match-filter', 'duration <= 1800 & !is_live',
                '--max-filesize', str(MAX_BYTES), '-S', 'res:1080',
                '--merge-output-format', 'mp4', '-o', str(folder / 'source.%(ext)s')
            ]).ydl_opts
            options.update(logger=QuietLogger(), quiet=True, noprogress=True,
                           ignoreerrors=False, progress_hooks=[bounded_progress])
            report['stage'] = 'video_download'
            with yt_dlp.YoutubeDL(options) as downloader:
                info = downloader.extract_info(SOURCE, download=True)
            videos = [p for p in folder.iterdir() if p.suffix in ('.mp4', '.mkv', '.webm')]
            if len(videos) != 1:
                raise RuntimeError('missing_video')
            video = videos[0]
            report['stage'] = 'media_check'
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                'stream=codec_type,height:format=duration', '-of', 'json', str(video)],
                capture_output=True, text=True, timeout=30, check=True)
            data = json.loads(result.stdout)
            streams = data.get('streams', [])
            heights = [int(s['height']) for s in streams if s.get('codec_type') == 'video' and s.get('height')]
            if not heights:
                raise RuntimeError('missing_video_stream')
            report.update(success=True, verdict='downloaded', bytes=video.stat().st_size,
                          duration_seconds=round(float(data['format']['duration']), 1),
                          height=max(heights), audio=any(s.get('codec_type') == 'audio' for s in streams))
            report['stage'] = 'subtitles'
            try:
                subtitle_options = {**options, 'skip_download': True, 'writesubtitles': True,
                                    'writeautomaticsub': True, 'subtitleslangs': ['ja', 'en'],
                                    'subtitlesformat': 'vtt'}
                with yt_dlp.YoutubeDL(subtitle_options) as downloader:
                    downloader.process_ie_result(copy.deepcopy(info), download=True)
                report['subtitle_files'] = len(list(folder.glob('source.*.vtt')))
                report['subtitles'] = 'downloaded' if report['subtitle_files'] else 'not_available'
            except Exception as error:
                report['subtitles'] = error_code(error)
            report['stage'] = 'complete'
    except Exception as error:
        report['verdict'] = 'missing_runtime' if str(error) == 'missing_runtime' else error_code(error)
    finally:
        report['seconds'] = round(time.monotonic() - started, 1)
    return report


if __name__ == '__main__':
    report = probe()
    # Log no raw provider response, media URLs, cookies, tokens or IP addresses.
    print(json.dumps(report, sort_keys=True))
    if os.getenv('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a', encoding='utf-8') as stream:
            stream.write('## Anonymous YouTube import test\n\n```json\n' + json.dumps(report, indent=2) + '\n```\n')
            stream.write('\nNo AI calls or repository secrets. Media and subtitles deleted after checking.\n')
    if os.getenv('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a', encoding='utf-8') as stream:
            for key in ('verdict', 'bytes', 'duration_seconds', 'height', 'audio', 'subtitles', 'seconds', 'stage'):
                stream.write(key + '=' + str(report.get(key, 'n/a')) + '\n')
