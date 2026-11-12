"""Chat mode worker (local addition).

Runs the normal pipeline with the chat assistant as the model, without an API
key and without the web screen.

  chat-jobs/inbox/<id>.json      job placed by the chat assistant
  chat-jobs/status/<id>.json     progress / result of each job
  chat-jobs/worker.json          heartbeat (is the worker running?)
  chat-jobs/cancel/<id>          create this file to stop a job
  runs/chat-bridge.json          the AI request currently waiting for an answer
  完成PDF/                        finished PDFs (and editable Markdown)

Job file fields:
  source        https URL (YouTube / X) or an absolute path to a video file
  purpose       auto | procedure | seminar | training      (default auto)
  detail_level  compact | standard | detailed             (default standard)
  output_language auto | ja | en                          (default ja)
  design, visual_density, presentation_modes, presentation_notes, prompt,
  no_transcribe, external_research                        (optional)
  resume_folder name of a stopped run in runs/ to continue (optional)
  answerer      free text: who answered as the AI (model / effort / conditions) for the test report
  api_rates     [input, output] USD per million tokens for the API-equivalent estimate (default 4, 20)

Each job also gets a test report (runs/<run>/chat-report.json and 完成PDF/<name>_検証レポート.txt):
how the same answers would have fared against the API limits (calls, output caps) and
an API-equivalent size/cost estimate. No API is called.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import traceback
from pathlib import Path

from atomic_io import safe_replace
from manual_client import ManualClient
from pipeline import ROOT, Config, PrototypeError, run

JOBS = ROOT / 'chat-jobs'
INBOX, STATUS, CANCEL_DIR, DONE = JOBS / 'inbox', JOBS / 'status', JOBS / 'cancel', JOBS / 'done'
OUTPUT = ROOT / '完成PDF'
UI_PROMPT = ('動画の内容を正確に読み取り、写真と説明を組み合わせたPDFにまとめて。'
             '重要な部分に詳しい説明を付け、写真を2、3枚横並びにするなど、読みやすく構成して。')
ALLOWED = {
    'purpose': {'auto', 'procedure', 'seminar', 'training'},
    'detail_level': {'compact', 'standard', 'detailed'},
    'output_language': {'auto', 'ja', 'en'},
}
STATE = {'state': 'idle', 'job': None, 'message': ''}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    safe_replace(temporary, path)


def read_json(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {} if default is None else default


def log(message):
    print(time.strftime('%H:%M:%S'), message, flush=True)


def heartbeat_loop(stop):
    while not stop.wait(5):
        try:
            write_json(JOBS / 'worker.json', {'pid': os.getpid(), 'updated_at': time.time(), **STATE})
        except OSError:
            pass


def safe_name(text, limit=60):
    text = re.sub(r'[\\/:*?"<>|\r\n\t]+', ' ', str(text)).strip()
    return (text[:limit].rstrip() or 'document')


def build_config(job, cancel):
    if job.get('resume_folder'):
        previous = read_json(ROOT / 'runs' / job['resume_folder'] / 'run.json')
        if not previous:
            raise PrototypeError('再開する生成が見つかりません。')
        if not previous.get('manual_mode'):
            raise PrototypeError('API生成の記録はチャットモードで再開できません。')
        source = previous['source']
        prompt = previous.get('request_prompt', previous['prompt'])
        settings = previous
        resume = True
    else:
        source = str(job.get('source', '')).strip()
        if not source:
            raise PrototypeError('動画のURLまたはファイルパスがありません。')
        if not source.startswith('https://') and not Path(source).is_file():
            raise PrototypeError(f'動画ファイルが見つかりません: {source}')
        prompt = job.get('prompt') or UI_PROMPT
        settings = job
        resume = False
    for key, allowed in ALLOWED.items():
        value = settings.get(key)
        if value is not None and value not in allowed:
            raise PrototypeError(f'{key} の値が正しくありません: {value}')
    config = Config(
        model=settings.get('model', 'chat-bridge'), effort=settings.get('effort', 'auto'), model_options=None,
        no_transcribe=bool(settings.get('no_transcribe')),
        external_research=bool(settings.get('external_research', False)),
        cancel_event=cancel, resume=resume,
        purpose=settings.get('purpose') or 'auto',
        detail_level=settings.get('detail_level') or 'standard',
        output_language=settings.get('output_language') or 'ja',
        design=settings.get('design') or 'editorial',
        visual_density=settings.get('visual_density') or 'auto',
        presentation_modes=tuple(settings.get('presentation_modes') or ()),
        presentation_notes=settings.get('presentation_notes') or '')
    return source, prompt, config


def publish(folder, job_id):
    """Copy the finished PDF/Markdown to 完成PDF with a readable name."""
    pdf = folder / 'document.pdf'
    if not pdf.is_file():
        return None
    title = read_json(folder / 'document.json').get('title') or job_id
    stem = time.strftime('%Y%m%d-%H%M') + '_' + safe_name(title)
    OUTPUT.mkdir(exist_ok=True)
    target = OUTPUT / (stem + '.pdf')
    shutil.copy2(pdf, target)
    if (folder / 'document.md').is_file():
        shutil.copy2(folder / 'document.md', OUTPUT / (stem + '.md'))
    return target


# Same per-request output caps and call limit the API path enforces (usage_guard / pipeline.Config).
API_OUTPUT_CAPS = {'analyze': 49152, 'verify': 16384, 'document': 65536}
PHASE_NAMES = {'analyze': '分析', 'document': '資料作成', 'verify': '照合'}


def build_test_report(folder, job, state, error=None):
    """Summarise a chat-mode run in API terms. Read-only: never changes the run."""
    run_info = read_json(folder / 'run.json')
    exchanges = read_json(folder / 'manual-exchanges.json', [])
    events = read_json(folder / 'quality-events.json', [])
    exchanges = exchanges if isinstance(exchanges, list) else []
    events = events if isinstance(events, list) else []
    try:
        rates = [float(v) for v in (job.get('api_rates') or (4, 20))][:2]
    except (TypeError, ValueError):
        rates = [4.0, 20.0]
    call_limit = int(run_info.get('max_api_calls') or 12)
    requests, total_in, total_out, format_rejections, over_cap = [], 0, 0, 0, []
    for item in exchanges:
        cap = API_OUTPUT_CAPS.get(item.get('phase'), 65536)
        tin, tout = item.get('input_tokens_estimate') or 0, item.get('output_tokens_estimate') or 0
        total_in, total_out = total_in + tin, total_out + tout
        format_rejections += item.get('format_rejections') or 0
        if tout > cap:
            over_cap.append(item.get('sequence'))
        requests.append({'sequence': item.get('sequence'), 'phase': item.get('phase'),
                         'answered_with': item.get('answered_with'), 'input_tokens_estimate': tin,
                         'output_tokens_estimate': tout, 'api_output_cap': cap,
                         'format_rejections': item.get('format_rejections') or 0,
                         'answer_seconds': item.get('answer_seconds')})
    rejections = [{'phase': e.get('phase'), 'tool': e.get('tool'), 'error': str(e.get('error', ''))[:300]}
                  for e in events if isinstance(e, dict) and e.get('error')]
    # A broken answer costs the API path one extra call (its single format repair).
    api_calls = len(exchanges) + format_rejections
    warnings = []
    if api_calls > call_limit:
        warnings.append(f'APIでは呼び出し回数の上限（{call_limit}回）で止まっていた可能性があります（今回 {api_calls}回相当）。')
    if over_cap:
        warnings.append(f'回答が1回の出力上限を超えています（依頼 {over_cap}）。APIでは途切れて停止します。')
    if format_rejections:
        warnings.append(f'形式の不備で受け付けられなかった回答が {format_rejections}件あります。APIでは修正1回分の呼び出しになります。')
    report = {
        'answerer': str(job.get('answerer') or '未記入'), 'state': state, 'error': error,
        'source': run_info.get('source') or job.get('source'),
        'conditions': {k: run_info.get(k, job.get(k)) for k in (
            'purpose', 'detail_level', 'output_language', 'design', 'visual_density', 'external_research')},
        'ai_requests': len(exchanges), 'api_call_equivalent': api_calls, 'api_call_limit': call_limit,
        'format_rejections': format_rejections, 'content_rejections': rejections,
        'revisions': run_info.get('revisions'), 'layout_failures': run_info.get('layout_failures'),
        'content_verified': run_info.get('content_verified'), 'seconds': run_info.get('seconds'),
        'input_tokens_estimate': total_in, 'output_tokens_estimate': total_out,
        'api_rates_usd_per_million': rates,
        'api_cost_estimate_usd': round((total_in * rates[0] + total_out * rates[1]) / 1e6, 2),
        'estimate_note': '回答の分量だけの目安。APIでは考える過程の出力も課金・上限の対象になるため、実際はこれより多くなります。',
        'warnings': warnings, 'requests': requests,
    }
    return report


def report_text(report, pdf_name=None):
    c = report['conditions']
    lines = ['検証レポート（チャットモード。APIは呼び出していません）', '',
             f"回答したAI：{report['answerer']}",
             f"結果：{report['state']}" + (f"（{report['error']}）" if report.get('error') else ''),
             f"PDF：{pdf_name or 'なし'}",
             f"動画：{report.get('source')}",
             f"条件：用途 {c.get('purpose')}／詳しさ {c.get('detail_level')}／言語 {c.get('output_language')}／"
             f"デザイン {c.get('design')}／外部検索 {'オン' if c.get('external_research') else 'オフ'}", '',
             f"AIへの依頼：{report['ai_requests']}回（API換算 {report['api_call_equivalent']}回、APIの上限 {report['api_call_limit']}回）",
             f"形式の不備で受け付けられなかった回答：{report['format_rejections']}件",
             f"アプリの検査で差し戻された提出：{len(report['content_rejections'])}件",
             f"紙面を作った回数：{report.get('revisions')}回（2回以上は作り直しあり）／紙面検査の不合格：{report.get('layout_failures')}回",
             f"API換算の分量：入力 約{report['input_tokens_estimate']:,}トークン／出力 約{report['output_tokens_estimate']:,}トークン",
             f"API換算の費用の目安：約${report['api_cost_estimate_usd']}"
             f"（入力${report['api_rates_usd_per_million'][0]}・出力${report['api_rates_usd_per_million'][1]}／100万トークンで計算）",
             f"　※{report['estimate_note']}", '']
    lines.append('APIだった場合の注意：' + ('なし' if not report['warnings'] else ''))
    lines += [f'- {w}' for w in report['warnings']]
    lines += ['', '依頼ごとの内訳：']
    for r in report['requests']:
        lines.append(f"- {r['sequence']}回目（{PHASE_NAMES.get(r['phase'], r['phase'])}）：{'・'.join(r.get('answered_with') or [])}"
                     f"／入力 約{r['input_tokens_estimate']:,}／出力 約{r['output_tokens_estimate']:,}"
                     f"（上限 {r['api_output_cap']:,}）／形式の不備 {r['format_rejections']}件／{r.get('answer_seconds')}秒")
    if report['content_rejections']:
        lines += ['', '差し戻しの理由：']
        lines += [f"- {PHASE_NAMES.get(e['phase'], e['phase'])}・{e['tool']}：{e['error']}" for e in report['content_rejections']]
    return '\n'.join(lines) + '\n'


def save_report(folder, job, status, target=None):
    """Best effort: the report must never turn a finished job into a failure."""
    try:
        report = build_test_report(folder, job, status.get('state'), status.get('error'))
        write_json(folder / 'chat-report.json', report)
        text = report_text(report, target.name if target else None)
        (folder / 'chat-report.txt').write_text(text, encoding='utf-8')
        if target:
            (target.parent / (target.stem + '_検証レポート.txt')).write_text(text, encoding='utf-8')
            status['report_file'] = str(target.parent / (target.stem + '_検証レポート.txt'))
        status['report'] = {k: report[k] for k in ('answerer', 'ai_requests', 'api_call_equivalent', 'format_rejections',
                                                   'api_cost_estimate_usd', 'warnings')}
        status['report']['content_rejections'] = len(report['content_rejections'])
    except Exception as error:  # noqa: BLE001
        log(f'検証レポートを作成できませんでした: {error}')


def process(path):
    job_id = path.stem
    job = read_json(path)
    DONE.mkdir(parents=True, exist_ok=True)
    shutil.move(str(path), str(DONE / path.name))
    status_path = STATUS / f'{job_id}.json'
    status = {'id': job_id, 'state': 'running', 'message': '準備しています', 'started_at': time.time(),
              'updated_at': time.time(), 'job': job}
    cancel = threading.Event()

    def update(message):
        status.update(message=message, updated_at=time.time())
        STATE['message'] = message
        log(message)
        if (CANCEL_DIR / job_id).exists():
            cancel.set()
        try:
            write_json(status_path, status)
        except OSError:
            pass

    STATE.update(state='busy', job=job_id)
    try:
        source, prompt, config = build_config(job, cancel)
        folder_name = job.get('resume_folder') or time.strftime('%Y%m%d-%H%M%S') + '-' + os.urandom(3).hex()
        run_dir = ROOT / 'runs' / folder_name
        status['run_folder'] = folder_name
        update(f'開始: {source}')
        client = ManualClient(run_dir, cancel, notify=update)

        def watch_cancel():
            while not cancel.wait(1):
                if (CANCEL_DIR / job_id).exists():
                    cancel.set()
        threading.Thread(target=watch_cancel, daemon=True).start()
        folder = run(source, config=config, prompt=prompt, notify=update, run_dir=run_dir, client=client)
        report = read_json(folder / 'run.json')
        target = publish(folder, job_id)
        status.update(state=report.get('status', 'complete'), pdf=str(target) if target else None,
                      run_pdf=f'runs/{folder_name}/document.pdf', finished_at=time.time())
        save_report(folder, job, status, target)
        update('PDFが完成しました' if report.get('status') == 'complete' else
               'PDFを作成しました（内容の確認が必要な箇所があります）')
    except Exception as error:  # noqa: BLE001 - every failure must be reported to the chat
        status.update(state='failed', error=str(error)[:3000], finished_at=time.time(),
                      traceback=traceback.format_exc()[-3000:])
        if status.get('run_folder') and (ROOT / 'runs' / status['run_folder']).is_dir():
            save_report(ROOT / 'runs' / status['run_folder'], job, status)
        update(f'停止しました: {error}')
    finally:
        cancel.set()
        STATE.update(state='idle', job=None)


def main():
    for directory in (INBOX, STATUS, CANCEL_DIR, DONE, OUTPUT):
        directory.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    threading.Thread(target=heartbeat_loop, args=(stop,), daemon=True).start()
    write_json(JOBS / 'worker.json', {'pid': os.getpid(), 'updated_at': time.time(), **STATE})
    log('チャットモードの受付を開始しました。このウィンドウは開いたままにしてください。')
    try:
        while True:
            jobs = sorted((p for p in INBOX.glob('*.json') if time.time() - p.stat().st_mtime > 1),
                          key=lambda p: p.stat().st_mtime)
            if jobs:
                process(jobs[0])
            else:
                time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        STATE.update(state='stopped')
        write_json(JOBS / 'worker.json', {'pid': os.getpid(), 'updated_at': time.time(), **STATE})


if __name__ == '__main__':
    main()
