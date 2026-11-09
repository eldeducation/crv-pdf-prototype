"""Explicit anonymous YouTube configuration for CRV and deployment checks.

No personal cookies, proxies, third-party download services or AI APIs.
"""
from contextlib import contextmanager, ExitStack
from pathlib import Path
from unittest.mock import patch
import functools
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from security import normalized_video_url, child_environment
import home_fetch


def is_youtube(source):
    try:
        return normalized_video_url(source).startswith('https://www.youtube.com/watch?')
    except ValueError:
        return False


POT_HOME = Path('/opt/bgutil/server')
POT_PLUGINS = Path('/opt/youtube-plugins')


def pot_available():
    return (POT_HOME/'build/generate_once.js').is_file() and (POT_PLUGINS/'bgutil/yt_dlp_plugins').is_dir()


def youtube_args(client=None):
    node = shutil.which('node')
    args = ['--ignore-config', '--no-plugin-dirs', '--no-playlist', '--use-extractors', '^youtube$',
            '--socket-timeout', '20', '--retries', '1', '--extractor-retries', '1',
            '--match-filter', 'duration <= 1800 & !is_live']
    if node:
        args += ['--js-runtimes', 'node:' + node]
    if pot_available():
        # Only the pinned build-time plugin; ignore user/global plugin folders.
        args += ['--plugin-dirs', str(POT_PLUGINS), '--extractor-args',
                 'youtubepot-bgutilscript:server_home=' + str(POT_HOME)]
        client = client or 'mweb,tv,web_safari'
    if client:
        args += ['--extractor-args', 'youtube:player_client=' + client]
    return args


def error_code(error):
    message = str(error).lower()
    if "not a bot" in message or 'confirm your identity' in message or 'youtube_verification' in message:
        return 'youtube_verification'
    if 'private video' in message or 'members-only' in message or 'age-restricted' in message or 'not available in your country' in message:
        return 'access_restricted'
    if '403' in message or 'no video formats' in message or 'nsig' in message or 'signature' in message or 'youtube_client' in message:
        return 'youtube_client'
    return 'download_failed'


@contextmanager
def youtube_context():
    import claude_real_video.core as core
    original_fetch = core.fetch_video
    original_subtitle_lang = core.remote_subtitle_lang
    # Set only on the cloud host when the home-PC fetcher is configured.
    queue = home_fetch.queue_dir()

    def subtitle_lang(source, lang=None):
        # The PC applies CRV's own caption-track choice on its connection.
        if queue and is_youtube(source):
            return 'agent:' + (lang if lang and lang != 'auto' and home_fetch.SUB_REQUEST.fullmatch('agent:' + lang) else 'auto')
        return original_subtitle_lang(source, lang)

    @functools.lru_cache(maxsize=2)
    def remote_info(source):
        if not is_youtube(source):
            return None
        try:
            import yt_dlp
            args = youtube_args() + ['--skip-download', '--quiet', '--no-warnings']
            opts = yt_dlp.parse_options(args).ydl_opts
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(source, download=False)
        except Exception:
            return None

    def fetch(source, out_dir, cookies=None, cookies_from_browser=None, ytdlp_args=None, sub_lang=None):
        if not is_youtube(source):
            return original_fetch(source, out_dir, cookies, cookies_from_browser, ytdlp_args, sub_lang)
        if cookies or cookies_from_browser:
            raise ValueError('Personal YouTube cookies are not accepted by the shared importer.')
        if queue:
            return home_fetch.request_download(queue, normalized_video_url(source), out_dir, sub_lang)
        last_error = None
        for client in (None, 'android_vr', 'web_embedded'):
            try:
                return original_fetch(source, out_dir, None, None,
                                      list(ytdlp_args or []) + youtube_args(client), sub_lang)
            except RuntimeError as error:
                last_error = error
                # Public, anonymous clients only. Never retry access-restricted
                # content or unrelated ffmpeg/filesystem failures.
                if error_code(error) not in ('youtube_verification', 'youtube_client'):
                    raise
        raise RuntimeError('YouTube URL取り込みを確認できませんでした。公開サーバーからのアクセス確認が要求されています。'
                           '（' + error_code(last_error) + '）') from last_error

    with ExitStack() as stack:
        stack.enter_context(patch.object(core, 'fetch_video', fetch))
        stack.enter_context(patch.object(core, '_remote_info', remote_info))
        stack.enter_context(patch.object(core, 'remote_subtitle_lang', subtitle_lang))
        yield


def deployment_probe(source, work):
    """Opt-in, one-shot anonymous download in the running cloud container."""
    report = {'event': 'youtube_import_probe', 'success': False, 'ai_calls': 0}
    start = time.monotonic()
    try:
        source = normalized_video_url(source)
        if not is_youtube(source):
            raise ValueError('Only a YouTube URL can be checked.')
        work = Path(work);work.mkdir(parents=True, exist_ok=True)
        queue = home_fetch.queue_dir()
        if queue:
            # A fresh instance may boot before the PC's next poll reaches it.
            deadline = time.monotonic() + 180
            while not home_fetch.agent_online(queue) and time.monotonic() < deadline:
                time.sleep(5)
        with tempfile.TemporaryDirectory(prefix='youtube-check-', dir=work) as folder:
            command = [sys.executable, str(Path(__file__).resolve()), '--download-check', source, folder]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, encoding='utf-8', env=child_environment(),
                                       start_new_session=os.name != 'nt')
            try:
                # The home-PC route includes the PC's download and upload time.
                limit = home_fetch.RESULT_SECONDS + 120 if home_fetch.queue_dir() else 300
                stdout, stderr = process.communicate(timeout=limit)
            except subprocess.TimeoutExpired:
                if os.name != 'nt':
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                process.communicate(timeout=10)
                raise
            # Child emits only its controlled final summary to stdout.
            if process.returncode:
                report['error_code'] = error_code(stderr)
                if stdout.strip():
                    diagnostic = json.loads(stdout.strip().splitlines()[-1])
                    for key in ('provider_loaded', 'token_generated', 'login_required'):
                        report[key] = bool(diagnostic.get(key, False))
            else:
                report.update(json.loads(stdout.strip().splitlines()[-1]))
    except subprocess.TimeoutExpired:
        report['error_code'] = 'timeout'
    except Exception:
        report['error_code'] = 'probe_failed'
    report['seconds'] = round(time.monotonic() - start, 1)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return report


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 4 or sys.argv[1] != '--download-check' or not is_youtube(sys.argv[2]):
        raise SystemExit(2)
    safe_environment = child_environment()
    os.environ.clear()
    os.environ.update(safe_environment)
    diagnostics = {'provider_loaded': False, 'token_generated': False, 'login_required': False}
    try:
        import claude_real_video.core as core
        original_run = core._run
        def observed_run(command, *args, **kwargs):
            result = original_run(command, *args, **kwargs)
            if command and Path(str(command[0])).stem == 'yt-dlp':
                detail = (result.stderr or '') + (result.stdout or '')
                diagnostics['provider_loaded'] |= 'bgutil:script-node-2.0.2 (external)' in detail
                diagnostics['token_generated'] |= 'via bgutil script' in detail and 'Generating a' in detail
                diagnostics['login_required'] |= 'LOGIN_REQUIRED' in detail or 'not a bot' in detail
            return result
        with youtube_context(), patch.object(core, '_run', observed_run):
            # Same order as CRV: choose the caption track, then download.
            sub_lang = core.remote_subtitle_lang(sys.argv[2])
            video = core.fetch_video(sys.argv[2], sys.argv[3], ytdlp_args=['-S', 'res:1080', '--verbose'], sub_lang=sub_lang)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type:format=duration', '-of', 'json', video],
                               capture_output=True, text=True, timeout=30, check=True, env=child_environment())
        data = json.loads(probe.stdout)
        if not any(s.get('codec_type') == 'video' for s in data.get('streams', [])):
            raise RuntimeError('Downloaded file has no video stream.')
        print(json.dumps({'success': True, 'bytes': Path(video).stat().st_size,
                          'duration_seconds': float(data['format']['duration']),
                          'audio': any(s.get('codec_type') == 'audio' for s in data['streams']),
                          'via_home_pc': bool(home_fetch.queue_dir()),
                          'subtitles': any(home_fetch.SUBTITLE_NAME.fullmatch(p.name) for p in Path(video).parent.iterdir())}),
              flush=True)
    except Exception as error:
        print(json.dumps(diagnostics), flush=True)
        print(error_code(error), file=sys.stderr, flush=True)
        raise SystemExit(1)


def ensure_ffmpeg(environ=None, which=None):
    """yt-dlp needs ffmpeg to merge video and audio. winget installs it in a
    per-user folder that a shell started earlier may not have on PATH."""
    import os
    import shutil
    environ = os.environ if environ is None else environ
    which = which or shutil.which
    if which('ffmpeg') and which('ffprobe'):
        return True
    base = Path(environ.get('LOCALAPPDATA', '')) / 'Microsoft' / 'WinGet'
    candidates = [base / 'Links'] + sorted((base / 'Packages').glob('*FFmpeg*/*/bin'), reverse=True)
    for folder in candidates:
        if (folder / 'ffmpeg.exe').is_file() and (folder / 'ffprobe.exe').is_file():
            environ['PATH'] = str(folder) + os.pathsep + environ.get('PATH', '')
            return True
    return False
