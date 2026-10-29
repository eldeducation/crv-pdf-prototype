"""Cloud gateway with a browser-compatible invitation login; no keys on disk."""
import hashlib
import http.server
import json
import os
import secrets
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie
import share_gateway as gateway
from security import response_headers

def external_origin(value):
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        raise ValueError('PUBLIC_BASE_URL must be an HTTPS origin without a path.')
    return 'https://' + parsed.netloc

LOGIN_HTML = '''<!doctype html><html lang="ja"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>CRV PDF - Sign in</title>
<style>*{box-sizing:border-box}body{margin:0;background:#f0f5e9;color:#203627;font:16px/1.7 system-ui,sans-serif;min-height:100vh;display:grid;place-items:center;padding:24px}main{width:min(100%,480px);padding:36px;background:#fffdf7;border:1px solid #b7caa8;box-shadow:7px 7px #cfe3bb}small{color:#576a4e}h1{font-size:28px;margin:12px 0}label{font-size:14px;font-weight:700;display:block;margin-top:24px}input{display:block;width:100%;padding:13px;border:1px solid #91aa7d;font:inherit;margin:8px 0 18px}button{padding:13px;background:#2b4b32;color:white;border:0;width:100%;font:inherit;font-weight:700;cursor:pointer}p{font-size:13px}</style>
<main><small>CRV PDF / INVITATION ONLY</small><h1>試作品にログイン</h1><p>動画から資料を作るクラウド試験版です。<br>Sign in with the invitation password shared by the owner.</p>
<form action="/login" method="post"><label for="password">招待用パスワード / Invitation password</label><input id="password" name="password" type="password" required minlength="24" maxlength="512" autocomplete="current-password"><button type="submit">ログイン / Sign in</button></form>
<p>ここにはAIのAPIキーを入力しないでください。<br>This is not your AI API key. PDF results are temporary; download them when ready.</p></main></html>'''.encode('utf-8')

class CloudHandler(gateway.Handler):
    password_digest = b''
    public_origin = ''
    login_tokens = {}
    login_attempts = []
    login_lock = threading.Lock()
    login_seconds = 8 * 3600

    def valid_host(self):
        return self.headers.get('Host', '') == urllib.parse.urlsplit(self.public_origin).netloc

    def authenticated(self):
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get('Cookie', ''))
        except Exception:
            return False
        token = cookies['__Host-video_access'].value if '__Host-video_access' in cookies else ''
        if not token or len(token) > 128:
            return False
        now = time.monotonic()
        with self.login_lock:
            for key, expiry in list(self.login_tokens.items()):
                if expiry < now:
                    del self.login_tokens[key]
            return self.login_tokens.get(token, 0) > now

    def login_page(self):
        self.send_response(200)
        headers = response_headers(LOGIN_HTML, 'text/html; charset=utf-8', secure=True, trusted_script=b'')
        headers['Content-Security-Policy'] = headers['Content-Security-Policy'].replace("form-action 'none'", "form-action 'self'")
        for name, value in {'Content-Type': 'text/html; charset=utf-8', 'Content-Length': str(len(LOGIN_HTML)), **headers}.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(LOGIN_HTML)

    def login(self):
        if self.headers.get('Origin') != self.public_origin:
            return self.send(403, {'error': 'Invalid login origin.'})
        if (self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded'
                or self.headers.get('Transfer-Encoding')):
            return self.send(415, {'error': 'Expected a login form.'})
        try:
            length = int(self.headers.get('Content-Length', '0'))
        except ValueError:
            return self.send(400, {'error': 'Invalid login request.'})
        if not 0 < length <= 4096:
            return self.send(413, {'error': 'Login request is too large.'})
        now = time.monotonic()
        with self.login_lock:
            self.login_attempts[:] = [t for t in self.login_attempts if now - t < 60]
            if len(self.login_attempts) >= 30:
                return self.send(429, {'error': 'Too many login attempts. Wait one minute.'}, extra_headers={'Retry-After': '60'})
            self.login_attempts.append(now)
        body = self.rfile.read(length)
        if len(body) != length:
            return self.send(400, {'error': 'Incomplete login request.'})
        try:
            fields = urllib.parse.parse_qs(body.decode('utf-8'), max_num_fields=4)
            passwords = fields.get('password', [])
            password = passwords[0] if len(passwords) == 1 else ''
        except (ValueError, UnicodeError):
            password = ''
        valid = secrets.compare_digest(hashlib.sha256(password.encode()).digest(), self.password_digest)
        password = ''
        if not valid:
            return self.send(401, {'error': '招待用パスワードが違います。戻って入力し直してください。 / Invalid invitation password.'})
        token = secrets.token_urlsafe(32)
        with self.login_lock:
            for key, expiry in list(self.login_tokens.items()):
                if expiry < now:
                    del self.login_tokens[key]
            if len(self.login_tokens) >= 128:
                return self.send(503, {'error': 'Too many active logins. Contact the owner.'})
            self.login_tokens[token] = now + self.login_seconds
        cookie = f'__Host-video_access={token}; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age={self.login_seconds}'
        return self.send(303, b'', extra_headers={'Location': '/', 'Set-Cookie': cookie})

    def do_GET(self):
        if self.command == 'GET' and self.path == '/healthz':
            return self.send(200, {'status': 'ok'})
        if not self.valid_host():
            return self.send(403, {'error': 'Invalid host.'})
        if self.command == 'POST' and self.path == '/login':
            return self.login()
        if not self.authenticated():
            if self.command == 'GET' and self.path in ('/', '/login'):
                return self.login_page()
            return self.send(401, {'error': '招待用パスワードでログインしてください。 / Invitation login required.'})
        if self.path in ('/', '/login') and self.command == 'GET':
            return self.send(302, b'', extra_headers={'Location': '/' + gateway.TOKEN + '/'})
        return super().do_GET()

    do_POST = do_GET

def main():
    password = os.environ.pop('VIDEO_PDF_ACCESS_PASSWORD', '')
    if len(password) < 24:
        raise ValueError('Set an invitation password with at least 24 characters.')
    origin = external_origin(os.getenv('PUBLIC_BASE_URL') or os.getenv('RENDER_EXTERNAL_URL', ''))
    for name in ('ANTHROPIC_API_KEY', 'OPENROUTER_API_KEY', 'OPENAI_API_KEY'):
        os.environ.pop(name, None)
    CloudHandler.password_digest = hashlib.sha256(password.encode()).digest()
    CloudHandler.public_origin = origin
    password = ''
    (gateway.ROOT / 'work').mkdir(exist_ok=True)
    server = http.server.ThreadingHTTPServer(('0.0.0.0', int(os.getenv('PORT', '7860'))), CloudHandler)
    server.daemon_threads = True
    record = {'pid': os.getpid(), 'port': server.server_port, 'path': '/' + gateway.TOKEN + '/', 'public_url': origin}
    (gateway.ROOT / 'work/sharing.local.json').write_text(json.dumps(record), encoding='utf-8')
    threading.Thread(target=gateway.session_expiry_worker, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()
        gateway.clean()

if __name__ == '__main__':
    main()
