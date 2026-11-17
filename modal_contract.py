"""Versioned, provider-key-free extraction requests shared by Render and Modal."""
import hashlib
import json
import math
import re

VERSION = 'crv-modal-20261117-v1'
MAX_VIDEO_BYTES = 200 * 1024**2  # same limit as the existing shared Render UI
MAX_VIDEO_SECONDS = 1800       # same content limit as Evidence
MAX_RESULT_BYTES = 64 * 1024**2
MAX_UNPACKED_BYTES = 160 * 1024**2
PREPARE_JOBS_PER_MONTH = 3
DETAIL_JOBS_PER_MONTH = 36
PROFILES = ('windows-compatible', 'adaptive')


def validate_options(options):
    if not isinstance(options, dict):
        raise ValueError('抽出設定が不正です。')
    if options.get('version') != VERSION:
        raise ValueError('画像抽出の接続バージョンが一致しません。')
    if type(options.get('frame_width')) is not int or options['frame_width'] not in (640, 1280):
        raise ValueError('画像の横幅は640または1280pxです。')
    if type(options.get('max_frames')) is not int or not 1 <= options['max_frames'] <= 600:
        raise ValueError('画像枚数の指定が不正です。')
    if type(options.get('no_transcribe')) is not bool:
        raise ValueError('文字起こしの指定が不正です。')
    if options.get('profile') not in PROFILES:
        raise ValueError('抽出方式の指定が不正です。')
    if options.get('stt_model') is not None and options['stt_model'] not in (
            'openai/whisper-large-v3', 'openai/whisper-large-v3-turbo', 'openai/whisper-1'):
        raise ValueError('文字起こしモデルの指定が不正です。')
    return dict(options)


def identity(source_sha256, options):
    if not isinstance(source_sha256, str) or not re.fullmatch('[a-f0-9]{64}', source_sha256):
        raise ValueError('動画の検証情報が不正です。')
    validate_options(options)
    return hashlib.sha256(json.dumps([source_sha256, options], sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()[:32]


def valid_id(value):
    return isinstance(value, str) and bool(re.fullmatch('[a-f0-9]{32}', value))


def detail_identity(parent, spec):
    if not valid_id(parent):
        raise ValueError('元動画の識別子が不正です。')
    return hashlib.sha256(json.dumps([VERSION, parent, spec], sort_keys=True,
                                     separators=(',', ':')).encode()).hexdigest()[:32]


def validate_detail(spec, duration):
    if not isinstance(spec, dict) or spec.get('kind') not in ('frame', 'interval'):
        raise ValueError('追加画像の指定が不正です。')
    if spec['kind'] == 'frame':
        sec = spec.get('seconds')
        if type(sec) not in (int, float) or not math.isfinite(sec) or not 0 <= sec < duration:
            raise ValueError('追加画像の時刻が動画の範囲外です。')
    else:
        values = [spec.get(k) for k in ('start', 'end', 'fps', 'width', 'count', 'video_start')]
        if not all(type(x) in (int, float) and math.isfinite(x) for x in values):
            raise ValueError('区間の指定が不正です。')
        start, end, fps, width, count, _ = values
        if not 0 <= start < end <= duration or end-start > 60 or not 0.01 <= fps <= 4:
            raise ValueError('区間の指定が動画の範囲外です。')
        if int(width) != width or not 640 <= width <= 1920 or int(count) != count or not 1 <= count <= 24:
            raise ValueError('区間画像の解像度または枚数が不正です。')
        if spec.get('format') not in ('jpeg', 'png'):
            raise ValueError('区間画像の形式が不正です。')
    return dict(spec)
