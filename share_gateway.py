"""Temporary demo gateway; each browser gets a separate local app process."""
import atexit
import http.client
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from security import response_headers, normalized_video_url

ROOT = Path(__file__).resolve().parent
TOKEN = secrets.token_urlsafe(32)
SESSIONS = {}
LOCK = threading.Lock()
MAX_SESSION_AGE = 8 * 3600
MAX_SESSION_IDLE = 3600
UPLOAD_SLOTS = threading.BoundedSemaphore(2)
COPY_FILES = (
    'server.py', 'pipeline.py', 'openrouter_client.py', 'usage_guard.py',
    'content_quality.py', 'checkpoints.py', 'crv_worker.py', 'render.cjs',
    'layout.css', 'index.html', 'ui.js', 'runtime.local.json', 'security.py',
    'document_options.py', 'document_design.py', 'editorial_quality.py', 'restyle.py', 'source_references.py',
    'job_progress.py', 'action_grounding.py', 'manual_client.py', 'presentation_quality.py', 'web_research.py',
)


def allowed_route(method, route):
    if method == 'POST':
        return route in ('configure', 'disconnect', 'upload', 'start', 'stop', 'manual/respond')
    if method != 'GET':
        return False
    return (route in ('', 'ui.js', 'status') or bool(re.fullmatch(r'manual/request/[a-f0-9]{24}\.zip', route))
            or bool(re.fullmatch(
                r'files/\d{8}-\d{6}-[a-f0-9]{6}/(?:document\.pdf|document\.md|run\.json|usage\.json|review-notes\.txt|source-index\.json|source-video|assets/[A-Za-z0-9_.-]+\.(?:jpg|jpeg|png))', route)))


def start_input_error(data):
    if not isinstance(data, dict):
        return 'Expected a JSON object.'
    if data.get('restyle_from') and data.get('resume_folder'):
        return '途中再開とデザイン変更は同時に実行できません。'
    for key in ('restyle_from', 'resume_folder'):
        if data.get(key) and not re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{6}', str(data[key])):
            return '資料の識別子が不正です。'
    # The session server resolves saved IDs inside its own runs directory and
    # checks verification. The browser cannot supply an evidence path.
    if not any(data.get(k) for k in ('upload_id', 'resume_folder', 'restyle_from')):
        try:
            normalized_video_url(data.get('url', ''))
        except ValueError as error:
            return str(error)
    return None


def create_session(restore_identity=None):
    if len(SESSIONS) >= 8:
        raise ValueError('共有枠が使用中です。管理者に共有の再起動を依頼してください。')
    identity = restore_identity or secrets.token_urlsafe(24)
    if not re.fullmatch(r'[A-Za-z0-9_-]{32}', identity):
        raise ValueError('Invalid session identity.')
    parent = (ROOT / 'work' / 'share-sessions').resolve()
    folder = parent / identity
    if restore_identity and (not folder.is_dir() or folder.resolve().parent != parent):
        raise ValueError('Invalid session folder.')
    folder.mkdir(parents=True, exist_ok=bool(restore_identity))
    for name in COPY_FILES:
        shutil.copy2(ROOT / name, folder / name)
    shutil.copytree(ROOT / 'prompts', folder / 'prompts', dirs_exist_ok=bool(restore_identity))
    page = (folder / 'index.html').read_text(encoding='utf-8')
    page, script = page.split('<script>', 1)
    page = page.replace('<html lang="ja">', '<html lang="en" data-default-language="en">')
    page = page.replace('<main>', '<main><div class="panel"><b>共有用の試作品</b><p>ご自身のAPIキーを入力して利用してください。API料金はそのキーの残高から発生します。キーと生成結果はブラウザごとに分離されます。アップロードした動画はクラウドサーバーで処理され、抽出画像は選択したAIサービスへ送信されます。開発中のため、生成が途中停止する場合があります。</p></div>')
    page = page.replace('このPC内の画面', 'この画面').replace('キーは保存せず、起動中だけ保持します。', 'キーはクラウドサーバーのメモリにのみ保持し、共有プロセスの終了時に消えます。')
    page = page.replace('1GB', '90MB').replace('1024**3', '90*1024**2')
    page = page.replace('ローカル検証用の試作品です。Web公開・利用者管理・ブラウザ上での編集は次の段階です。',
                        'クラウドの試験公開版です。休止・再起動で生成物が消える場合があります。完成したPDFは保存してください。')
    page += '<script>' + script
    (folder / 'index.html').write_text(page, encoding='utf-8')
    env = os.environ.copy()
    for name in ('ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY', 'OPENAI_API_KEY', 'VIDEO_PDF_ACCESS_PASSWORD'):
        env.pop(name, None)
    process = subprocess.Popen([sys.executable, '-u', str(folder / 'server.py')],
        cwd=folder, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    for _ in range(100):
        if (folder / 'server.local.json').exists():
            try:
                record = json.loads((folder / 'server.local.json').read_text(encoding='utf-8'))
                if record.get('pid') != process.pid:
                    time.sleep(0.1)
                    continue
                session = {'folder': folder, 'process': process, 'url': urllib.parse.urlsplit(record['url']),
                           'created_at': time.monotonic(), 'last_seen': time.monotonic()}
                connection = http.client.HTTPConnection('127.0.0.1', session['url'].port, timeout=5)
                try:
                    connection.request('GET', session['url'].path + 'status')
                    response = connection.getresponse()
                    status = json.loads(response.read())
                    if response.status != 200 or not isinstance(status.get('csrf_token'), str):
                        raise ValueError('Session initialization failed.')
                    session['csrf_token'] = status['csrf_token']
                finally:
                    connection.close()
                SESSIONS[identity] = session
                return identity, session
            except (ValueError, OSError):
                pass
        if process.poll() is not None:
            break
        time.sleep(0.1)
    process.terminate()
    raise ValueError('共有画面を起動できませんでした。')


def clean():
    for session in SESSIONS.values():
        if session['process'].poll() is None:
            session['process'].terminate()


def expire_sessions():
    # Caller holds LOCK. Polling may keep a session alive, but not its API key.
    now = time.monotonic()
    for identity, session in list(SESSIONS.items()):
        if now - session['created_at'] > MAX_SESSION_AGE or now - session['last_seen'] > MAX_SESSION_IDLE:
            if session['process'].poll() is None:
                session['process'].terminate()
            del SESSIONS[identity]


def session_expiry_worker():
    while True:
        time.sleep(30)
        with LOCK:
            expire_sessions()


atexit.register(clean)


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(30)

    def log_message(self, *_):
        pass

    def send(self, status, payload, media='application/json; charset=utf-8', cookie=None, extra_headers=None):
        if not isinstance(payload, bytes):
            payload = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        secure = self.headers.get('Host', '') != f'127.0.0.1:{self.server.server_port}'
        for key, value in {'Content-Type': media, 'Content-Length': str(len(payload)),
                           **response_headers(payload, media, secure=secure)}.items():
            self.send_header(key, value)
        if cookie:
            secure = '; Secure' if not self.headers.get('Host', '').startswith('127.0.0.1:') else ''
            self.send_header('Set-Cookie', f'video_session={cookie}; HttpOnly; SameSite=Strict; Path=/{TOKEN}/{secure}')
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    def forward(self):
        prefix = '/' + TOKEN + '/'
        path = urllib.parse.urlsplit(self.path).path
        if not path.startswith(prefix):
            return self.send(404, {'error': 'ページがありません'})
        origin = self.headers.get('Origin')
        host = self.headers.get('Host', '')
        record = json.loads((ROOT / 'work' / 'sharing.local.json').read_text(encoding='utf-8-sig'))
        public = urllib.parse.urlsplit(record.get('public_url', ''))
        local_host = f'127.0.0.1:{self.server.server_port}'
        public_host = public.netloc if public.scheme == 'https' else ''
        if host not in {local_host, public_host} or not host:
            return self.send(403, {'error': 'Invalid host.'})
        expected_origin = ('http://' if host == local_host else 'https://') + host
        if (origin and origin != expected_origin) or (self.command == 'POST' and origin != expected_origin):
            return self.send(403, {'error': '別のサイトから操作できません'})
        route = urllib.parse.unquote(path[len(prefix):])
        if not allowed_route(self.command, route):
            return self.send(404, {'error': '操作がありません'})
        cookies = SimpleCookie()
        cookies.load(self.headers.get('Cookie', ''))
        identity = cookies['video_session'].value if 'video_session' in cookies else ''
        new_cookie = None
        with LOCK:
            expire_sessions()
            session = SESSIONS.get(identity)
            if not session:
                if self.command != 'GET' or route != '':
                    return self.send(401, {'error': '共有URLを開き直してください'})
                identity, session = create_session()
                new_cookie = identity
            session['last_seen'] = time.monotonic()
        body = None
        headers = {}
        if route.endswith('/source-video'):
            headers['Range'] = self.headers.get('Range', 'bytes=0-')
        if self.command == 'POST':
            supplied_csrf = self.headers.get('X-CSRF-Token', '').encode('utf-8')
            if not secrets.compare_digest(supplied_csrf, session['csrf_token'].encode('ascii')):
                return self.send(403, {'error': 'Session verification failed. Reload the page.'})
            if route != 'upload' and self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                return self.send(415, {'error': 'Expected application/json.'})
            length = int(self.headers.get('Content-Length', 0))
            limit = 90*1024**2 if route == 'upload' else 3_000_000 if route == 'manual/respond' else 100000
            if self.headers.get('Transfer-Encoding') or not 0 < length <= limit:
                return self.send(413, {'error': '動画は90MB以内、回答は3MB以内、設定は100KB以内です'})
            if route == 'upload':
                total = sum(p.stat().st_size for p in (session['folder'] / 'uploads').glob('*') if p.is_file())
                if total + length > 512*1024**2:
                    return self.send(413, {'error': 'この共有枠のアップロード容量に達しました'})
            body = self.rfile.read(length)
            if len(body) != length:
                return self.send(400, {'error': '送信が中断されました'})
            headers = {'Content-Type': self.headers.get('Content-Type', 'application/json')}
            headers['X-CSRF-Token'] = self.headers.get('X-CSRF-Token', '')
            if route == 'upload':
                headers['X-Filename'] = self.headers.get('X-Filename', 'video.mp4')
            if route == 'start':
                data = json.loads(body)
                error = start_input_error(data)
                if error:
                    return self.send(400, {'error': error})
        url = session['url']
        connection = http.client.HTTPConnection('127.0.0.1', url.port, timeout=90)
        try:
            connection.request(self.command, url.path + route, body=body, headers=headers)
            response = connection.getresponse()
            payload = response.read()
            extra = {name: response.getheader(name) for name in ('Content-Range', 'Accept-Ranges') if response.getheader(name)}
            return self.send(response.status, payload, response.getheader('Content-Type', 'application/octet-stream'), new_cookie, extra)
        finally:
            connection.close()

    def do_GET(self):
        upload = self.command == 'POST' and urllib.parse.urlsplit(self.path).path.endswith('/upload')
        if upload and not UPLOAD_SLOTS.acquire(blocking=False):
            return self.send(429, {'error': 'Uploads are busy. Try again shortly.'})
        try:
            self.forward()
        except (ValueError, OSError, http.client.HTTPException):
            self.send(400, {'error': '共有画面の処理に失敗しました。ページを開き直してください'})
        finally:
            if upload:
                UPLOAD_SLOTS.release()

    do_POST = do_GET


def main():
    global TOKEN
    port = 0
    if '--reuse-address' in sys.argv:
        old = json.loads((ROOT / 'work' / 'sharing.local.json').read_text(encoding='utf-8-sig'))
        candidate = old['path'].strip('/')
        if re.fullmatch(r'[A-Za-z0-9_-]{30,80}', candidate):
            TOKEN, port = candidate, int(old['port'])
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    record = {'pid': os.getpid(), 'port': server.server_port, 'path': '/' + TOKEN + '/'}
    (ROOT / 'work' / 'sharing.local.json').write_text(json.dumps(record), encoding='utf-8')
    if '--restore-sessions-file' in sys.argv:
        manifest = Path(sys.argv[sys.argv.index('--restore-sessions-file')+1]).resolve()
        if manifest.parent != (ROOT / 'work').resolve():
            raise ValueError('Invalid restore manifest.')
        identities = json.loads(manifest.read_text(encoding='utf-8-sig'))
        if not isinstance(identities, list) or len(identities) > 8 or len(set(identities)) != len(identities):
            raise ValueError('Invalid restore sessions.')
        for identity in identities:
            create_session(identity)
    threading.Thread(target=session_expiry_worker, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        clean()


if __name__ == '__main__':
    main()
