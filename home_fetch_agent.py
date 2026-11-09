"""Home-PC YouTube fetcher for the cloud app. Run it while you work.

    python home_fetch_agent.py --setup https://crv-pdf-prototype.onrender.com
    python home_fetch_agent.py

It only polls the cloud app over HTTPS (nothing connects to this PC), downloads
the requested public YouTube video with the cloud importer's own settings
(youtube_support + CRV, up to 1080p, the same caption track) over this PC's
connection, and uploads the files. No Google login, cookie or AI call.
The shared token lives only in home_fetch.local.json beside this file.
"""
from pathlib import Path
import argparse
import json
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from security import normalized_video_url          # noqa: E402
from youtube_support import is_youtube, youtube_context, error_code, ensure_ffmpeg  # noqa: E402,F401
import home_fetch                                    # noqa: E402

CONFIG = ROOT / 'home_fetch.local.json'
PART = 16 * 1024 * 1024


def log(message):
    print(time.strftime('%H:%M:%S ') + message, flush=True)


def server_origin(value):
    parts = urllib.parse.urlsplit(value.strip())
    local = parts.hostname in ('127.0.0.1', 'localhost')
    if (parts.scheme != 'https' and not (local and parts.scheme == 'http')) or not parts.hostname \
            or parts.username or parts.password or parts.path not in ('', '/') or parts.query or parts.fragment:
        raise ValueError('Use the app origin, e.g. https://crv-pdf-prototype.onrender.com')
    return parts.scheme + '://' + parts.netloc


class Client:
    def __init__(self, origin, token, timeout=60):
        self.origin, self.token, self.timeout = origin, token, timeout

    def post(self, path, body=b'', content_type='application/octet-stream', timeout=None):
        request = urllib.request.Request(self.origin + path, data=body, method='POST', headers={
            'Authorization': 'Bearer ' + self.token, 'Content-Type': content_type,
            'User-Agent': 'crv-home-fetch/1'})
        with urllib.request.urlopen(request, timeout=timeout or self.timeout) as response:
            return json.loads(response.read())

    def next_job(self):
        return self.post('/home-fetch/next', timeout=45).get('job')

    def upload(self, rid, path):
        size, offset = path.stat().st_size, 0
        with path.open('rb') as stream:
            while offset < size:
                stream.seek(offset)
                chunk = stream.read(PART)
                for attempt in range(3):
                    try:
                        result = self.post(f'/home-fetch/upload/{rid}/{path.name}?offset={offset}', chunk, timeout=300)
                        break
                    except (OSError, urllib.error.URLError):
                        if attempt == 2:
                            raise
                        time.sleep(3 * (attempt + 1))
                # The server reports what it holds, so a retried part never duplicates.
                offset = int(result['size'])

    def finish(self, rid, ok, code=None):
        body = json.dumps({'ok': True} if ok else {'ok': False, 'error_code': code}).encode()
        self.post(f'/home-fetch/done/{rid}', body, 'application/json')


def fetch(url, folder, sub):
    import claude_real_video.core as core
    from unittest.mock import patch
    # This PC is the downloader: never hand the job back to a fetch queue.
    with patch.object(home_fetch, 'queue_dir', return_value=None), youtube_context():
        lang = sub.split(':', 1)[1] if sub else None
        sub_lang = core.remote_subtitle_lang(url, None if lang == 'auto' else lang) if sub else None
        # Same yt-dlp passthrough as pipeline.extract for URLs.
        video = Path(core.fetch_video(url, str(folder), ytdlp_args=['-S', 'res:1080'], sub_lang=sub_lang))
    subtitles = [p for p in folder.iterdir() if home_fetch.SUBTITLE_NAME.fullmatch(p.name)]
    return video, subtitles


def handle(client, job):
    rid = job.get('id', '')
    if not home_fetch.REQUEST_ID.fullmatch(str(rid)):
        return
    try:
        url = normalized_video_url(job.get('url', ''))
        if not is_youtube(url):
            raise ValueError
    except ValueError:
        log('Rejected a request that is not a YouTube video link.')
        return client.finish(rid, False, 'rejected')
    sub = job.get('sub') if home_fetch.SUB_REQUEST.fullmatch(str(job.get('sub') or '')) else None
    log('Downloading ' + url)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix='crv-home-fetch-') as temporary:
        folder = Path(temporary)
        try:
            video, subtitles = fetch(url, folder, sub)
            if not home_fetch.VIDEO_NAME.fullmatch(video.name):
                # e.g. source.f136.mp4: CRV fell back to an unmerged video-only stream.
                raise RuntimeError('No merged video file.')
        except Exception as error:
            code = error_code(error)
            log('Download failed: ' + code)
            return client.finish(rid, False, code)
        log(f'Uploading {video.stat().st_size / 1e6:.0f} MB' + (' with captions' if subtitles else ''))
        try:
            for path in [video, *subtitles]:
                client.upload(rid, path)
        except Exception:
            log('Upload failed.')
            try:
                client.finish(rid, False, 'upload_failed')
            except Exception:
                pass
            return
        client.finish(rid, True)
        log(f'Done in {time.monotonic() - started:.0f} s.')


def run(client):
    log('Waiting for YouTube links from ' + client.origin + ' (Ctrl+C to stop).')
    delay = 5
    while True:
        try:
            job = client.next_job()
            delay = 5
        except urllib.error.HTTPError as error:
            if error.code == 401:
                raise SystemExit('The cloud app rejected the token. Check VIDEO_PDF_FETCH_TOKEN on Render.')
            log(f'Cloud app answered {error.code}; retrying in {delay} s.')
            time.sleep(delay); delay = min(delay * 2, 60)
            continue
        except (OSError, urllib.error.URLError, ValueError):
            # A sleeping free instance takes about a minute to wake up.
            log(f'Cloud app not reachable; retrying in {delay} s.')
            time.sleep(delay); delay = min(delay * 2, 60)
            continue
        if job:
            handle(client, job)


def setup(origin):
    token = secrets.token_urlsafe(32)
    CONFIG.write_text(json.dumps({'server': origin, 'token': token}), encoding='utf-8')
    copied = False
    if sys.platform == 'win32':
        try:
            subprocess.run(['clip'], input=token.encode('ascii'), check=True, timeout=10)
            copied = True
        except (OSError, subprocess.SubprocessError):
            pass
    print('Saved ' + CONFIG.name + ' on this PC (do not share or commit it).')
    print('Next: on Render > Environment, add VIDEO_PDF_FETCH_TOKEN with this token, then deploy.')
    print('The token was copied to the clipboard.' if copied else 'Copy the "token" value from ' + CONFIG.name + '.')


def main():
    parser = argparse.ArgumentParser(description='Home-PC YouTube fetcher for the cloud app.')
    parser.add_argument('--setup', metavar='APP_ORIGIN', help='create a new token for this app origin')
    args = parser.parse_args()
    if args.setup:
        return setup(server_origin(args.setup))
    if not CONFIG.is_file():
        raise SystemExit('Run first: python home_fetch_agent.py --setup https://crv-pdf-prototype.onrender.com')
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    if not ensure_ffmpeg():
        # Without it yt-dlp leaves separate video/audio files (no merged source).
        raise SystemExit('ffmpeg and ffprobe were not found. Install them (winget install Gyan.FFmpeg) and retry.')
    try:
        run(Client(server_origin(config['server']), config['token']))
    except KeyboardInterrupt:
        log('Stopped.')


if __name__ == '__main__':
    main()
