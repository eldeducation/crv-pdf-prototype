"""Streaming Render -> Modal bridge. Provider API keys never leave Render here."""
import hashlib
import http.client
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import time
from urllib.parse import urlsplit
import zipfile

from modal_contract import (VERSION, MAX_VIDEO_BYTES, MAX_RESULT_BYTES, MAX_UNPACKED_BYTES,
                            identity, detail_identity, validate_detail)

ENV_NAMES = ('VIDEO_PDF_MODAL_URL', 'VIDEO_PDF_MODAL_KEY', 'VIDEO_PDF_MODAL_SECRET',
             'VIDEO_PDF_MODAL_PROFILE')
MARKER = 'modal-extraction.json'


class ModalError(Exception):
    pass


def enabled():
    return bool(os.getenv('VIDEO_PDF_MODAL_URL', '').strip())


def session_environment(environ=None):
    from security import child_environment
    source = os.environ if environ is None else environ
    # Infrastructure credentials reach the session's HTTP client, but are NOT
    # added to the generic child allowlist used for ffmpeg/CRV/Chromium.
    return {**child_environment(source), **{k: source[k] for k in ENV_NAMES if k in source}}


def connection():
    url = urlsplit(os.getenv('VIDEO_PDF_MODAL_URL', '').strip())
    if (url.scheme != 'https' or not url.hostname or url.username or url.password or
            url.port not in (None, 443) or url.query or url.fragment or url.path not in ('', '/') or
            not re.fullmatch(r'[a-z0-9-]+(?:\.[a-z0-9-]+)?\.modal\.run', url.hostname)):
        raise ModalError('Modalの接続先設定が不正です。管理者に確認してください。')
    key, secret = (os.getenv(k, '') for k in ENV_NAMES[1:3])
    if not re.fullmatch(r'wk-[A-Za-z0-9]+', key) or not re.fullmatch(r'ws-[A-Za-z0-9]+', secret):
        raise ModalError('Modalの接続情報が設定されていません。管理者に確認してください。')
    return url.hostname, {'Modal-Key': key, 'Modal-Secret': secret}


def request(method, route, *, body=None, upload=None, download=None):
    hostname, headers = connection()
    conn = http.client.HTTPSConnection(hostname, timeout=120)
    headers = {**headers}
    if upload is not None:
        headers.update({'Content-Type': 'application/octet-stream', 'Content-Length': str(upload.stat().st_size)})
    elif body is not None:
        body = json.dumps(body, separators=(',', ':')).encode()
        headers.update({'Content-Type': 'application/json', 'Content-Length': str(len(body))})
    try:
        if upload is not None:
            conn.putrequest(method, route)
            for key, value in headers.items():
                conn.putheader(key, value)
            conn.endheaders()
            with upload.open('rb') as handle:
                for chunk in iter(lambda: handle.read(64 * 1024), b''):
                    conn.send(chunk)
        else:
            conn.request(method, route, body=body, headers=headers)
        response = conn.getresponse()
        if response.status >= 300:
            data = response.read(8192)
            if response.status in (401, 403):
                raise ModalError('Modalの接続認証に失敗しました。管理者に確認してください。')
            try:
                message = json.loads(data).get('detail', '')
            except (ValueError, AttributeError):
                message = ''
            # Server messages are a fixed allowlist, not tracebacks/URLs/keys.
            if not isinstance(message, str) or not message.startswith(('無料検証', '動画', '抽出', '追加画像', '処理', '接続')):
                message = 'Modal側で処理を受け付けられませんでした。'
            raise ModalError(message[:300])
        if download is not None:
            total = 0
            with download.open('wb') as handle:
                for chunk in iter(lambda: response.read(64 * 1024), b''):
                    total += len(chunk)
                    if total > MAX_RESULT_BYTES:
                        raise ModalError('抽出結果が受信上限を超えました。画像を削らずに停止しました。')
                    handle.write(chunk)
            return total
        return json.loads(response.read(2 * 1024**2))
    except (OSError, http.client.HTTPException, ValueError) as error:
        # Never relay request headers, endpoints or OS paths to the browser.
        raise ModalError('Modalとの通信が中断されました。同じ動画で再開すると、完了済みの抽出を再利用します。') from None
    finally:
        conn.close()


def health():
    result = request('GET', '/health')
    if result.get('version') != VERSION:
        raise ModalError('接続先の抽出バージョンが一致しません。')
    return {'configured': True, 'ready': True, 'version': VERSION}


def file_sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def unpack(archive, destination):
    destination = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        infos = bundle.infolist()
        if len(infos) > 1000 or sum(x.file_size for x in infos) > MAX_UNPACKED_BYTES:
            raise ModalError('抽出結果の展開上限を超えました。')
        seen = set()
        for info in infos:
            name = PurePosixPath(info.filename)
            if ('\\' in info.filename or ':' in info.filename or name.is_absolute() or
                    any(p in ('', '.', '..') for p in info.filename.split('/')) or
                    info.filename in seen or (info.external_attr >> 16) & 0o170000 == 0o120000):
                raise ModalError('抽出結果に不正なファイル名があります。')
            seen.add(info.filename)
            target = (destination / info.filename).resolve()
            if not target.is_relative_to(destination):
                raise ModalError('抽出結果の保存先が不正です。')
            if info.is_dir():
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(info) as source, target.open('wb') as output:
                shutil.copyfileobj(source, output, 64 * 1024)


def wait_for(job, *, notify, cancel_event=None, timeout=1050):
    deadline = time.monotonic() + timeout
    previous = None
    while time.monotonic() < deadline:
        if cancel_event is not None and cancel_event.is_set():
            request('POST', f'/jobs/{job}/cancel', body={})
            raise ModalError('処理を停止しました。')
        state = request('GET', f'/jobs/{job}')
        if state.get('status') == 'complete':
            return state
        if state.get('status') in ('failed', 'cancelled'):
            raise ModalError(state.get('message') or '抽出処理が停止しました。同じ処理を自動で繰り返していません。')
        phase = state.get('phase', 'queued')
        if phase != previous:
            notify({'queued': 'Modalで処理の開始を待っています', 'frames': 'Modalで画像を抽出しています',
                    'select': 'Modalで画像を整理しています', 'transcribe': 'Modalで音声を文字に起こしています',
                    'pack': 'Modalから抽出結果を受け取る準備をしています'}.get(phase, 'Modalで動画を準備しています'))
            previous = phase
        time.sleep(3)
    raise ModalError('処理の確認時間を超えました。Modalの処理は自動で再作成していません。同じ動画で再開してください。')


def prepare(source, folder, config, *, notify=print, api_key=''):
    source, folder = Path(source), Path(folder)
    if not source.is_file():
        raise ModalError('動画ファイルをアップロードしてください。Modal連携によるYouTubeリンク取得は今回の対象外です。')
    if not 0 < source.stat().st_size <= MAX_VIDEO_BYTES:
        raise ModalError('動画は既存の共有画面と同じ200MB以内です。画質は自動で下げません。')
    options = {'version': VERSION, 'frame_width': config.frame_width, 'max_frames': config.max_frames,
               'no_transcribe': config.no_transcribe,
               'profile': os.getenv('VIDEO_PDF_MODAL_PROFILE', 'windows-compatible')}
    cloud_stt = bool(getattr(config, 'cloud_transcribe', False) and not config.no_transcribe)
    if cloud_stt:
        import cloud_transcribe
        options['stt_model'] = cloud_transcribe.model_from_env()
    digest = file_sha(source)
    job = identity(digest, options)
    supplied_transcript = None
    # A create request is idempotent. A completed job is reused before any
    # optional paid speech API is called on Render.
    state = request('POST', '/jobs', body={'id': job, 'sha256': digest, 'bytes': source.stat().st_size,
                                         'extension': source.suffix.lower(), 'options': options})
    if cloud_stt and state['status'] in ('awaiting_upload', 'uploaded'):
        speech_cache = folder.parent / 'modal-speech-cache.json'
        cached = json.loads(speech_cache.read_text(encoding='utf-8')) if speech_cache.exists() else {}
        if cached.get('job') == job:
            supplied_transcript = cached['data']
        else:
            if not api_key.startswith('sk-or-'):
                raise ModalError('接続したOpenRouterキーで文字起こしを設定してください。')
            import claude_real_video.core as core
            with tempfile.TemporaryDirectory(dir=folder.parent) as speech:
                transcript = core.existing_subtitles(str(source), str(source), speech)
                is_subtitle = bool(transcript)
                if not transcript:
                    notify('文字起こしは既存設定のOpenRouterで行います。キーはModalへ送りません')
                    transcript = cloud_transcribe.transcribe(str(source), speech, key=api_key, model=options['stt_model'])
                supplied_transcript = {name: (Path(speech) / name).read_text(encoding='utf-8')
                                       for name in ('transcript.json', 'transcript.txt', 'cloud-transcribe.json')
                                       if (Path(speech) / name).is_file()}
                supplied_transcript['source_subtitles'] = is_subtitle
            speech_cache.write_text(json.dumps({'job': job, 'data': supplied_transcript}, ensure_ascii=False), encoding='utf-8')
    if state['status'] == 'awaiting_upload':
        notify('動画を画質を変えずにModalへ送っています')
        request('PUT', f'/jobs/{job}/source', upload=source)
    if state['status'] not in ('complete', 'running', 'queued'):
        request('POST', f'/jobs/{job}/start', body={'transcript': supplied_transcript})
    state = wait_for(job, notify=notify, cancel_event=getattr(config, 'cancel_event', None))
    folder.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=folder.parent) as temp:
        temp = Path(temp)
        archive = temp / 'result.zip'
        request('GET', f'/jobs/{job}/result', download=archive)
        unpack(archive, temp / 'unpacked')
        result = temp / 'unpacked'
        report = json.loads((result / 'report.json').read_text(encoding='utf-8'))
        if report['source_sha256'] != digest or report['options'] != options:
            raise ModalError('抽出した動画または設定が入力と一致しません。')
        frames = json.loads((result / 'crv/frames.json').read_text(encoding='utf-8'))['frames']
        if not 1 <= len(frames) <= config.max_frames:
            raise ModalError('抽出画像の枚数を確認できませんでした。')
        for frame in report['images']:
            relative = frame['file']
            if not re.fullmatch(r'frames/frame_[0-9]+\.jpg', relative):
                raise ModalError('抽出画像の名前が不正です。')
            if file_sha(result / 'crv' / relative) != frame['sha256']:
                raise ModalError('抽出画像の受信時の検証に失敗しました。')
        folder.mkdir(exist_ok=True)
        shutil.copytree(result / 'crv', folder, dirs_exist_ok=True)
        shutil.copyfile(result / 'report.json', folder.parent / 'modal-report.json')
        shutil.copyfile(result / 'extraction.log', folder.parent / 'extraction.log')
    video = folder / ('source' + source.suffix.lower())
    if not video.exists():
        try:
            os.link(source, video)
        except OSError:
            shutil.copyfile(source, video)
    manifest = (folder / 'MANIFEST.txt').read_text(encoding='utf-8')
    remote_root = report['evidence_path']
    manifest = manifest.replace(remote_root, str(folder.resolve()))
    manifest = re.sub(r'^source: .+$', lambda _: 'source: ' + str(source.resolve()), manifest, flags=re.M)
    (folder / 'MANIFEST.txt').write_text(manifest, encoding='utf-8')
    (folder / MARKER).write_text(json.dumps({'job': job, 'options': options, 'sha256': digest,
                                          'version': VERSION}), encoding='utf-8')
    notify(f'Modalでの動画準備が完了しました（画像{len(frames)}枚、画質変更なし）')


def remote_evidence(folder):
    return (Path(folder) / MARKER).is_file()


def detail(folder, spec, destination, *, prefix=None):
    metadata = json.loads((Path(folder) / MARKER).read_text(encoding='utf-8'))
    parent = metadata['job']
    job = detail_identity(parent, spec)
    request('POST', f'/jobs/{parent}/details', body={'id': job, 'spec': spec})
    wait_for(job, notify=lambda _: None, timeout=240)
    destination = Path(destination)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temp:
        temp = Path(temp)
        request('GET', f'/jobs/{job}/result', download=temp / 'result.zip')
        unpack(temp / 'result.zip', temp / 'out')
        data = json.loads((temp / 'out/report.json').read_text(encoding='utf-8'))
        if data['parent'] != parent or data['spec'] != spec:
            raise ModalError('追加画像の設定が一致しません。')
        if spec['kind'] == 'frame':
            shutil.copyfile(temp / 'out/detail.jpg', destination)
        else:
            suffix = '.png' if spec['format'] == 'png' else '.jpg'
            for index, name in enumerate(data['files'], 1):
                if not re.fullmatch(r'frame_[0-9]{3}\.(jpg|png)', name):
                    raise ModalError('区間画像の名前が不正です。')
                shutil.copyfile(temp / 'out' / name, destination / (prefix + f'{index:03}' + suffix))
        return data.get('ffmpeg_output', '')
