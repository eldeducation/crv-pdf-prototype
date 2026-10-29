"""Cloud adapter for the existing per-browser gateway, with an invite password."""
import base64, hashlib, http.server, json, os, secrets, threading
from pathlib import Path
import share_gateway as gateway

def external_origin(value):
    from urllib.parse import urlsplit
    parsed=urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path not in ('','/') or parsed.query or parsed.fragment:
        raise ValueError('PUBLIC_BASE_URL must be an HTTPS origin without a path.')
    return 'https://'+parsed.netloc

class CloudHandler(gateway.Handler):
    password_digest=b''
    def authenticated(self):
        value=self.headers.get('Authorization','')
        if not value.startswith('Basic '): return False
        try:
            username, password=base64.b64decode(value[6:],validate=True).decode().split(':',1)
            return secrets.compare_digest(username,'demo') and secrets.compare_digest(hashlib.sha256(password.encode()).digest(),self.password_digest)
        except (ValueError,UnicodeError): return False
    def do_GET(self):
        if self.command=='GET' and self.path=='/healthz':
            return self.send(200,{'status':'ok'})
        if not self.authenticated():
            return self.send(401,{'error':'Invitation password required.'},extra_headers={'WWW-Authenticate':'Basic realm="CRV PDF trial", charset="UTF-8"'})
        if self.path=='/' and self.command=='GET':
            return self.send(302,b'',extra_headers={'Location':'/'+gateway.TOKEN+'/'})
        return super().do_GET()
    do_POST=do_GET

def main():
    password=os.environ.pop('VIDEO_PDF_ACCESS_PASSWORD','')
    if len(password)<24: raise ValueError('Set an invitation password with at least 24 characters.')
    origin=external_origin(os.getenv('PUBLIC_BASE_URL') or os.getenv('RENDER_EXTERNAL_URL',''))
    for name in ('ANTHROPIC_API_KEY','OPENROUTER_API_KEY','OPENAI_API_KEY'):os.environ.pop(name,None)
    CloudHandler.password_digest=hashlib.sha256(password.encode()).digest()
    password=''
    (gateway.ROOT/'work').mkdir(exist_ok=True)
    server=http.server.ThreadingHTTPServer(('0.0.0.0',int(os.getenv('PORT','7860'))),CloudHandler)
    server.daemon_threads=True
    record={'pid':os.getpid(),'port':server.server_port,'path':'/'+gateway.TOKEN+'/','public_url':origin}
    (gateway.ROOT/'work/sharing.local.json').write_text(json.dumps(record),encoding='utf-8')
    threading.Thread(target=gateway.session_expiry_worker,daemon=True).start()
    try:server.serve_forever()
    finally:server.server_close();gateway.clean()

if __name__=='__main__':main()
