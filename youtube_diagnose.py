"""One-shot anonymous YouTube access diagnosis on the real cloud runtime.

Separates "YouTube refuses this server's network" from "yt-dlp picked the wrong
client". It asks, once each and without retries: which anonymous yt-dlp
clients get playable formats, whether IPv6 egress exists, and whether a real
anonymous Chromium (fresh profile, sandbox on) can play the same video on the
watch page and the privacy embed. When any client works it downloads the video
once and checks it with ffprobe.

No AI calls, personal profile/cookies, proxy or third-party download service.
Only the enumerated SAFE_FIELDS are logged: no IP address, cookie or token.
Enabled only by the administrator flag VIDEO_PDF_DIAGNOSE_YOUTUBE.
"""
from pathlib import Path
import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

from security import normalized_video_url, child_environment
from youtube_support import is_youtube, error_code, youtube_args, POT_PLUGINS
from youtube_browser import CHROME, worker_environment, ready_chromium

# Clients that returned formats from a residential connection come first.
CLIENTS = ('android_vr', 'web_embedded', 'mweb', 'tv', 'web_safari', 'web', 'tv_simply', 'ios', 'android')
PLAYABILITY = ('OK', 'LOGIN_REQUIRED', 'UNPLAYABLE', 'ERROR', 'CONTENT_CHECK_REQUIRED', 'AGE_CHECK_REQUIRED', 'LIVE_STREAM_OFFLINE')
RESULTS = ('ok', 'bot_check', 'no_formats', 'youtube_client', 'access_restricted', 'download_failed', 'timeout')
SAFE_FIELDS = frozenset(
    ['success', 'verdict', 'egress_colo', 'egress_ip_version', 'ipv6_reachable', 'ipv6_mweb', 'browser_started',
     'browser_watch_status', 'browser_watch_bot', 'browser_watch_played', 'browser_consent_page',
     'embed_status', 'embed_bot', 'embed_played', 'download_client', 'bytes', 'duration_seconds',
     'height', 'audio', 'error_code', 'stage', 'browser_watch_page', 'embed_page']
    + ['client_' + c for c in CLIENTS] + ['detail_' + c for c in CLIENTS])
CHILD_TIMEOUT = 600  # Render Free has 0.1 CPU; every stage reports as it finishes.


def video_id(source):
    return normalized_video_url(source).split('v=', 1)[1][:11]


def enum(value, allowed, other='other'):
    return value if value in allowed else other


# --- egress -----------------------------------------------------------------

def egress(report):
    """Cloudflare's trace names the data-centre city code; the IP stays private."""
    try:
        with urllib.request.urlopen('https://www.cloudflare.com/cdn-cgi/trace', timeout=10) as r:
            fields = dict(line.split('=', 1) for line in r.read(2048).decode().splitlines() if '=' in line)
        colo = fields.get('colo', '')
        report['egress_colo'] = colo if colo.isalpha() and len(colo) <= 4 else 'unknown'
        report['egress_ip_version'] = 6 if ':' in fields.get('ip', '') else 4
    except Exception:
        report['egress_colo'] = 'unavailable'
    try:
        address = socket.getaddrinfo('www.youtube.com', 443, socket.AF_INET6, socket.SOCK_STREAM)[0][4]
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as sock:
            sock.settimeout(5)
            sock.connect(address)
        report['ipv6_reachable'] = True
    except Exception:
        report['ipv6_reachable'] = False


# --- yt-dlp clients ---------------------------------------------------------

# Fixed vocabulary read from yt-dlp's own messages; message text is never logged.
FLAG_PATTERNS = (
    ('login', ('not a bot', 'LOGIN_REQUIRED', 'confirm your identity')),
    ('pot_skip', ('require a GVS PO Token', 'require a PO Token')),
    ('pot_made', ('Generating a', 'Retrieved a', 'via bgutil')),
    ('drm', ('DRM',)),
    ('sabr', ('SABR',)),
    ('jsc_fail', ('challenge solving failed', 'nsig extraction failed', 'Signature extraction failed',
                  'Unable to extract nsig', 'n challenge')),
    ('filtered', ('does not pass filter',)),
    ('unavailable', ('Video unavailable', 'This video is unavailable')),
)


class QuietLogger:
    def __init__(self):
        self.flags = set()

    @property
    def bot(self):
        return 'login' in self.flags

    def debug(self, text):
        self.observe(text)

    warning = error = info = debug

    def observe(self, text):
        text = str(text)
        for flag, needles in FLAG_PATTERNS:
            if any(n in text for n in needles):
                self.flags.add(flag)


def client_options(client, logger, extra=None):
    import yt_dlp
    parsed = yt_dlp.parse_options(youtube_args(client) + ['--extractor-retries', '0', '--retries', '0'] + list(extra or []))
    if POT_PLUGINS.is_dir():
        # parse_options alone does not register CLI plugin directories for the API.
        from yt_dlp.globals import plugin_dirs
        from yt_dlp.plugins import load_all_plugins
        plugin_dirs.value = parsed.options.plugin_dirs
        load_all_plugins()
    opts = parsed.ydl_opts
    # The CLI default ignoreerrors='only_download' returns None instead of
    # raising, which hid the real refusal in the first cloud run.
    opts.update(logger=logger, quiet=True, no_warnings=False, noprogress=True, verbose=True, ignoreerrors=False)
    return opts


def playable(info):
    return any(f.get('vcodec') not in (None, 'none') and f.get('url') and f.get('ext') != 'mhtml'
               for f in (info or {}).get('formats') or [])


def describe(logger, info):
    """e.g. 'f5v0+pot_skip' : format count, playable-video count, fixed flags."""
    formats = (info or {}).get('formats') or []
    video = sum(1 for f in formats if f.get('vcodec') not in (None, 'none') and f.get('url') and f.get('ext') != 'mhtml')
    head = 'none' if info is None else 'f%dv%d' % (len(formats), video)
    return '+'.join([head] + sorted(logger.flags))[:63]


def probe_client(source, client, extra=None, details=None):
    import yt_dlp
    logger = QuietLogger()
    info = None
    try:
        with yt_dlp.YoutubeDL(client_options(client, logger, extra)) as ydl:
            info = ydl.extract_info(source, download=False)
        result = 'ok' if playable(info) else 'bot_check' if logger.bot else 'no_formats'
    except Exception as error:
        code = error_code(error)
        if logger.bot or code == 'youtube_verification':
            result = 'bot_check'
        else:
            result = enum(code, RESULTS, 'download_failed')
    if details is not None:
        details['detail_' + client] = describe(logger, info)
    return result


def download(source, client, folder, report):
    import yt_dlp
    logger = QuietLogger()
    # Same quality ceiling as the normal import (CRV is called with res:1080).
    extra = ['-S', 'res:1080', '--merge-output-format', 'mp4', '-o', str(Path(folder) / 'source.%(ext)s')]
    with yt_dlp.YoutubeDL(client_options(client, logger, extra)) as ydl:
        ydl.extract_info(source, download=True)
    videos = [p for p in Path(folder).glob('source.*') if p.suffix.lower() in ('.mp4', '.mkv', '.webm')]
    if not videos:
        raise RuntimeError('No video file was downloaded.')
    video = max(videos, key=lambda p: p.stat().st_size)
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type,height:format=duration',
                             '-of', 'json', str(video)], capture_output=True, text=True, timeout=30, check=True,
                            env=child_environment())
    data = json.loads(result.stdout)
    streams = data.get('streams', [])
    heights = [int(s['height']) for s in streams if s.get('codec_type') == 'video' and s.get('height')]
    if not heights:
        raise RuntimeError('No video stream.')
    report.update(success=True, download_client=client, bytes=video.stat().st_size,
                  duration_seconds=round(float(data['format']['duration']), 1), height=max(heights),
                  audio=any(s.get('codec_type') == 'audio' for s in streams))


# --- real anonymous browser -------------------------------------------------

STATE_JS = '''(() => {
  const p = document.getElementById('movie_player');
  let r = null;
  try { r = p && p.getPlayerResponse ? p.getPlayerResponse() : null; } catch (e) {}
  r = r || window.ytInitialPlayerResponse || {};
  const s = r.playabilityStatus || {};
  const v = document.querySelector('video');
  let text = String(s.reason || '');
  try { text += ' ' + JSON.stringify((s.errorScreen || {}).playerErrorMessageRenderer || {}); } catch (e) {}
  text += ' ' + ((document.querySelector('.ytp-error') || {}).innerText || '');
  return JSON.stringify({host: location.hostname, status: String(s.status || ''),
    bot: /not a bot|sign in to confirm/i.test(text), time: v ? Number(v.currentTime) || 0 : -1});
})()'''

PLAY_JS = '''(() => { const v = document.querySelector('video');
  if (v) { v.muted = true; const p = v.play(); if (p && p.catch) p.catch(() => {}); }
  const b = document.querySelector('.ytp-large-play-button'); if (b && !v) b.click(); return !!v; })()'''


async def page_state(tab):
    try:
        value = await tab.evaluate(STATE_JS, return_by_value=True)
    except Exception:
        return {'eval': 'eval_error'}
    if not isinstance(value, str):
        return {'eval': 'eval_not_string'}
    try:
        return dict(json.loads(value), eval='ok')
    except ValueError:
        return {'eval': 'eval_bad_json'}


def page_kind(host, evaluated):
    if evaluated != 'ok':
        return evaluated
    host = str(host)
    if host.startswith('consent.'):
        return 'consent'
    if host in ('www.google.com', 'google.com') or host.startswith('sorry.'):
        return 'google_sorry'
    if host in ('www.youtube.com', 'm.youtube.com', 'www.youtube-nocookie.com'):
        return 'youtube'
    return 'other'


async def watch(browser, url, report, prefix):
    tab = await browser.get(url)
    await tab.sleep(8)
    try:
        await tab.evaluate(PLAY_JS, return_by_value=True)
    except Exception:
        pass
    await tab.sleep(12)
    state = await page_state(tab)
    report[prefix + '_page'] = page_kind(state.get('host', ''), state.get('eval'))
    report[prefix + '_status'] = enum(state.get('status', ''), PLAYABILITY, 'unknown' if not state.get('status') else 'other')
    report[prefix + '_bot'] = bool(state.get('bot'))
    report[prefix + '_played'] = bool(state.get('time', -1) > 1)
    if prefix == 'browser_watch':
        report['browser_consent_page'] = str(state.get('host', '')).startswith('consent.')


def browser_check(source, folder, report):
    import nodriver
    from nodriver.core.config import Config
    processes = []
    loop = asyncio.new_event_loop()
    try:
        # ready_chromium applies youtube_browser's protections (sandbox, site
        # isolation, certificate checks, fresh profile, loopback-only debugging).
        config = Config(browser_executable_path=str(CHROME), headless=False, sandbox=True,
                        browser_args=['--autoplay-policy=no-user-gesture-required'])
        bounded = lambda step, seconds: loop.run_until_complete(asyncio.wait_for(step, seconds))
        bounded(ready_chromium(config, folder, report, processes), 90)
        browser = bounded(nodriver.start(config=config), 60)
        vid = video_id(source)
        bounded(watch(browser, 'https://www.youtube.com/watch?v=' + vid, report, 'browser_watch'), 90)
        bounded(watch(browser, 'https://www.youtube-nocookie.com/embed/' + vid + '?autoplay=1&mute=1',
                      report, 'embed'), 90)
    finally:
        for proc in processes:
            if proc.returncode is None:
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass
        loop.close()


# --- orchestration ----------------------------------------------------------

def verdict(report):
    if report.get('success'):
        return 'downloaded'
    if any(report.get('client_' + c) == 'ok' for c in CLIENTS):
        return 'client_ok_download_failed'
    browser_bot = report.get('browser_watch_bot') or report.get('browser_watch_status') == 'LOGIN_REQUIRED'
    if browser_bot and not report.get('browser_watch_played') and not report.get('embed_played'):
        return 'network_refused_even_for_real_browser'
    if report.get('browser_watch_played') or report.get('embed_played'):
        return 'real_browser_plays_only_ytdlp_refused'
    return 'inconclusive'


def emit(report, stage):
    """Progress line after every stage, so a timeout still leaves evidence."""
    report['stage'] = stage
    report['verdict'] = verdict(report)
    print(json.dumps(safe_report(report)), flush=True)


def diagnose(source, folder):
    report = {'success': False}
    egress(report)
    emit(report, 'egress')
    # Browser first (and closed) so Chromium and yt-dlp never share the 512 MB.
    try:
        browser_check(source, folder, report)
    except Exception:
        report.setdefault('error_code', 'browser_check_failed')
    emit(report, 'browser')
    for client in CLIENTS:
        report['client_' + client] = probe_client(source, client, details=report)
        emit(report, 'client_' + client)
        time.sleep(2)  # pace one request per client; no retry loop
    if report.get('ipv6_reachable'):
        report['ipv6_mweb'] = probe_client(source, 'mweb', ['--force-ipv6'])
    working = next((c for c in CLIENTS if report.get('client_' + c) == 'ok'), None)
    if working:
        emit(report, 'download_started')
        try:
            download(source, working, folder, report)
        except Exception as error:
            report['error_code'] = error_code(error)
    emit(report, 'done')
    return report


def safe_report(report):
    return {k: v for k, v in report.items() if k in SAFE_FIELDS and isinstance(v, (bool, int, float, str)) and len(str(v)) < 64}


def run_probe(source, work):
    """Parent side: bounded child under a private Xvfb, sanitized environment."""
    report = {'event': 'youtube_diagnosis', 'success': False, 'ai_calls': 0}
    started = time.monotonic()
    try:
        source = normalized_video_url(source)
        if not is_youtube(source):
            raise ValueError('Only YouTube URLs are accepted.')
        work = Path(work); work.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='youtube-diagnose-', dir=work) as folder:
            env = child_environment()
            env.update(HOME=folder, TMPDIR=folder, XDG_CACHE_HOME=folder, XDG_CONFIG_HOME=folder)
            command = ['xvfb-run', '-a', '-s', '-screen 0 1280x720x24 -nolisten tcp',
                       sys.executable, str(Path(__file__).resolve()), '--diagnose', source, folder]
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                                    encoding='utf-8', env=env, start_new_session=True)
            timed_out = False
            try:
                stdout, _ = proc.communicate(timeout=CHILD_TIMEOUT)
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name != 'nt':
                    os.killpg(proc.pid, signal.SIGKILL)
                else:
                    proc.kill()
                # Retrying communicate() keeps the stage lines already printed.
                stdout, _ = proc.communicate(timeout=10)
            lines = [x for x in (stdout or '').strip().splitlines() if x.startswith('{')]
            if lines:
                report.update(safe_report(json.loads(lines[-1])))
            if timed_out:
                report['error_code'] = 'timeout'
            elif not lines and proc.returncode:
                report['error_code'] = 'diagnosis_worker_failed'
    except Exception:
        report['error_code'] = 'diagnosis_failed'
    report['seconds'] = round(time.monotonic() - started, 1)
    print(json.dumps(report), flush=True)
    return report


if __name__ == '__main__':
    if len(sys.argv) != 4 or sys.argv[1] != '--diagnose' or not is_youtube(sys.argv[2]):
        raise SystemExit(2)
    env = worker_environment(sys.argv[3]); os.environ.clear(); os.environ.update(env)
    try:
        result = diagnose(normalized_video_url(sys.argv[2]), sys.argv[3])
    except Exception:
        result = {'success': False, 'error_code': 'diagnosis_crashed'}
    print(json.dumps(safe_report(result)), flush=True)
    # Skip interpreter shutdown: nodriver's exit hooks can wait on the closed
    # browser. The parent still removes the temporary folder.
    os._exit(0 if result.get('success') else 1)
