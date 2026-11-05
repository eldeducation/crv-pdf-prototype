"""Bounded, sequential video uploads; incomplete files never become job inputs."""
import re
import secrets
import threading
import time
import urllib.parse
from pathlib import Path

SHARED_MAX_BYTES = 200 * 1024**2
LOCAL_MAX_BYTES = 1024**3
CHUNK_BYTES = 8 * 1024**2
COPY_BYTES = 64 * 1024
SESSION_MAX_BYTES = 512 * 1024**2
CHUNK_HEADERS = ('X-Upload-ID', 'X-Upload-Offset', 'X-Upload-Size')


def upload_metadata(headers, length, maximum):
    """Validate both declared total and chunk boundaries before reading any body."""
    if headers.get('Transfer-Encoding') or not 0 < length <= maximum:
        raise ValueError('動画のサイズが上限を超えているか、転送形式が不正です。')
    ext = Path(urllib.parse.unquote(headers.get('X-Filename', 'video.mp4'))).suffix.lower()
    if ext not in {'.mp4', '.mov', '.webm', '.mkv'}:
        raise ValueError('MP4・MOV・WebM・MKVを選んでください。')
    values = [headers.get(name) for name in CHUNK_HEADERS]
    if not any(value is not None for value in values):
        return None, 0, length, ext
    identity, raw_offset, raw_total = values
    if (not isinstance(identity, str) or not re.fullmatch(r'[a-f0-9]{24}', identity)
            or not isinstance(raw_offset, str) or not re.fullmatch(r'[0-9]{1,12}', raw_offset)
            or not isinstance(raw_total, str) or not re.fullmatch(r'[0-9]{1,12}', raw_total)):
        raise ValueError('分割アップロードの情報が不正です。')
    offset, total = int(raw_offset), int(raw_total)
    if not (0 < total <= maximum and length <= CHUNK_BYTES and offset + length <= total):
        raise ValueError('分割アップロードのサイズが不正です。')
    return identity, offset, total, ext


def body_chunks(source, length):
    """Forward exactly Content-Length bytes without buffering the entire video."""
    remaining = length
    while remaining:
        chunk = source.read(min(COPY_BYTES, remaining))
        if not chunk:
            raise ValueError('動画の転送が中断されました。')
        remaining -= len(chunk)
        yield chunk


class UploadReceiver:
    def __init__(self, folder, completed):
        self.folder = Path(folder)
        self.completed = completed
        self.pending = {}
        self.lock = threading.Lock()

    def receive(self, headers, source, length, maximum=LOCAL_MAX_BYTES, quota=None):
        identity, offset, total, ext = upload_metadata(headers, length, maximum)
        identity = identity or secrets.token_hex(12)
        with self.lock:
            now = time.monotonic()
            # Only this receiver's abandoned partial files are removed. Completed
            # videos, documents and other sessions' files are never deleted here.
            for key, item in list(self.pending.items()):
                if now - item['updated'] > 3600:
                    item['path'].unlink(missing_ok=True)
                    del self.pending[key]
            item = self.pending.get(identity)
            if item is None:
                if offset or identity in self.completed or len(self.pending) >= 8:
                    raise ValueError('アップロードを最初からやり直してください。')
                self.folder.mkdir(parents=True, exist_ok=True)
                if quota is not None:
                    used = sum(p.stat().st_size for p in self.folder.iterdir() if p.is_file())
                    reserved = sum(p['total'] - p['received'] for p in self.pending.values())
                    if used + reserved + total > quota:
                        raise ValueError('この共有枠のアップロード容量に達しました')
                path = self.folder / (identity + '.part')
                # Exclusive creation also prevents a restarted server from
                # overwriting an existing partial upload with the same ID.
                with path.open('xb'):
                    pass
                item = {'path': path, 'ext': ext, 'total': total, 'received': 0, 'updated': now}
                self.pending[identity] = item
            if (offset != item['received'] or total != item['total'] or ext != item['ext']):
                raise ValueError('アップロードの順序が一致しません。最初からやり直してください。')
            try:
                with item['path'].open('ab') as output:
                    for chunk in body_chunks(source, length):
                        output.write(chunk)
                item['received'] += length
                item['updated'] = time.monotonic()
                if item['received'] != total:
                    return {'received': item['received'], 'complete': False}
                final = self.folder / (identity + ext)
                # An existing completed file must never be replaced.
                if final.exists():
                    raise ValueError('アップロードを最初からやり直してください。')
                item['path'].rename(final)
                self.completed[identity] = final
                del self.pending[identity]
                return {'upload_id': identity, 'received': total, 'complete': True}
            except Exception:
                item['path'].unlink(missing_ok=True)
                self.pending.pop(identity, None)
                raise
