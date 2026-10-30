"""Small defensive helpers; this is not a sandbox or a credential vault."""
import base64
import hashlib
import re
import os
import json
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


VIDEO_URL_ERROR = 'YouTubeまたはXの動画付き投稿リンクか、動画ファイルを指定してください。'
X_IMPORT_ERROR = 'Xの動画を取得できませんでした。投稿の公開状態・動画番号・取得制限を確認してください。ログインが必要な投稿には対応していません。動画ファイルのアップロードも利用できます。'


def normalized_video_url(value):
    """Only accept known video pages; strip tracking and never resolve short links.

    Always select one native X video. Without /video/N and --no-playlist,
    Twitter's extractor can follow an unrelated link in a non-video post.
    """
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError(VIDEO_URL_ERROR)
    value = value.strip()
    if re.search(r'[\x00-\x20\x7f\\]', value):
        raise ValueError(VIDEO_URL_ERROR)
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or parsed.username is not None or
                parsed.password is not None or parsed.port not in {None, 443}):
            raise ValueError(VIDEO_URL_ERROR)
    except ValueError:
        raise ValueError(VIDEO_URL_ERROR) from None
    if parsed.hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com'} and parsed.path == '/watch':
        identity = parse_qs(parsed.query).get('v', [''])[0]
        if re.fullmatch(r'[A-Za-z0-9_-]{11}', identity):
            return 'https://www.youtube.com/watch?v=' + identity
    if parsed.hostname == 'youtu.be' and re.fullmatch(r'/[A-Za-z0-9_-]{11}/?', parsed.path):
        return 'https://www.youtube.com/watch?v=' + parsed.path.strip('/')
    if parsed.hostname in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com', 'mobile.twitter.com'}:
        match = re.fullmatch(r'/([A-Za-z0-9_]{1,15}|i/web)/status/([0-9]{1,22})(?:/video/([1-9][0-9]?))?/?', parsed.path)
        if match:
            return f'https://x.com/{match[1]}/status/{match[2]}/video/{match[3] or "1"}'
    raise ValueError(VIDEO_URL_ERROR)


def validated_provider(key):
    if not isinstance(key, str) or not 20 <= len(key) <= 512:
        raise ValueError('Enter a valid OpenRouter or Anthropic API key.')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', key):
        raise ValueError('Invalid API key characters.')
    if key.startswith('sk-or-v1-'):
        return 'openrouter'
    if key.startswith('sk-ant-'):
        return 'anthropic'
    raise ValueError('Only OpenRouter and Anthropic keys are supported. Direct OpenAI keys are not supported.')


def redact(text, secret=''):
    text = str(text)
    if secret:
        text = text.replace(secret, '[REDACTED]')
    return re.sub(r'\bsk-[A-Za-z0-9_-]{12,}', '[REDACTED]', text)


def response_headers(payload=b'', media='', secure=False, trusted_script=None):
    # Permit only the exact inline scripts in the delivered, trusted UI.
    # A new injected script/event handler has no matching hash and cannot run.
    hashes = []
    if media.startswith('text/html'):
        if trusted_script is None:
            trusted_script = ('\n' + (Path(__file__).parent / 'ui.js').read_text(encoding='utf-8') + '\n').encode('utf-8')
        digest = base64.b64encode(hashlib.sha256(trusted_script).digest()).decode('ascii')
        hashes.append("'sha256-" + digest + "'")
    scripts = ' '.join(hashes) or "'none'"
    headers = {
        'Cache-Control': 'no-store',
        'Referrer-Policy': 'no-referrer',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'DENY',
        'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
        'Content-Security-Policy': (
            "default-src 'none'; base-uri 'none'; object-src 'none'; "
            "frame-ancestors 'none'; form-action 'none'; "
            f"script-src {scripts}; script-src-attr 'none'; "
            "style-src 'self' 'unsafe-inline'; connect-src 'self'; "
            "img-src 'self' data:; media-src 'self' blob:; font-src 'self'"
        ),
    }
    if secure:
        headers['Strict-Transport-Security'] = 'max-age=86400'
    return headers


# Explicit runtime settings only. Never inherit arbitrary host credentials,
# Python/Node startup hooks, or a wildcard VIDEO_PDF_* namespace.
CHILD_ENV_NAMES = frozenset("""
PATH PATHEXT SYSTEMROOT WINDIR COMSPEC TEMP TMP TMPDIR HOME USERPROFILE
LOCALAPPDATA APPDATA NUMBER_OF_PROCESSORS PROCESSOR_ARCHITECTURE
LANG LC_ALL LC_CTYPE TZ PYTHONUTF8 PYTHONIOENCODING PYTHONUNBUFFERED
PYTHONDONTWRITEBYTECODE PYTHONNOUSERSITE VIRTUAL_ENV
XDG_CACHE_HOME XDG_CONFIG_HOME XDG_DATA_HOME HF_HOME HF_HUB_CACHE
HUGGINGFACE_HUB_CACHE TRANSFORMERS_CACHE TORCH_HOME
HF_HUB_OFFLINE TRANSFORMERS_OFFLINE HF_HUB_DISABLE_TELEMETRY
PLAYWRIGHT_BROWSERS_PATH OMP_NUM_THREADS MKL_NUM_THREADS OPENBLAS_NUM_THREADS
CRV_MEMORY_DB CRV_NO_MEMORY VIDEO_PDF_SPEED_CHECK VIDEO_PDF_MODEL
VIDEO_PDF_EFFORT VIDEO_PDF_INPUT_USD_PER_MILLION VIDEO_PDF_OUTPUT_USD_PER_MILLION
SSL_CERT_FILE SSL_CERT_DIR REQUESTS_CA_BUNDLE CURL_CA_BUNDLE
""".split())


def child_environment(environ=None):
    source = os.environ if environ is None else environ
    return {k: v for k, v in source.items() if k.upper() in CHILD_ENV_NAMES}


def public_error(value, secret='', roots=()):
    """Keep useful error detail, without key-shaped values or host paths.

    Used only on responses, never on evidence, prompts or the stored document.
    Known workspace roots also cover paths containing spaces/Japanese text.
    """
    text = redact(value, secret)
    for root in sorted({str(p).rstrip('/\\') for p in roots if p}, key=len, reverse=True):
        for spelling in {root, root.replace('\\', '/'), root.replace('/', '\\')}:
            text = re.sub(re.escape(spelling) + r'(?=[/\\\s\x22\x27:]|$)', '[workspace]', text, flags=re.I)
    # Drive/UNC paths outside known roots; do not match https:// URLs.
    text = re.sub(r'(?<![A-Za-z0-9])(?:[A-Za-z]:[\\/]|\\\\[^\s\\/]+[\\/])[^\r\n\x22\x27<>]*', '[local path]', text)
    text = re.sub(r'(?<![A-Za-z0-9:/])/(?:app|home|Users|tmp|var/tmp|opt|root|usr/local)(?:/[^\s\x22\x27<>:,;]+)+', '[local path]', text)
    return text


def public_errors(value, roots=()):
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            if isinstance(v, str) and k in {'error', 'message', 'stderr', 'traceback'}:
                result[k] = public_error(v, roots=roots)
            elif isinstance(v, str) and k in {'source', 'evidence_dir'} and (v.startswith('/') or re.match(r'^[A-Za-z]:[\\/]', v)):
                result[k] = v.replace('\\', '/').rstrip('/').rsplit('/', 1)[-1]
            else:
                result[k] = public_errors(v, roots)
        return result
    if isinstance(value, list):
        return [public_errors(v, roots) for v in value]
    return value


def audit_request(method, path, status):
    """Only fixed route categories, time and outcome; no URL/token/body/IP."""
    parts = str(path).split('?', 1)[0].strip('/').split('/')
    known = {'login', 'healthz', 'status', 'configure', 'disconnect', 'upload', 'start', 'stop', 'ui.js'}
    category = next((p for p in parts if p in known), None)
    if category is None:
        category = 'download' if 'files' in parts else 'manual' if 'manual' in parts else 'page' if len(parts) <= 1 else 'other'
    if int(status) < 400 and category in {'status', 'healthz', 'ui.js'}:
        return
    event = {'event': 'http_result', 'time': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
             'method': method if method in {'GET', 'POST', 'HEAD'} else 'OTHER',
             'route': category, 'status': int(status)}
    try:
        print(json.dumps(event, separators=(',', ':')), flush=True)
    except (OSError, ValueError):
        pass  # Logging must not interrupt an existing generation.
