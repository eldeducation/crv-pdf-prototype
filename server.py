"""Loopback-only control panel. Keys stay in memory; there is no public hosting."""
from __future__ import annotations
import json
import os
import secrets
import sys
import re
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from security import validated_provider, redact, response_headers, public_errors
from source_references import write_index, local_video, byte_range
from job_progress import describe
from manual_client import ManualClient, MAX_RESPONSE_BYTES
from restyle import restyle_source
from model_catalog import fetch_models, key_status, CatalogError
import key_store
from video_upload import UploadReceiver, LOCAL_MAX_BYTES, SHARED_MAX_BYTES, SESSION_MAX_BYTES

from pipeline import ROOT, Config, DEFAULT_PROMPT, PrototypeError, load_env, run, provider_for, resume_fingerprint

load_env()
TOKEN = secrets.token_urlsafe(24)
LOCK = threading.Lock()


def last_job():
    # Restore result metadata only. Credentials are never included or persisted.
    candidates = sorted((ROOT / "runs").glob("*/run.json"), key=lambda p:p.stat().st_mtime, reverse=True)
    for path in candidates:
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            if not report.get("live_ai") and not report.get('manual_mode'):
                continue
            status = report.get("status", "failed")
            if status == "running":
                status = "failed"
                report = {**report, "error": ('前回のAPIなしのテストは中断されています。保存された内容から再開できます。'
                          if report.get('manual_mode') else '前回の処理は中断されています。API使用量の未確定分は管理画面で確認してください。')}
            layout = path.parent / "layout-check.json"
            if (status == "failed" and (path.parent / "document.pdf").is_file() and layout.is_file()
                    and not json.loads(layout.read_text(encoding="utf-8")).get("errors")):
                status = "needs_review"
                report = {**report, "content_verified": False}
            return {"status": status, "started": path.stat().st_mtime-report.get("seconds", 0),
                    'finished_at': path.stat().st_mtime, 'updated_at': path.stat().st_mtime,
                    "message": "完成しました" if status == "complete" else
                               "PDF作成済み・内容の確認が必要です" if status == "needs_review" else
                               report.get("error", "前回の生成は完了していません"),
                    "folder": path.parent.name, "report": report, 'manual_mode': bool(report.get('manual_mode'))}
        except (OSError, ValueError, TypeError):
            continue
    return None


def restyle_sources(limit=15):
    """Completed, content-verified runs in this server's own runs folder that can be
    rebuilt with new settings (newest first). Metadata only; restyle_source re-checks on start."""
    found = []
    for path in sorted((ROOT / 'runs').glob('*/run.json'), key=lambda p: p.stat().st_mtime, reverse=True)[:60]:
        try:
            folder, report, _ = restyle_source(ROOT, path.parent.name)
            title = json.loads((folder / 'document.json').read_text(encoding='utf-8')).get('title', '')
        except (ValueError, OSError, TypeError):
            continue
        found.append({'folder': folder.name, 'title': str(title)[:120], 'finished_at': path.stat().st_mtime,
                      'purpose': report.get('purpose', 'auto'), 'detail_level': report.get('detail_level', 'standard'),
                      'design': report.get('design', 'auto'), 'manual_mode': bool(report.get('manual_mode'))})
        if len(found) >= limit:
            break
    return found


KEY_IDLE_SECONDS = 30 * 60
KEY_STATUS_SECONDS = 15
STATE = {"api_key": os.getenv("OPENROUTER_API_KEY", "") or os.getenv("ANTHROPIC_API_KEY", ""), "job": last_job(),
         "key_used_at": time.monotonic(), "key_revision": 0, "catalog": None, "catalog_attempt": 0}
CSRF_TOKEN = secrets.token_urlsafe(32)
CANCEL = threading.Event()
UPLOADS = {}
UPLOAD_RECEIVER = UploadReceiver(ROOT / 'uploads', UPLOADS)
MANUAL_CLIENT = None
CATALOG_LOCK = threading.Lock()


def public_status():
    with LOCK:
        expire_key()
        job = dict(STATE["job"]) if STATE["job"] else None
        if job and job.get('manual_mode') and job.get('status') == 'running' and MANUAL_CLIENT:
            job['manual_request'] = MANUAL_CLIENT.status()
        if job and job.get("folder"):
            result_folder = ROOT / 'runs' / job['folder']
            job['references_available'] = (result_folder / 'source-index.json').is_file() or (result_folder / 'content-plan.json').is_file()
            job['progress'] = describe(result_folder, job, resume_fingerprint())
            usage_file = ROOT / "runs" / job["folder"] / "usage.json"
            if usage_file.is_file():
                try:
                    usage = json.loads(usage_file.read_text(encoding="utf-8"))
                    job["usage"] = {k: usage[k] for k in ('known_cost_usd', 'cost_complete', 'call_count', 'max_calls', 'budget_usd', 'pending')}
                    if isinstance(usage.get('estimate'), dict):
                        job['usage']['estimate'] = {k: usage['estimate'].get(k) for k in ('low_usd', 'high_usd', 'ceiling_usd', 'automatic_ceiling')}
                except (OSError, ValueError, KeyError):
                    pass
        return {"configured": bool(STATE["api_key"]), "job": job, "csrf_token": CSRF_TOKEN,
                'key_saved': bool(STATE.get('key_saved')), 'key_store_available': key_store.available(ROOT),
                "key_revision": STATE["key_revision"], "quality_pipeline": "quality-first-v3",
                "default_model": os.getenv("VIDEO_PDF_MODEL", "anthropic/claude-opus-5.5" if provider_for(STATE["api_key"]) == "openrouter" else "claude-opus-5-5"),
                "default_effort": os.getenv("VIDEO_PDF_EFFORT", "xhigh"), "provider": provider_for(STATE["api_key"])}


def requested_budget(value):
    """Blank/absent = automatic ceiling from the pre-run estimate (the normal case)."""
    if value in (None, '', 0):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        raise PrototypeError('費用の上限は数値で指定するか、空欄（自動）にしてください。') from None


def expire_key():
    # Caller holds LOCK. Polling the UI must not extend the key's lifetime.
    # A key the user chose to save on this PC is not dropped for being idle.
    running = STATE['job'] and STATE['job']['status'] == 'running'
    if (STATE['api_key'] and not running and not STATE.get('key_saved')
            and time.monotonic() - STATE['key_used_at'] >= KEY_IDLE_SECONDS):
        clear_connection()


def restore_saved_key():
    """At startup: reuse a key the user saved on this PC (Windows DPAPI), if any."""
    key = key_store.load(ROOT)
    if not key:
        return
    try:
        validated_provider(key)
    except Exception:
        return
    STATE['api_key'], STATE['key_saved'] = key, True
    STATE['key_used_at'] = time.monotonic()


def clear_connection():
    # Caller holds LOCK; invalidate both successful and in-flight catalogues.
    STATE['api_key'] = ''
    STATE['key_revision'] += 1
    STATE['catalog'] = None
    STATE['catalog_attempt'] = 0
    STATE['key_status'] = None
    STATE['key_saved'] = False


def model_catalog(force=False):
    with LOCK:
        expire_key()
        key, revision = STATE['api_key'], STATE['key_revision']
        if not key:
            raise CatalogError('no_key', 400)
        cached = STATE['catalog']
        if cached and (not force and time.time() - cached['fetched_at'] < 600):
            return cached
        if STATE['catalog_attempt'] and time.monotonic() - STATE['catalog_attempt'] < 10:
            if cached:
                return cached
            raise CatalogError('retry_later', 429)
        if not CATALOG_LOCK.acquire(blocking=False):
            raise CatalogError('loading', 409)
        STATE['catalog_attempt'] = time.monotonic()
    try:
        result = fetch_models(key, provider_for(key))
        with LOCK:
            expire_key()
            if STATE['key_revision'] != revision:
                raise CatalogError('changed', 409)
            result['key_revision'] = revision
            STATE['catalog'] = result
            return result
    finally:
        CATALOG_LOCK.release()


def key_expiry_worker():
    while True:
        time.sleep(15)
        with LOCK:
            expire_key()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def send(self, status, content, media="application/json; charset=utf-8", extra_headers=None):
        if isinstance(content, (dict, list)):
            content = json.dumps(public_errors(content, roots=(ROOT, Path.home())), ensure_ascii=False).encode("utf-8")
        elif isinstance(content, str):
            content = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", media)
        self.send_header("Content-Length", str(len(content)))
        for name, value in response_headers(content, media).items():
            self.send_header(name, value)
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(content)

    def route(self):
        prefix = "/" + TOKEN + "/"
        parts = urllib.parse.urlsplit(self.path)
        expected_host = f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host') != expected_host:
            self.send(403, {'error': 'Invalid host.'})
            return None
        if not parts.path.startswith(prefix):
            self.send(404, {"error": "ページが見つかりません"})
            return None
        if self.headers.get("Origin") and self.headers["Origin"] != f"http://{self.headers.get('Host')}":
            self.send(403, {"error": "別のサイトから操作できません"})
            return None
        return urllib.parse.unquote(parts.path[len(prefix):])

    def do_GET(self):
        route = self.route()
        if route is None:
            return
        if route == "":
            return self.send(200, (ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
        if route == "ui.js":
            return self.send(200, (ROOT / "ui.js").read_bytes(), "text/javascript; charset=utf-8")
        if route == "status":
            return self.send(200, public_status())
        if route == 'restyle-sources':
            return self.send(200, {'sources': restyle_sources()})
        if re.fullmatch(r'manual/request/[a-f0-9]{24}\.zip', route):
            with LOCK:
                client = MANUAL_CLIENT if STATE['job'] and STATE['job'].get('manual_mode') and STATE['job']['status'] == 'running' else None
            if not client:
                return self.send(404, {'error': '回答待ちの依頼はありません。'})
            try:
                return self.send(200, client.packet(route.split('/')[-1][:-4]), 'application/zip',
                                 {'Content-Disposition': 'attachment; filename="manual-request.zip"'})
            except ValueError as error:
                return self.send(409, {'error': str(error)})
        if route.startswith("files/"):
            match = re.fullmatch(r'files/(\d{8}-\d{6}-[a-f0-9]{6})/(.+)', route)
            if not match:
                return self.send(404, {'error': 'File not found.'})
            folder = (ROOT / 'runs' / match[1]).resolve()
            if not folder.is_relative_to((ROOT / 'runs').resolve()):
                return self.send(404, {'error': 'File not found.'})
            if match[2] == 'source-index.json':
                try:
                    if not (folder / 'source-index.json').is_file():
                        write_index(folder)
                    data = json.loads((folder / 'source-index.json').read_text(encoding='utf-8'))
                    data['local_video_available'] = local_video(ROOT, folder) is not None
                    return self.send(200, data)
                except (OSError, ValueError, TypeError, KeyError):
                    return self.send(404, {'error': 'Source references are not available yet.'})
            if match[2] == 'source-video':
                video = local_video(ROOT, folder)
                if not video:
                    return self.send(404, {'error': 'Source video is not available.'})
                size = video.stat().st_size
                try:
                    start, end = byte_range(self.headers.get('Range'), size)
                except ValueError:
                    return self.send(416, b'', extra_headers={'Content-Range': f'bytes */{size}'})
                with video.open('rb') as stream:
                    stream.seek(start)
                    chunk = stream.read(end-start+1)
                media = {'.mp4': 'video/mp4', '.webm': 'video/webm', '.mov': 'video/quicktime', '.mkv': 'video/x-matroska'}[video.suffix.lower()]
                return self.send(206, chunk, media, {'Accept-Ranges': 'bytes', 'Content-Range': f'bytes {start}-{end}/{size}'})
            target = (ROOT / "runs" / route[6:]).resolve()
            allowed = {"document.pdf": "application/pdf", "document.md": "text/markdown; charset=utf-8", "run.json": "application/json",
                       "review-notes.txt": "text/plain; charset=utf-8", "usage.json": "application/json"}
            if re.fullmatch(r'assets/[A-Za-z0-9_.-]+\.(?:jpg|jpeg|png)', match[2]):
                if not target.is_relative_to(folder / 'assets') or not target.is_file():
                    return self.send(404, {'error': 'Image not found.'})
                return self.send(200, target.read_bytes(), 'image/png' if target.suffix == '.png' else 'image/jpeg')
            if not target.is_relative_to((ROOT / "runs").resolve()) or target.name not in allowed or not target.is_file():
                return self.send(404, {"error": "ファイルがありません"})
            if target.suffix == '.json':
                return self.send(200, json.loads(target.read_text(encoding='utf-8')), allowed[target.name])
            return self.send(200, target.read_bytes(), allowed[target.name])
        return self.send(404, {"error": "ページがありません"})

    def do_POST(self):
        global MANUAL_CLIENT
        route = self.route()
        if route is None:
            return
        if not secrets.compare_digest(self.headers.get('X-CSRF-Token', '').encode('utf-8'), CSRF_TOKEN.encode('ascii')):
            return self.send(403, {'error': 'Session verification failed. Reload the page.'})
        try:
            length = int(self.headers.get("Content-Length", 0))
            if route == "upload":
                shared = ROOT.parent.name == 'share-sessions'
                result = UPLOAD_RECEIVER.receive(
                    self.headers, self.rfile, length,
                    maximum=SHARED_MAX_BYTES if shared else LOCAL_MAX_BYTES,
                    quota=SESSION_MAX_BYTES if shared else None)
                return self.send(200, result)
            if not 0 < length <= (MAX_RESPONSE_BYTES if route == 'manual/respond' else 99_999):
                raise PrototypeError("入力サイズを確認してください。")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError('Expected a JSON object.')
            if route == 'manual/respond':
                with LOCK:
                    if not MANUAL_CLIENT or not STATE['job'] or STATE['job']['status'] != 'running' or not STATE['job'].get('manual_mode'):
                        raise ValueError('回答待ちのテストはありません。')
                    MANUAL_CLIENT.submit(body)
                return self.send(200, {'accepted': True})
            if route == 'models':
                try:
                    return self.send(200, model_catalog(bool(body.get('refresh'))))
                except CatalogError as error:
                    return self.send(error.status, {'error': 'モデル一覧を取得できませんでした。', 'catalog_error': error.code})
            if route == 'key-status':
                # Remaining spending allowance of the configured key, so a 402 can be
                # explained without signing in to the provider. No AI generation.
                with LOCK:
                    expire_key()
                    key, revision = STATE['api_key'], STATE['key_revision']
                    cached = STATE.get('key_status')
                if not key:
                    return self.send(400, {'error': '最初にAPIキーを設定してください。'})
                if provider_for(key) != 'openrouter':
                    return self.send(200, {'supported': False})
                # Repeated presses (or a script) reuse a recent answer instead of calling
                # the provider each time with the user's key.
                if cached and cached[0] == revision and time.monotonic() - cached[1] < KEY_STATUS_SECONDS:
                    return self.send(200, cached[2])
                try:
                    result = {'supported': True, **key_status(key)}
                    with LOCK:
                        STATE['key_status'] = (revision, time.monotonic(), result)
                    return self.send(200, result)
                except CatalogError as error:
                    return self.send(error.status, {'error': 'キーの利用状況を取得できませんでした。', 'catalog_error': error.code})
            if route == 'disconnect':
                with LOCK:
                    if STATE['job'] and STATE['job']['status'] == 'running':
                        raise ValueError('Stop generation and wait for the current request to finish before disconnecting.')
                    clear_connection()
                    key_store.delete(ROOT)           # disconnecting also forgets a saved key
                return self.send(200, {'configured': False})
            if route == "stop":
                CANCEL.set()
                with LOCK:
                    if STATE['job'] and STATE['job']['status'] == 'running':
                        STATE['job'].update(stop_requested=True, updated_at=time.time())
                return self.send(200, {"message": "停止を受け付けました。実行中のAPI応答を記録した後、追加の送信を止めます。"})
            if route == "configure":
                key = str(body.get("api_key", "")).strip()
                if not key:
                    raise PrototypeError("APIキーを入力してください。")
                provider = validated_provider(key)
                remember = body.get('remember') is True and key_store.available(ROOT)
                with LOCK:
                    if STATE['job'] and STATE['job']['status'] == 'running':
                        raise ValueError('Wait for the current generation to finish before replacing the API key.')
                    clear_connection()
                    STATE["api_key"] = key
                    STATE['key_used_at'] = time.monotonic()
                    # Saving is opt-in; a key set without the box replaces any saved one.
                    if remember:
                        key_store.save(ROOT, key)
                        STATE['key_saved'] = True
                    else:
                        key_store.delete(ROOT)
                return self.send(200, {"configured": True, "provider": provider, "model": "anthropic/claude-opus-5.5" if provider == "openrouter" else "claude-opus-5-5"})
            if route == "start":
                with LOCK:
                    expire_key()
                    execution_mode = body.get('execution_mode', 'api')
                    if execution_mode not in ('api', 'manual'):
                        raise ValueError('実行方法が正しくありません。')
                    manual_mode = execution_mode == 'manual'
                    if STATE["job"] and STATE["job"]["status"] == "running":
                        raise PrototypeError("現在の生成が終わってから実行してください。")
                    resume_folder = body.get('resume_folder')
                    restyle_from = body.get('restyle_from')
                    if resume_folder and restyle_from:
                        raise ValueError('途中再開とデザイン変更は同時に実行できません。')
                    if restyle_from:
                        _, previous, _ = restyle_source(ROOT, restyle_from)
                        # The page's current execution mode and model apply, so a chat-made run can be
                        # re-edited through the API (and vice versa). Older clients omit them.
                        chosen = 'execution_mode' in body
                        if not chosen:
                            manual_mode = bool(previous.get('manual_mode'))
                        use_previous_model = not chosen or manual_mode or not str(body.get('model', '')).strip()
                        body = {**body, 'url': previous['source'], 'upload_id': None,
                                'prompt': previous.get('request_prompt', previous['prompt']),
                                'model': previous['model'] if use_previous_model else body['model'],
                                'effort': previous['effort'] if use_previous_model else body.get('effort', 'xhigh'),
                                'purpose': previous.get('purpose', 'auto'), 'detail_level': previous.get('detail_level', 'standard'),
                                'output_language': previous.get('output_language', 'auto'),
                                'presentation_modes': body.get('presentation_modes', previous.get('presentation_modes', [])),
                                'presentation_notes': body.get('presentation_notes', previous.get('presentation_notes', '')),
                                'external_research': previous.get('external_research', True)}
                    if resume_folder:
                        if not re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{6}', str(resume_folder)):
                            raise PrototypeError('再開する生成の識別子が不正です。')
                        previous = json.loads((ROOT / 'runs' / resume_folder / 'run.json').read_text(encoding='utf-8'))
                        manual_mode = bool(previous.get('manual_mode'))
                        if previous.get('quality_pipeline') != 'quality-first-v3' or previous.get('status') == 'complete':
                            raise PrototypeError('この生成は再開対象ではありません。')
                        resume_info = describe(ROOT / 'runs' / resume_folder, {'status': 'failed' if previous['status'] == 'running' else previous['status'], 'report': previous}, resume_fingerprint())['resume']
                        if not resume_info['available']:
                            raise PrototypeError('現在の保存状態ではそのまま再開できません。生成状況の案内を確認してください。')
                        body = {**body, 'url': previous['source'], 'prompt': previous.get('request_prompt', previous['prompt']),
                                'model': previous['model'], 'effort': previous['effort'], 'upload_id': None,
                                'purpose': previous.get('purpose', 'auto'), 'detail_level': previous.get('detail_level', 'standard'),
                                'output_language': previous.get('output_language', 'auto'),
                                'design': previous.get('design', 'auto'),
                                'visual_density': previous.get('visual_density', 'auto'),
                                'presentation_modes': previous.get('presentation_modes', []),
                                'presentation_notes': previous.get('presentation_notes', ''),
                                'restyle_from': previous.get('restyle_from'),
                                'external_research': previous.get('external_research', True)}
                        restyle_from = previous.get('restyle_from')
                    if not manual_mode and not STATE['api_key']:
                        raise PrototypeError('最初にAI接続を設定してください。')
                    source = UPLOADS.get(body.get("upload_id")) if body.get("upload_id") else body.get("url", "").strip()
                    if not source:
                        raise PrototypeError("動画を選ぶかYouTubeリンクを入力してください。")
                    effort = body.get("effort", "xhigh")
                    if effort not in {"auto", "none", "minimal", "low", "medium", "high", "xhigh", "max"}:
                        raise PrototypeError("推論設定が正しくありません。")
                    model_id = body.get("model", "claude-opus-5-5").strip()
                    if not manual_mode and not model_id:
                        raise PrototypeError('使用するモデルを選んでください。')
                    selected = next((m for m in (STATE.get('catalog') or {}).get('models', []) if m['id'] == model_id), None)
                    if not manual_mode and selected and selected['compatibility'] == 'unsupported':
                        raise PrototypeError('選択したモデルは画像の読み取り・文章作成・ツール利用の要件を満たしていません。')
                    reuse_options = resume_folder or (restyle_from and model_id == previous.get('model')
                                                      and not previous.get('manual_mode'))
                    options = (previous.get('model_options') if reuse_options else None) or selected
                    if not manual_mode and options and 'efforts' in options and options.get('reasoning') is not False and effort != 'auto' and effort not in options['efforts']:
                        raise PrototypeError('選択したモデルでは、この推論設定を使えません。')
                    config = Config(model=model_id, effort=effort, model_options=None if manual_mode else options,
                                    no_transcribe=bool(body.get("no_transcribe")),
                                    external_research=body.get('external_research', True),
                                    budget_usd=requested_budget(body.get('budget_usd')), cancel_event=CANCEL,
                                    confirm_estimate=body.get('confirm_estimate') is True,
                                    resume=bool(resume_folder), purpose=body.get('purpose', 'auto'),
                                    detail_level=body.get('detail_level', 'standard'), output_language=body.get('output_language', 'auto'),
                                    design=body.get('design', 'editorial'), visual_density=body.get('visual_density', 'auto'),
                                    presentation_modes=body.get('presentation_modes', []), presentation_notes=body.get('presentation_notes', ''),
                                    restyle_from=restyle_from)
                    CANCEL.clear()
                    key = '' if manual_mode else STATE['api_key']
                    if not manual_mode:
                        validated_provider(key)
                        STATE['key_used_at'] = time.monotonic()
                    folder_name = resume_folder or time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)
                    MANUAL_CLIENT = ManualClient(ROOT / 'runs' / folder_name, CANCEL) if manual_mode else None
                    manual_client = MANUAL_CLIENT
                    STATE["job"] = {"status": "running", "message": "準備しています", "started": time.time(), "folder": folder_name,
                                    'updated_at': time.time(), 'stop_requested': False, 'manual_mode': manual_mode}
                def worker():
                    def update(message):
                        with LOCK:
                            STATE["job"]["message"] = message
                            STATE['job']['updated_at'] = time.time()
                    try:
                        if manual_client:
                            manual_client.notify = update
                        folder = run(source, config=config, api_key=key,
                                     prompt=body.get("prompt") or DEFAULT_PROMPT, notify=update,
                                     run_dir=ROOT / "runs" / folder_name, client=manual_client)
                        report = json.loads((folder / "run.json").read_text(encoding="utf-8"))
                        with LOCK:
                            STATE["job"].update(status=report["status"],
                                                finished_at=time.time(), updated_at=time.time(), stop_requested=False,
                                                message="PDF作成済み・内容の確認が必要です" if report["status"] == "needs_review" else "完成しました",
                                                folder=folder.name, report=report)
                    except Exception as error:
                        with LOCK:
                            message = redact(error, key)
                            failed_report = ROOT / 'runs' / folder_name / 'run.json'
                            STATE["job"].update(status="failed", message=message[:1200],
                                finished_at=time.time(), updated_at=time.time(), stop_requested=False,
                                report=json.loads(failed_report.read_text(encoding='utf-8')) if failed_report.exists() else {})
                threading.Thread(target=worker, daemon=True).start()
                return self.send(202, {"started": True})
            self.send(404, {"error": "操作が見つかりません"})
        except (PrototypeError, ValueError, TypeError) as error:
            self.send(400, {"error": str(error)})
        except Exception:
            self.send(500, {"error": "処理に失敗しました。入力とローカルの実行環境を確認してください。"})


class LocalServer(ThreadingHTTPServer):
    # On Windows SO_REUSEADDR lets a second process bind a port that is already
    # serving, so a restart could silently share the old address. Fail instead.
    allow_reuse_address = os.name != "nt"


def main():
    global TOKEN
    port = 0
    if "--reuse-address" in sys.argv:
        record = ROOT / "server.local.json"
        if record.exists():
            previous = urllib.parse.urlsplit(json.loads(record.read_text(encoding="utf-8"))["url"])
            token = previous.path.strip("/")
            if previous.hostname == "127.0.0.1" and re.fullmatch(r"[A-Za-z0-9_-]{20,80}", token):
                port, TOKEN = previous.port, token
    try:
        server = LocalServer(("127.0.0.1", port), Handler)
    except OSError:
        if not port:
            raise
        print("前回のアドレスは使用中です（すでに起動していませんか？）。新しいアドレスで起動します。", flush=True)
        TOKEN = secrets.token_urlsafe(24)
        server = LocalServer(("127.0.0.1", 0), Handler)
    address = f"http://127.0.0.1:{server.server_port}/{TOKEN}/"
    (ROOT / "server.local.json").write_text(json.dumps({"url": address, "pid": os.getpid()}), encoding="utf-8")
    with LOCK:
        restore_saved_key()
    try:
        # yt-dlp merges video and audio with ffmpeg; winget's per-user folder may be off PATH.
        from youtube_support import ensure_ffmpeg
        ensure_ffmpeg()
    except Exception:
        pass
    print(address, flush=True)
    if "--open-browser" in sys.argv:
        import webbrowser
        webbrowser.open(address)
    print("この画面はPC内で動きます。" + ("保存したAPIキーを読み込みました。" if STATE.get('key_saved')
                                          else "終了するとメモリ内のAPIキーは消えます。"), flush=True)
    threading.Thread(target=key_expiry_worker, daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        STATE["api_key"] = ""


if __name__ == "__main__":
    main()
