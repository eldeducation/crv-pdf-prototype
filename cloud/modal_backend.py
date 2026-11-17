"""Private, scale-to-zero video preparation for the existing Render app."""
from pathlib import Path
import modal

ROOT = Path(__file__).resolve().parent
APP_NAME = 'crv-pdf-extraction'
app = modal.App(APP_NAME, include_source=False)
volume = modal.Volume.from_name('crv-pdf-evidence-v1', create_if_missing=True, version=2)
ledger = modal.Dict.from_name('crv-pdf-extraction-ledger-v1', create_if_missing=True)
image = (modal.Image.debian_slim(python_version='3.12')
         .apt_install('ffmpeg')
         .pip_install('torch', index_url='https://download.pytorch.org/whl/cpu')
         .pip_install('claude-real-video[whisper]==0.10.7', 'Pillow==12.3.0',
                      'openai-whisper==20250625', 'fastapi==0.135.1')
         .env({'PYTHONIOENCODING': 'utf-8', 'PYTHONUNBUFFERED': '1',
               'CRV_NO_MEMORY': '1', 'OMP_NUM_THREADS': '1', 'XDG_CACHE_HOME': '/opt/cache'})
         .run_commands("python -c \"import whisper; whisper._download(whisper._MODELS['base'], '/opt/cache/whisper', False)\""))
if modal.is_local():
    image = image.add_local_file(ROOT / 'install_ffmpeg9.py', '/tmp/install_ffmpeg9.py', copy=True)
    image = image.run_commands('python /tmp/install_ffmpeg9.py')
    for name in ('modal_backend.py', 'modal_worker.py', 'balanced_select.py'):
        image = image.add_local_file(ROOT / name, '/root/' + name)
    image = image.add_local_file(ROOT.parent / 'modal_contract.py', '/root/modal_contract.py')


def job_path(job):
    from modal_contract import valid_id
    if not valid_id(job):
        raise ValueError('処理の識別子が不正です。')
    return Path('/data/jobs') / job


def reserve(kind, job):
    from datetime import datetime, timezone
    from modal_contract import PREPARE_JOBS_PER_MONTH, DETAIL_JOBS_PER_MONTH
    month = datetime.now(timezone.utc).strftime('%Y-%m')
    count = PREPARE_JOBS_PER_MONTH if kind == 'prepare' else DETAIL_JOBS_PER_MONTH
    for slot in range(count):
        key = f'{month}:{kind}:{slot}'
        previous = ledger.get(key, None)
        if previous == job:
            return
        if previous is None and ledger.put(key, job, skip_if_exists=True):
            return
    raise ValueError('無料検証の月間処理枠に達しました。画質を下げずに停止しました。管理者に確認してください。')


# Whisper base on 2 CPU cores runs at about the video's length: a 30-minute video needs
# up to ~45 minutes in total, so the limits allow that instead of cutting the transcript.
@app.function(image=image, cpu=(2, 2), memory=(4096, 4096), timeout=3000,
              max_containers=1, retries=0, volumes={'/data': volume},
              include_source=False, block_network=True)
def process(job):
    import hashlib
    import json
    import os
    import re
    import shutil
    import subprocess
    import sys
    import tempfile
    import threading
    import time
    import zipfile
    from PIL import Image
    from modal_contract import MAX_VIDEO_SECONDS, VERSION

    volume.reload()
    record = ledger[job]
    folder = job_path(job)
    parent_record = ledger[record['parent']] if record.get('parent') else record
    source = job_path(record.get('parent', job)) / ('source' + parent_record['extension'])
    began = time.monotonic()
    stopped = None
    watcher = None
    record.update(status='running', phase='frames')
    ledger[job] = record
    try:
        metadata = json.loads(subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format',
                                              '-of', 'json', str(source)], capture_output=True,
                                             text=True, check=True, timeout=30).stdout)
        duration = float(metadata['format']['duration'])
        if not 0 < duration <= MAX_VIDEO_SECONDS:
            raise ValueError('動画は既存の試作品と同じ30分以内が対象です。')
        with tempfile.TemporaryDirectory() as temporary:
            temporary = Path(temporary)
            log = temporary / 'extraction.log'
            samples = []
            stopped = threading.Event()
            def sample():
                last = None
                while not stopped.wait(1):
                    try:
                        samples.append(int(Path('/sys/fs/cgroup/memory.current').read_text()))
                    except (OSError, ValueError):
                        pass
                    if log.is_file():
                        with log.open('rb') as handle:
                            handle.seek(max(0, log.stat().st_size - 8192))
                            tail = handle.read().decode('utf-8', 'replace')
                        phases = re.findall(r'@@crv-progress (\w+)', tail)
                        phase = phases[-1] if phases else None
                        if phase and phase != last:
                            record['phase'] = phase
                            ledger[job] = record
                            last = phase
            watcher = threading.Thread(target=sample, daemon=True)
            watcher.start()
            if record['kind'] == 'prepare':
                options = record['options']
                evidence = temporary / 'crv'
                command = [sys.executable, '/root/modal_worker.py', str(source), '-o', str(evidence),
                           '--grid', '--frame-width', str(options['frame_width']),
                           '--max-frames', str(options['max_frames']), '--why',
                           '手順書というよりは動画の内容をうまくPDFにまとめて。単調な流れではなく、情報に濃淡をつけて。写真を2、3枚横並びにおくなど。']
                if options['profile'] == 'adaptive':
                    command.append('--adaptive')
                if options['no_transcribe']:
                    command.append('--no-transcribe')
                env = {key: value for key, value in os.environ.items()
                       if key in ('PATH', 'HOME', 'LANG', 'PYTHONIOENCODING', 'PYTHONUNBUFFERED',
                                  'OMP_NUM_THREADS', 'XDG_CACHE_HOME')}
                env.update(CRV_NO_MEMORY='1', CRV_MEMORY_DB=str(temporary / 'memory.db'))
                if record.get('transcript') is not None:
                    provided = temporary / 'provided-transcript.json'
                    provided.write_text(json.dumps(record['transcript'], ensure_ascii=False), encoding='utf-8')
                    env['CRV_PROVIDED_TRANSCRIPT'] = str(provided)
                with log.open('w', encoding='utf-8') as output:
                    completed = subprocess.run(command, env=env, stdout=output,
                                               stderr=subprocess.STDOUT, timeout=2820)
                if completed.returncode:
                    raise ValueError('抽出処理が停止しました。画質や画像枚数を下げての再試行はしていません。')
                frames = sorted((evidence / 'frames').glob('*.jpg'))
                if not frames:
                    raise ValueError('抽出画像を確認できませんでした。')
                images = []
                for path in frames:
                    with Image.open(path) as im:
                        images.append({'file': 'frames/' + path.name, 'width': im.width, 'height': im.height,
                                       'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
                report = {'version': VERSION, 'source_sha256': record['sha256'], 'options': options,
                          'frame_count': len(frames), 'images': images, 'evidence_path': str(evidence)}
            else:
                from modal_contract import validate_detail
                spec = validate_detail(record['spec'], duration)
                if spec['kind'] == 'frame':
                    command = ['ffmpeg', '-v', 'error', '-ss', str(spec['seconds']), '-i', str(source),
                               '-frames:v', '1', '-vf', 'scale=1920:-2', '-y', str(temporary / 'detail.jpg')]
                else:
                    start, end, fps, width, count, video_start = (spec[k] for k in
                            ('start', 'end', 'fps', 'width', 'count', 'video_start'))
                    suffix = '.png' if spec['format'] == 'png' else '.jpg'
                    filtering = (f"select='lt(t,{end+video_start:.9f})*"
                                 f"(isnan(prev_selected_t)+gte(t-prev_selected_t,{1/fps-1e-7:.9f}))',"
                                 f'scale={int(width)}:-2,showinfo')
                    command = ['ffmpeg', '-hide_banner', '-loglevel', 'info', '-ss', str(start), '-copyts',
                               '-i', str(source), '-vf', filtering, '-frames:v', str(int(count)),
                               '-fps_mode', 'vfr', '-q:v', '2', '-y', str(temporary / ('frame_%03d' + suffix))]
                result = subprocess.run(command, capture_output=True, text=True, timeout=120)
                log.write_text(result.stdout + result.stderr, encoding='utf-8')
                if result.returncode:
                    raise ValueError('追加画像の抽出に失敗しました。既存の画像で代用せず停止しました。')
                report = {'version': VERSION, 'parent': record['parent'], 'spec': spec,
                          'ffmpeg_output': result.stdout + result.stderr,
                          'files': sorted(path.name for path in temporary.glob('frame_*'))}
            stopped.set()
            watcher.join(timeout=2)
            report.update(worker_seconds=round(time.monotonic()-began, 3),
                          sampled_container_peak_bytes=max(samples, default=None), ai_api_calls=0,
                          ffmpeg=subprocess.run(['ffmpeg', '-version'], capture_output=True,
                                                text=True, check=True).stdout.splitlines()[0])
            (temporary / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            record['phase'] = 'pack'
            ledger[job] = record
            folder.mkdir(parents=True, exist_ok=True)
            partial = folder / 'result.zip.partial'
            with zipfile.ZipFile(partial, 'w', zipfile.ZIP_DEFLATED) as bundle:
                for path in sorted(temporary.rglob('*')):
                    if path.is_file() and path.suffix.lower() not in ('.mp4', '.mov', '.mkv', '.webm', '.m4v', '.wav', '.mp3', '.pt'):
                        bundle.write(path, path.relative_to(temporary).as_posix())
            partial.replace(folder / 'result.zip')
            record.update(status='complete', phase='complete', duration=duration,
                          worker_seconds=report['worker_seconds'], frame_count=report.get('frame_count'))
            ledger[job] = record
            volume.commit()
    except Exception as error:
        message = str(error) if isinstance(error, ValueError) else '抽出処理が停止しました。追加の実行は自動で行っていません。'
        record.update(status='failed', message=message[:300])
        ledger[job] = record
        print('Modal extraction failed: ' + type(error).__name__, flush=True)
    finally:
        if stopped is not None:
            stopped.set()
        if watcher is not None:
            watcher.join(timeout=2)


def make_api():
    import hashlib
    import json
    import time
    import uuid
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import FileResponse
    from modal_contract import (VERSION, MAX_VIDEO_BYTES, MAX_RESULT_BYTES, PREPARE_JOBS_PER_MONTH, identity,
                                detail_identity, valid_id, validate_options, validate_detail)

    web = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def get_job(job):
        if not valid_id(job):
            raise HTTPException(400, '処理の識別子が不正です。')
        value = ledger.get(job, None)
        if not value:
            raise HTTPException(404, '処理が見つかりません。')
        return value

    def public(record):
        return {key: record.get(key) for key in ('id', 'status', 'phase', 'message', 'frame_count', 'worker_seconds')}

    async def json_body(request, limit=2*1024**2):
        data = bytearray()
        async for chunk in request.stream():
            data.extend(chunk)
            if len(data) > limit:
                raise HTTPException(413, '処理の設定が大きすぎます。')
        try:
            return json.loads(data)
        except ValueError:
            raise HTTPException(400, '処理の設定が不正です。')

    @web.get('/health')
    def health():
        return {'version': VERSION, 'status': 'ok', 'max_video_bytes': MAX_VIDEO_BYTES,
                'prepare_jobs_per_month': PREPARE_JOBS_PER_MONTH, 'provider_keys_required': False}

    @web.post('/jobs')
    async def create(request: Request):
        data = await json_body(request, 16384)
        try:
            options = validate_options(data['options'])
            job = identity(data['sha256'], options)
            if data['id'] != job or type(data['bytes']) is not int or not 0 < data['bytes'] <= MAX_VIDEO_BYTES:
                raise ValueError('動画の検証情報が不正です。')
            if data['extension'] not in ('.mp4', '.webm', '.mkv', '.mov', '.m4v'):
                raise ValueError('動画の形式が対応外です。')
        except (ValueError, KeyError) as error:
            raise HTTPException(400, str(error))
        record = {'id': job, 'kind': 'prepare', 'status': 'awaiting_upload', 'phase': 'upload',
                  'sha256': data['sha256'], 'bytes': data['bytes'], 'extension': data['extension'],
                  'options': options}
        if ledger.put(job, record, skip_if_exists=True):
            try:
                reserve('prepare', job)  # reserve before accepting a large file
            except ValueError as error:
                ledger.pop(job, None)
                raise HTTPException(429, str(error))
        return public(ledger[job])

    @web.put('/jobs/{job}/source')
    async def upload(job: str, request: Request):
        record = get_job(job)
        if record['kind'] != 'prepare':
            raise HTTPException(400, '動画の送信先が不正です。')
        if record['status'] != 'awaiting_upload':
            return public(record)
        if request.headers.get('content-length') != str(record['bytes']):
            raise HTTPException(400, '動画のサイズが一致しません。')
        lock = 'upload:' + job
        lock_time = ledger.get(lock, None)
        if lock_time is not None and time.time() - lock_time > 180:
            ledger.pop(lock, None)  # longer than the platform's 150s request timeout
        if not ledger.put(lock, time.time(), skip_if_exists=True):
            raise HTTPException(409, '動画を送信中です。処理を重複して開始しません。')
        folder = job_path(job)
        folder.mkdir(parents=True, exist_ok=True)
        partial = folder / ('upload-' + uuid.uuid4().hex + '.partial')
        digest, total = hashlib.sha256(), 0
        try:
            with partial.open('wb') as output:
                async for chunk in request.stream():
                    total += len(chunk)
                    if total > record['bytes']:
                        raise HTTPException(413, '動画の送信サイズが上限を超えました。')
                    digest.update(chunk)
                    output.write(chunk)
            if total != record['bytes'] or digest.hexdigest() != record['sha256']:
                raise HTTPException(400, '動画の送信時の検証に失敗しました。')
            partial.replace(folder / ('source' + record['extension']))
            volume.commit()
            record['status'] = 'uploaded'
            ledger[job] = record
            return public(record)
        finally:
            if partial.exists():
                partial.unlink()
            ledger.pop(lock, None)

    def start(record, transcript=None):
        job = record['id']
        if record['status'] in ('complete', 'running', 'queued', 'failed', 'cancelled'):
            return public(record)
        if record['status'] != 'uploaded':
            raise HTTPException(409, '動画の送信が完了していません。')
        if record.get('options', {}).get('stt_model') and not isinstance(transcript, dict):
            raise HTTPException(400, '抽出に必要な文字起こし情報がありません。別の方式で代用せず停止しました。')
        if not ledger.put('start:' + job, time.time(), skip_if_exists=True):
            return public(ledger[job])
        try:
            reserve(record['kind'], job)
            record.update(status='queued', phase='queued')
            if transcript is not None:
                record['transcript'] = transcript
            ledger[job] = record
            call = process.spawn(job)
            # Store the call separately: worker progress updates must not race
            # with, and erase, the cancellation/OOM-detection handle.
            ledger['call:' + job] = call.object_id
            return public(ledger[job])
        except ValueError as error:
            record.update(status='failed', message=str(error))
            ledger[job] = record
            raise HTTPException(429, str(error))

    @web.post('/jobs/{job}/start')
    async def launch(job: str, request: Request):
        data = await json_body(request)
        transcript = data.get('transcript')
        if transcript is not None and (not isinstance(transcript, dict) or any(
                key not in ('transcript.json', 'transcript.txt', 'cloud-transcribe.json', 'source_subtitles')
                for key in transcript)):
            raise HTTPException(400, '抽出に必要な文字起こし情報が不正です。')
        return start(get_job(job), transcript)

    @web.post('/jobs/{parent}/details')
    async def details(parent: str, request: Request):
        original = get_job(parent)
        if original['status'] != 'complete' or original['kind'] != 'prepare':
            raise HTTPException(409, '動画の初期抽出が完了していません。')
        data = await json_body(request, 16384)
        try:
            spec = validate_detail(data['spec'], original['duration'])
            job = detail_identity(parent, spec)
            if data['id'] != job:
                raise ValueError('追加画像の識別子が不正です。')
        except (ValueError, KeyError) as error:
            raise HTTPException(400, str(error))
        record = {'id': job, 'kind': 'detail', 'parent': parent, 'status': 'uploaded', 'phase': 'queued', 'spec': spec}
        ledger.put(job, record, skip_if_exists=True)
        return start(ledger[job])

    @web.get('/jobs/{job}')
    def status(job: str):
        record = get_job(job)
        # Failed/OOM/cancelled workers must not leave a permanently running job.
        call_id = ledger.get('call:' + job, None)
        if record['status'] in ('queued', 'running') and call_id:
            try:
                modal.FunctionCall.from_id(call_id).get(timeout=0)
            except TimeoutError:
                pass
            except Exception:
                record.update(status='failed', message='抽出処理が停止しました。自動で再実行していません。')
                ledger[job] = record
        return public(ledger[job])

    @web.get('/jobs/{job}/result')
    def result(job: str):
        record = get_job(job)
        if record['status'] != 'complete':
            raise HTTPException(409, '抽出処理はまだ完了していません。')
        volume.reload()
        path = job_path(job) / 'result.zip'
        if not path.is_file() or path.stat().st_size > MAX_RESULT_BYTES:
            raise HTTPException(409, '抽出結果を確認できませんでした。')
        return FileResponse(path, media_type='application/zip', filename='evidence.zip')

    @web.post('/jobs/{job}/cancel')
    def cancel(job: str):
        record = get_job(job)
        if record['status'] not in ('complete', 'failed', 'cancelled'):
            call_id = ledger.get('call:' + job, None)
            if call_id:
                modal.FunctionCall.from_id(call_id).cancel(terminate_containers=True)
            record.update(status='cancelled', message='処理を停止しました。')
            ledger[job] = record
        return public(record)

    return web


@app.function(image=image, cpu=(0.125, 0.5), memory=(256, 512), timeout=150,
              max_containers=1, scaledown_window=5, volumes={'/data': volume}, include_source=False)
@modal.asgi_app(requires_proxy_auth=True)
def api():
    return make_api()
