"""Home-PC fetcher for YouTube links on a cloud host whose network YouTube refuses.

The cloud never connects to the home PC. The PC polls the cloud over HTTPS,
downloads with the same CRV/yt-dlp settings on its home connection and uploads
the files. A small file queue links the sandboxed CRV process and the public
gateway. No Google account, cookie, proxy or third-party service is involved.

Queue layout (cloud):  <queue>/enabled          feature switch
                        <queue>/agent-seen       PC heartbeat (mtime)
                        <queue>/requests/<id>.json   waiting for the PC
                        <queue>/claimed/<id>.json    being fetched
                        <queue>/results/<id>/        uploaded files + done.json
"""
import hashlib
import json
import os
import re
import secrets
import shutil
import time
from pathlib import Path

QUEUE_ENV = 'VIDEO_PDF_FETCH_QUEUE'
REQUEST_ID = re.compile(r'[a-f0-9]{24}')
VIDEO_NAME = re.compile(r'source\.(?:mp4|mkv|webm)')
SUBTITLE_NAME = re.compile(r'source\.[A-Za-z0-9-]{1,24}\.(?:srt|vtt)')
SUB_REQUEST = re.compile(r'agent:(?:auto|[A-Za-z0-9-]{1,24})')
MAX_VIDEO_BYTES = 2 * 1024**3
MAX_SUBTITLE_BYTES = 5 * 1024**2
MAX_PART_BYTES = 32 * 1024**2
HEARTBEAT_SECONDS = 90      # the PC polls about every 20 s
CLAIM_SECONDS = 120         # a waiting request the PC never picked up
RESULT_SECONDS = 20 * 60    # inside the 30-minute extraction limit
STALE_SECONDS = 2 * 3600
ERROR_CODES = ('youtube_verification', 'access_restricted', 'youtube_client', 'download_failed', 'rejected', 'upload_failed')

AGENT_OFFLINE = ('YouTubeリンクの取得には、自宅PCの取得係の起動が必要です。'
                 'PCで「home_fetch_agent」を起動してから再実行するか、動画ファイルをアップロードしてください。')


def queue_dir(environ=None):
    value = (os.environ if environ is None else environ).get(QUEUE_ENV, '')
    path = Path(value) if value else None
    return path if path and (path / 'enabled').is_file() else None


def token_digest(token):
    return hashlib.sha256(token.encode('utf-8')).digest()


def _write_json(path, data):
    temporary = path.with_name(path.name + '.' + secrets.token_hex(4) + '.tmp')
    temporary.write_text(json.dumps(data), encoding='utf-8')
    os.replace(temporary, path)


# --- cloud: the CRV process asks for one video ---------------------------------

def agent_online(queue, now=time.time):
    try:
        return now() - (queue / 'agent-seen').stat().st_mtime < HEARTBEAT_SECONDS
    except OSError:
        return False


def request_download(queue, url, out_dir, sub=None, sleep=time.sleep, now=time.time):
    """Wait for the home PC to deliver source.<ext> (+ captions) into out_dir."""
    if not agent_online(queue, now):
        raise RuntimeError(AGENT_OFFLINE)
    if sub is not None and not SUB_REQUEST.fullmatch(sub):
        sub = None
    rid = secrets.token_hex(12)
    request = queue / 'requests' / (rid + '.json')
    result = queue / 'results' / rid
    _write_json(request, {'id': rid, 'url': url, 'sub': sub, 'created': now()})
    started = now()
    try:
        while not (result / 'done.json').is_file():
            if request.exists() and now() - started > CLAIM_SECONDS:
                raise RuntimeError(AGENT_OFFLINE)
            if now() - started > RESULT_SECONDS:
                raise RuntimeError('自宅PCでの取得が時間内に終わりませんでした。（timeout）')
            sleep(2)
        status = json.loads((result / 'done.json').read_text(encoding='utf-8'))
        if not status.get('ok'):
            code = status.get('error_code') if status.get('error_code') in ERROR_CODES else 'download_failed'
            raise RuntimeError('自宅PCでYouTube動画を取得できませんでした。（' + code + '）')
        videos = [p for p in result.iterdir() if VIDEO_NAME.fullmatch(p.name)]
        if len(videos) != 1:
            raise RuntimeError('自宅PCから動画ファイルが届きませんでした。（upload_failed）')
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        for item in result.iterdir():
            if VIDEO_NAME.fullmatch(item.name) or SUBTITLE_NAME.fullmatch(item.name):
                shutil.move(str(item), str(out_dir / item.name))
        return str(out_dir / videos[0].name)
    finally:
        request.unlink(missing_ok=True)
        shutil.rmtree(result, ignore_errors=True)


# --- cloud: the gateway serves the PC ------------------------------------------

class HomeFetchQueue:
    def __init__(self, root):
        self.root = Path(root)
        for name in ('requests', 'claimed', 'results'):
            (self.root / name).mkdir(parents=True, exist_ok=True)
        (self.root / 'enabled').touch()

    def heartbeat(self):
        (self.root / 'agent-seen').touch()

    def purge(self, now=None):
        now = now or time.time()
        for folder in ('requests', 'claimed'):
            for item in (self.root / folder).glob('*.json'):
                try:
                    if now - item.stat().st_mtime > STALE_SECONDS:
                        item.unlink()
                except OSError:
                    pass
        for item in (self.root / 'results').iterdir():
            try:
                if now - item.stat().st_mtime > STALE_SECONDS:
                    shutil.rmtree(item, ignore_errors=True)
            except OSError:
                pass

    def next(self, wait_seconds=20, sleep=time.sleep):
        """Long-poll: the oldest waiting request, claimed for the PC, or None."""
        self.heartbeat()
        self.purge()
        deadline = time.monotonic() + wait_seconds
        while True:
            for item in sorted((self.root / 'requests').glob('*.json'), key=lambda p: p.stat().st_mtime):
                rid = item.stem
                if not REQUEST_ID.fullmatch(rid):
                    continue
                claimed = self.root / 'claimed' / item.name
                try:
                    os.replace(item, claimed)
                    data = json.loads(claimed.read_text(encoding='utf-8'))
                except (OSError, ValueError):
                    continue
                (self.root / 'results' / rid).mkdir(exist_ok=True)
                return {'id': rid, 'url': data.get('url', ''), 'sub': data.get('sub')}
            if time.monotonic() >= deadline:
                return None
            sleep(1)
            self.heartbeat()

    def _claimed(self, rid):
        if not REQUEST_ID.fullmatch(str(rid)) or not (self.root / 'claimed' / (rid + '.json')).is_file():
            raise KeyError('Unknown request.')
        return self.root / 'results' / rid

    def append(self, rid, name, offset, read, length):
        """Append one part. offset must equal the bytes already stored, so a
        retried part is idempotent. read(n) supplies the request body."""
        folder = self._claimed(rid)
        if VIDEO_NAME.fullmatch(name):
            limit = MAX_VIDEO_BYTES
        elif SUBTITLE_NAME.fullmatch(name):
            limit = MAX_SUBTITLE_BYTES
        else:
            raise ValueError('Unexpected file name.')
        if not 0 < length <= MAX_PART_BYTES:
            raise ValueError('Invalid part size.')
        path = folder / name
        current = path.stat().st_size if path.exists() else 0
        if offset != current:
            return current
        if current + length > limit:
            raise ValueError('File is too large.')
        with path.open('ab') as stream:
            remaining = length
            while remaining:
                chunk = read(min(1024 * 1024, remaining))
                if not chunk:
                    stream.truncate(current)
                    raise ValueError('Upload interrupted.')
                stream.write(chunk)
                remaining -= len(chunk)
        self.heartbeat()
        return current + length

    def finish(self, rid, ok, error_code=None):
        folder = self._claimed(rid)
        code = error_code if error_code in ERROR_CODES else 'download_failed'
        _write_json(folder / 'done.json', {'ok': bool(ok)} if ok else {'ok': False, 'error_code': code})
        (self.root / 'claimed' / (rid + '.json')).unlink(missing_ok=True)
        self.heartbeat()
