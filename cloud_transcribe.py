"""Speech-to-text through OpenRouter instead of Whisper on this machine (opt-in).

Runs inside crv_worker.py in place of CRV's local Whisper step, so the video's own
subtitles still win and only videos without them are sent. The audio (not the
video) goes to OpenRouter and the transcription provider it routes to. Only
segment text and times come back; the API key is never written or printed.
"""
import base64
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from security import child_environment

ENDPOINT = 'https://openrouter.ai/api/v1/audio/transcriptions'
DEFAULT_MODEL = 'openai/whisper-large-v3'
# Models that return segment times (verbose_json). Times are needed to match speech to frames.
MODELS = ('openai/whisper-large-v3', 'openai/whisper-large-v3-turbo', 'openai/whisper-1')
FLAG_ENV = 'VIDEO_PDF_CLOUD_STT'     # '1' = the key follows on the worker's stdin (never in the environment)
MODEL_ENV = 'VIDEO_PDF_STT_MODEL'
CHUNK_SECONDS = 600           # 10 minutes of 48 kbps mono MP3 is about 3.6 MB (4.8 MB as base64)
MAX_SECONDS = 2 * 3600
RECORD = 'cloud-transcribe.json'


class TranscribeError(Exception):
    pass


def model_from_env():
    model = os.getenv(MODEL_ENV, '').strip() or DEFAULT_MODEL
    if model not in MODELS:
        raise TranscribeError('文字起こしのモデル指定が対応外です。')
    return model


def _ffmpeg(args):
    result = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', *args], env=child_environment(),
                            capture_output=True, text=True, encoding='utf-8', errors='replace')
    if result.returncode != 0:
        raise TranscribeError('音声の取り出しに失敗しました。')


def _duration(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)],
                            capture_output=True, text=True, env=child_environment())
    try:
        return float(result.stdout.strip())
    except ValueError:
        raise TranscribeError('音声の長さを読み取れませんでした。') from None


def audio_chunks(video, folder, start=None, end=None):
    """Mono 16 kHz MP3 pieces of at most CHUNK_SECONDS: [(offset_seconds, path)]."""
    whole = Path(folder) / 'audio.mp3'
    window = (['-ss', str(start)] if start else []) + (['-to', str(end)] if end else [])
    _ffmpeg([*window, '-i', str(video), '-vn', '-ac', '1', '-ar', '16000', '-b:a', '48k', str(whole)])
    length = _duration(whole)
    if length > MAX_SECONDS:
        raise TranscribeError('文字起こしは2時間以内の音声に対応しています。')
    if length <= CHUNK_SECONDS * 1.05:          # no tiny last piece for a clip just over the limit
        return [(0.0, whole)]
    pieces, offset = [], 0.0
    while offset < length - 0.5:
        piece = Path(folder) / f'audio-{len(pieces):02d}.mp3'
        _ffmpeg(['-ss', str(offset), '-t', str(CHUNK_SECONDS), '-i', str(whole), '-c', 'copy', str(piece)])
        pieces.append((offset, piece))
        offset += CHUNK_SECONDS
    return pieces


def request_once(path, key, model, lang, opener=urllib.request.urlopen):
    body = {'model': model, 'input_audio': {'data': base64.b64encode(Path(path).read_bytes()).decode(), 'format': 'mp3'},
            'response_format': 'verbose_json', 'timestamp_granularities': ['segment'], 'temperature': 0}
    if lang and lang != 'auto':
        body['language'] = lang
    request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode(),
                                     headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
    with opener(request, timeout=300) as response:
        return json.loads(response.read())


def request(path, key, model, lang, opener=urllib.request.urlopen, wait=5):
    """One request, retried once only for rate limits, server errors and network failures."""
    for attempt in (1, 2):
        try:
            return request_once(path, key, model, lang, opener)
        except urllib.error.HTTPError as error:
            code = error.code
            if code in (429, 500, 502, 503, 504, 524, 529) and attempt == 1:
                time.sleep(wait)
                continue
            hints = {401: 'キーが無効です', 402: 'OpenRouterの残高が不足しています', 403: 'このキーでは使えません',
                     413: '音声が大きすぎます', 429: '利用が混み合っています'}
            raise TranscribeError(f'OpenRouterの文字起こしに失敗しました（HTTP {code}：{hints.get(code, "時間をおいて再試行してください")}）。') from None
        except (urllib.error.URLError, TimeoutError, OSError):
            if attempt == 1:
                time.sleep(wait)
                continue
            raise TranscribeError('OpenRouterに接続できませんでした。') from None
        except ValueError:
            raise TranscribeError('OpenRouterの文字起こし結果を読み取れませんでした。') from None


def segments_from(body, offset):
    out = []
    for s in body.get('segments') or []:
        text = str(s.get('text') or '').strip()
        try:
            begin, finish = float(s['start']), float(s['end'])
        except (KeyError, TypeError, ValueError):
            continue
        if text and finish >= begin:
            out.append({'start': round(begin + offset, 3), 'end': round(finish + offset, 3), 'text': text})
    return out


def transcribe(video, out_dir, lang=None, start=None, end=None, *, key, model, opener=urllib.request.urlopen):
    """Write transcript.json / transcript.txt like CRV's Whisper step. Times are relative
    to `start` (CRV shifts them back onto the source clock afterwards)."""
    if not key:
        raise TranscribeError('OpenRouterのキーがありません。')
    began = time.monotonic()
    segments, cost, seconds = [], 0.0, 0.0
    with tempfile.TemporaryDirectory() as tmp:
        pieces = audio_chunks(video, tmp, start, end)
        for offset, piece in pieces:
            body = request(piece, key, model, lang, opener)
            segments += segments_from(body, offset)
            usage = body.get('usage') or {}
            cost += float(usage.get('cost') or 0)
            seconds += float(usage.get('seconds') or 0)
    record = {'provider': 'openrouter', 'model': model, 'chunks': len(pieces), 'segments': len(segments),
              'audio_seconds': round(seconds, 1), 'cost_usd': round(cost, 6),
              'elapsed_seconds': round(time.monotonic() - began, 1)}
    Path(out_dir, RECORD).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding='utf-8')
    if not segments:
        return None
    Path(out_dir, 'transcript.json').write_text(json.dumps({'segments': segments}, ensure_ascii=False, indent=1), encoding='utf-8')
    target = Path(out_dir, 'transcript.txt')
    target.write_text('\n'.join(s['text'] for s in segments) + '\n', encoding='utf-8')
    return str(target)


def install(core):
    """Replace CRV's local Whisper step when the app asked for it (crv_worker.py).
    The key arrives on stdin, so neither the worker's environment nor the yt-dlp
    and ffmpeg processes it starts ever hold it."""
    if os.environ.get(FLAG_ENV) != '1':
        return []
    import sys
    key = sys.stdin.readline().strip()
    if not key:
        raise TranscribeError('OpenRouterのキーを受け取れませんでした。')
    model = model_from_env()
    from unittest.mock import patch

    def cloud_impl(video, out_dir, lang, model_name='base', start=None, end=None):
        try:
            path = transcribe(video, out_dir, lang, start, end, key=key, model=model)
        except TranscribeError as error:
            print('  ! ' + str(error), flush=True)
            return None
        print(f'  文字起こし：OpenRouter（{model}）', flush=True)
        return path

    # CRV checks for a local Whisper before calling it; the cloud step needs none.
    return [patch.object(core, '_transcribe_impl', cloud_impl),
            patch.object(core, '_whisper_available', lambda: True)]


def summary(evidence_dir):
    path = Path(evidence_dir) / RECORD
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return {k: data.get(k) for k in ('provider', 'model', 'chunks', 'segments', 'audio_seconds', 'cost_usd')}
