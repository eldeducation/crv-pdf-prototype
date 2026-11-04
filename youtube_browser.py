"""Isolated anonymous Chromium/WPC experiment. No AI calls or personal profile."""
from pathlib import Path
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from security import normalized_video_url, child_environment
from youtube_support import is_youtube, error_code

CHROME = Path('/opt/youtube-chromium')
PLUGINS = Path('/opt/wpc-plugins')
SAFE_FIELDS = ('success', 'provider_loaded', 'browser_started', 'token_generated',
               'login_required', 'browser_failed', 'bytes', 'duration_seconds', 'audio', 'error_code')


def browser_args(source, folder, sub_lang=None):
    source = normalized_video_url(source)
    if not is_youtube(source):
        raise ValueError('Only public YouTube URLs are accepted.')
    args = ['--ignore-config', '--no-plugin-dirs', '--plugin-dirs', str(PLUGINS),
            '--no-playlist', '--use-extractors', '^youtube$', '--js-runtimes', 'node',
            '--socket-timeout', '20', '--retries', '1', '--extractor-retries', '1',
            '--match-filter', 'duration <= 1800 & !is_live',
            '--extractor-args', 'youtube:player_client=mweb;fetch_pot=always;pot_trace=true',
            '--extractor-args', 'youtubepot-wpc:browser_path=' + str(CHROME),
            '-S', 'res:1080', '--merge-output-format', 'mp4',
            '-o', str(Path(folder)/'source.%(ext)s'), '--verbose', source]
    if sub_lang:
        args += ['--write-subs', '--write-auto-subs', '--sub-langs', sub_lang]
    return args


def browser_probe(source, work):
    """Run a bounded, anonymous real download on the actual cloud runtime."""
    report = {'event': 'youtube_browser_probe', 'success': False, 'ai_calls': 0}
    started = time.monotonic()
    try:
        source = normalized_video_url(source)
        if not is_youtube(source):
            raise ValueError('Only YouTube URLs are accepted.')
        work = Path(work); work.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='youtube-browser-', dir=work) as folder:
            env = child_environment()
            # Neither a host browser profile nor its configuration can be used.
            env.update(HOME=folder, TMPDIR=folder, XDG_CACHE_HOME=folder, XDG_CONFIG_HOME=folder)
            command = ['xvfb-run', '-a', '-s', '-screen 0 1280x720x24 -nolisten tcp',
                       sys.executable, str(Path(__file__).resolve()), '--download-check', source, folder]
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, encoding='utf-8', env=env, start_new_session=True)
            try:
                stdout, stderr = proc.communicate(timeout=240)
            except subprocess.TimeoutExpired:
                if os.name != "nt":
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
                proc.communicate(timeout=10)
                raise
            if stdout.strip():
                child = json.loads(stdout.strip().splitlines()[-1])
                report.update({k: child[k] for k in SAFE_FIELDS if k in child})
            if proc.returncode:
                report['success'] = False
                report.setdefault('error_code', 'browser_worker_failed')
    except subprocess.TimeoutExpired:
        report['error_code'] = 'timeout'
    except Exception:
        report['error_code'] = 'browser_probe_failed'
    report['seconds'] = round(time.monotonic()-started, 1)
    print(json.dumps(report), flush=True)
    return report



def ydl_options(source, folder, logger):
    import yt_dlp
    parsed = yt_dlp.parse_options(browser_args(source, folder))
    # parse_options alone does not apply CLI plugin directories to the API.
    from yt_dlp.globals import plugin_dirs
    from yt_dlp.plugins import load_all_plugins
    plugin_dirs.value = parsed.options.plugin_dirs
    load_all_plugins()
    opts = parsed.ydl_opts
    opts.update(logger=logger, noprogress=True)
    return opts

def download_check(source, folder):
    report = dict(success=False, provider_loaded=False, browser_started=False,
                  token_generated=False, login_required=False, browser_failed=False)
    try:
        import yt_dlp
        from unittest.mock import patch
        class PrivateLogger:
            def debug(self, text):
                self.observe(text)
            def warning(self, text):
                self.observe(text)
            def error(self, text):
                self.observe(text)
            def observe(self, text):
                text = str(text)
                if 'not a bot' in text or 'LOGIN_REQUIRED' in text:
                    report['login_required'] = True
                if 'failed to start browser' in text:
                    report['browser_failed'] = True
        opts = ydl_options(source, folder, PrivateLogger())
        with yt_dlp.YoutubeDL(opts) as ydl:
            plugin = sys.modules.get('yt_dlp_plugins.extractor.getpot_wpc')
            if plugin is None:
                raise RuntimeError('WPC provider was not loaded.')
            report['provider_loaded'] = True
            launch = plugin.launch_browser
            mint = plugin.mint_po_token
            async def observed_launch(*args, **kwargs):
                try:
                    browser = await launch(*args, **kwargs)
                except Exception:
                    report['browser_failed'] = True
                    raise
                report['browser_started'] = True
                print(json.dumps({'event':'youtube_browser_stage', 'stage':'browser_started'}), flush=True)
                return browser
            async def observed_mint(*args, **kwargs):
                token = await mint(*args, **kwargs)
                report['token_generated'] |= bool(token)
                if token:
                    print(json.dumps({'event':'youtube_browser_stage', 'stage':'token_generated'}), flush=True)
                return token
            with patch.object(plugin, 'launch_browser', observed_launch), patch.object(plugin, 'mint_po_token', observed_mint):
                ydl.extract_info(source, download=True)
        videos = [p for p in Path(folder).glob('source.*') if p.suffix.lower() in ('.mp4','.mkv','.webm','.mov')]
        if not videos:
            raise RuntimeError('No video file was downloaded.')
        video = max(videos, key=lambda p:p.stat().st_size)
        result = subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type:format=duration','-of','json',str(video)],
                                capture_output=True, text=True, timeout=30, check=True, env=child_environment())
        data=json.loads(result.stdout)
        if not any(x.get('codec_type')=='video' for x in data.get('streams',[])):
            raise RuntimeError('No video stream.')
        report.update(success=True, bytes=video.stat().st_size,
                      duration_seconds=float(data['format']['duration']),
                      audio=any(x.get('codec_type')=='audio' for x in data['streams']))
    except Exception as error:
        report['error_code'] = 'youtube_verification' if report['login_required'] else 'browser_start_failed' if report['browser_failed'] else error_code(error)
    print(json.dumps(report),flush=True)
    return 0 if report['success'] else 1


if __name__=='__main__':
    if len(sys.argv)!=4 or sys.argv[1]!='--download-check' or not is_youtube(sys.argv[2]):
        raise SystemExit(2)
    env=child_environment();os.environ.clear();os.environ.update(env)
    raise SystemExit(download_check(normalized_video_url(sys.argv[2]),sys.argv[3]))
