"""Start a loopback-only app with a fresh, disconnected API state."""
from pathlib import Path
import argparse, http.client, json, os, re, subprocess, sys, time, urllib.parse, webbrowser
ROOT = Path(__file__).resolve().parent
APP = ROOT / 'app'

def local_address(value):
    p = urllib.parse.urlsplit(value)
    if (p.scheme != 'http' or p.hostname != '127.0.0.1' or p.username or p.password
            or not p.port or p.query or p.fragment or not re.fullmatch(r'/[A-Za-z0-9_-]{20,80}/', p.path)):
        raise ValueError('Invalid local server address')
    return p

def is_ready(address):
    p = local_address(address)
    connection = http.client.HTTPConnection('127.0.0.1', p.port, timeout=2)
    try:
        connection.request('GET', p.path)
        response = connection.getresponse()
        return response.status == 200 and b'VIDEO' in response.read(2000000)
    except OSError:
        return False
    finally:
        connection.close()

def launch_environment(environ=None):
    env = dict(os.environ if environ is None else environ)
    for name in list(env):
        if name in ('OPENROUTER_API_KEY','ANTHROPIC_API_KEY','OPENAI_API_KEY','PYTHONHOME','PYTHONPATH') or name.startswith(('VIDEO_PDF_','RENDER_')):
            env.pop(name, None)
    scripts = ROOT / '.venv' / ('Scripts' if os.name == 'nt' else 'bin')
    env['PATH'] = str(scripts) + os.pathsep + env.get('PATH','')
    env['PYTHONUNBUFFERED'] = '1'
    env['CRV_MEMORY_DB'] = str(APP / 'work/memory.db')
    env['XDG_CACHE_HOME'] = str(APP / 'work/cache')
    return env

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    py = ROOT / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not py.is_file() or not (APP / 'runtime.local.json').is_file():
        raise RuntimeError('First run: python setup_local.py')
    if (APP / '.env').exists():
        raise RuntimeError('Remove app/.env; enter API keys only in the local UI.')
    record = APP / 'server.local.json'
    address = None
    if record.exists():
        old = json.loads(record.read_text(encoding='utf-8'))
        if is_ready(old['url']):
            address = old['url']
    if not address:
        (APP / 'work').mkdir(exist_ok=True)
        options = {'creationflags':subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS} if os.name == 'nt' else {'start_new_session':True}
        previous_record = record.read_bytes() if record.exists() else None
        with (APP/'work/server.stdout.log').open('wb') as out, (APP/'work/server.stderr.log').open('wb') as err:
            process = subprocess.Popen([str(py), '-u', 'server.py', '--reuse-address'], cwd=APP, env=launch_environment(), stdout=out, stderr=err, **options)
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError('Server exited. Ask your coding agent to inspect app/work/server.stderr.log locally; do not publish the log.')
            if record.exists():
                raw = record.read_bytes()
                current = json.loads(raw)
                # Windows venv's redirector can spawn a different Python PID.
                if raw != previous_record and is_ready(current['url']):
                    address = current['url']
                    break
            time.sleep(.25)
        if not address:
            raise RuntimeError('Server is not ready. Inspect the local log.')
    print(address)
    if not args.no_browser:
        webbrowser.open(address)

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, ValueError, OSError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
