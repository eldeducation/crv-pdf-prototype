"""Isolated anonymous Chromium/WPC experiment. No AI calls or personal profile."""
from pathlib import Path
import json
import asyncio
import http.cookiejar
import socket
import urllib.request
import os
import re
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
               'login_required', 'browser_failed', 'browser_start_reason', 'anonymous_cookie_count', 'matched_user_agent', 'bytes', 'duration_seconds', 'audio', 'error_code')



def worker_environment(folder, environ=None):
    source = os.environ if environ is None else environ
    env = child_environment(source)
    # Preserve only the temporary Xvfb display, never a host display/profile.
    display = source.get('DISPLAY', '')
    authority = source.get('XAUTHORITY', '')
    if re.fullmatch(r':[0-9]+(?:\.0)?', display) and authority:
        if Path(authority).resolve().is_relative_to(Path(folder).resolve()):
            env.update(DISPLAY=display, XAUTHORITY=authority)
    return env


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


def browser_start_diagnostic(folder):
    # Launch only about:blank with the default sandbox, not a logged-in profile.
    try:
        result = subprocess.run([str(CHROME),'--headless=new','--dump-dom',
                                 '--user-data-dir='+str(Path(folder)/'startup-check'),'about:blank'],
                                capture_output=True,text=True,timeout=12,env=child_environment())
        detail=(result.stderr or '').lower()
        if any(x in detail for x in ('no usable sandbox','failed to move to new namespace','operation not permitted','sandbox_linux','zygote_host_impl_linux')):
            return 'sandbox_unavailable'
        if 'cannot open shared object file' in detail:
            return 'browser_library_missing'
        if 'missing x server' in detail or 'display' in detail and 'error' in detail:
            return 'display_unavailable'
        return 'blank_page_ok' if result.returncode==0 and '<html' in result.stdout else 'chromium_start_failed'
    except subprocess.TimeoutExpired:
        return 'chromium_start_timeout'
    except Exception:
        return 'chromium_check_failed'


def chromium_command(config, folder):
    config.sandbox = True
    config.user_data_dir = str(Path(folder)/'anonymous-chrome-profile')
    # nodriver defaults disable site isolation; restore Chrome's protections.
    blocked = ('--disable-features=', '--disable-site-isolation-trials',
               '--no-sandbox', '--disable-web-security', '--ignore-certificate-errors',
               '--allow-running-insecure-content', '--remote-allow-origins=')
    args = [x for x in config() if not x.startswith(blocked)]
    return [str(CHROME), *args, '--remote-debugging-address=127.0.0.1']


async def ready_chromium(config, folder, report, processes):
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    config.host='127.0.0.1';config.port=port
    proc=await asyncio.create_subprocess_exec(*chromium_command(config,folder),
            stdin=asyncio.subprocess.DEVNULL,stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE)
    processes.append(proc)
    def ready():
        try:
            with urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/json/version',timeout=1) as response:
                return bool(json.load(response).get('webSocketDebuggerUrl'))
        except Exception:
            return False
    deadline=time.monotonic()+60
    while time.monotonic()<deadline:
        if proc.returncode is not None:
            text=(await proc.stderr.read()).decode('utf-8',errors='replace').lower()
            if any(x in text for x in ('no usable sandbox','failed to move to new namespace','sandbox_linux','zygote_host_impl_linux')):
                report['browser_start_reason']='sandbox_unavailable'
            elif 'cannot open shared object file' in text:
                report['browser_start_reason']='browser_library_missing'
            elif 'missing x server' in text or 'authorization required' in text:
                report['browser_start_reason']='display_unavailable'
            else:
                report['browser_start_reason']='chromium_exited'
            raise RuntimeError('Chromium did not start.')
        if await asyncio.to_thread(ready):
            report['browser_started']=True
            report['browser_start_reason']='ready'
            print(json.dumps({'event':'youtube_browser_stage','stage':'browser_started'}),flush=True)
            return
        await asyncio.sleep(1)
    report['browser_start_reason']='chromium_ready_timeout'
    raise RuntimeError('Chromium startup timed out.')


GUEST_COOKIES = frozenset(('VISITOR_INFO1_LIVE','VISITOR_PRIVACY_METADATA','YSC','PREF','CONSENT','SOCS','__Secure-YEC'))

def copy_guest_cookies(jar, cookies):
    count=0
    for cookie in cookies:
        if cookie.name not in GUEST_COOKIES or cookie.domain.lstrip('.') != 'youtube.com':
            continue
        if len(cookie.value)>4096:
            continue
        expiry=int(cookie.expires) if cookie.expires and cookie.expires>0 else None
        jar.set_cookie(http.cookiejar.Cookie(version=0,name=cookie.name,value=cookie.value,
            port=None,port_specified=False,domain=cookie.domain,domain_specified=True,
            domain_initial_dot=cookie.domain.startswith('.'),path=cookie.path or '/',path_specified=True,
            secure=bool(cookie.secure),expires=expiry,discard=expiry is None,comment=None,
            comment_url=None,rest={},rfc2109=False))
        count+=1
    return count

def download_check(source, folder):
    report = dict(success=False, provider_loaded=False, browser_started=False,
                  token_generated=False, login_required=False, browser_failed=False)
    processes = []
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
            async def observed_launch(config):
                try:
                    await ready_chromium(config,folder,report,processes)
                    # host+port attach to the browser already ready on loopback.
                    return await launch(config)
                except Exception:
                    report['browser_failed']=True
                    raise
            async def observed_mint(*args, **kwargs):
                token = await mint(*args, **kwargs)
                report['token_generated'] |= bool(token)
                if token:
                    print(json.dumps({'event':'youtube_browser_stage', 'stage':'token_generated'}), flush=True)
                return token
            # Warm a new anonymous browser before the extractor makes requests,
            # then reuse precisely this browser for the matching PO Tokens.
            loop=plugin.loop()
            config=plugin.nodriver.core.config.Config(browser_executable_path=str(CHROME),headless=False,sandbox=True)
            browser=loop.run_until_complete(observed_launch(config))
            cookies=loop.run_until_complete(browser.cookies.get_all())
            report['anonymous_cookie_count']=copy_guest_cookies(ydl.cookiejar,cookies)
            agent=loop.run_until_complete(browser.main_tab.evaluate('navigator.userAgent'))
            if isinstance(agent,str) and agent.startswith('Mozilla/5.0') and len(agent)<512 and not re.search(r'[\r\n]',agent):
                ydl.params['http_headers']['User-Agent']=agent
                report['matched_user_agent']=True
            async def reuse_browser(_config):
                return browser
            with patch.object(plugin, 'loop', return_value=loop), patch.object(plugin, 'launch_browser', reuse_browser), patch.object(plugin, 'mint_po_token', observed_mint):
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
        report['error_code'] = 'browser_start_failed' if report['browser_failed'] else 'youtube_verification' if report['login_required'] else error_code(error)
    finally:
        for proc in processes:
            if proc.returncode is None:
                try:
                    proc.terminate()
                except ProcessLookupError:
                    pass
    print(json.dumps(report),flush=True)
    return 0 if report['success'] else 1


if __name__=='__main__':
    if len(sys.argv)!=4 or sys.argv[1]!='--download-check' or not is_youtube(sys.argv[2]):
        raise SystemExit(2)
    env=worker_environment(sys.argv[3]);os.environ.clear();os.environ.update(env)
    raise SystemExit(download_check(normalized_video_url(sys.argv[2]),sys.argv[3]))
