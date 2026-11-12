"""Recorded stage progress and conservative, credential-free resume guidance."""
import json
import time
from pathlib import Path
from atomic_io import safe_replace

STAGES = ('prepare', 'analyze', 'document', 'verify', 'finish')
# Default phase bounds: analysis 8, editing 7, up to two review sessions of 8,
# plus one format-repair reserve. Successful runs do not consume unused slots.
DEFAULT_MAX_API_CALLS = 8 + 7 + 2 * 8 + 1


def read(path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return {} if default is None else default


class Progress:
    def __init__(self, folder, resume=False, clock=None):
        self.folder = Path(folder)
        self.clock = clock or time.time
        old = read(self.folder / 'progress.json') if resume else {}
        self.data = old if old.get('version') == 1 else {
            'version': 1, 'current': None, 'status': 'running',
            'stages': {stage: {'state': 'pending'} for stage in STAGES},
            'created_at': self.clock(),
        }
        self.data['status'] = 'running'
        self.data.pop('stop_code', None)
        self.save()

    def save(self):
        self.data['updated_at'] = self.clock()
        temporary = self.folder / 'progress.tmp'
        temporary.write_text(json.dumps(self.data, ensure_ascii=False), encoding='utf-8')
        safe_replace(temporary, self.folder / 'progress.json')

    def start(self, stage, *, restart=False):
        if stage not in STAGES:
            raise ValueError('Unknown progress stage.')
        if restart:
            for later in STAGES[STAGES.index(stage)+1:]:
                self.data['stages'][later] = {'state': 'pending'}
        self.data['current'] = stage
        self.data['stages'][stage] = {'state': 'running', 'started_at': self.clock()}
        self.save()

    def complete(self, stage):
        self.data['stages'][stage].update(state='complete', completed_at=self.clock())
        self.save()

    def touch(self):
        self.save()

    def stop(self, code):
        self.data.update(status='stopped', stop_code=code)
        if self.data['current']:
            current = self.data['stages'][self.data['current']]
            if current['state'] != 'complete':
                current['state'] = 'stopped'
        self.save()

    def finish(self):
        self.data.update(status='complete', current=None)
        self.save()


def stop_code(error):
    code = getattr(error, 'code', None)
    if code:
        return code
    message = str(error)
    for text, reason in (('再作成の上限', 'revision_limit'), ('紙面修正の上限', 'revision_limit'),
                         ('AI処理の回数上限', 'round_limit'), ('API呼び出し回数の上限', 'call_limit'),
                         ('トークン上限', 'token_limit'), ('次の処理を含めると費用目安', 'budget'),
                         ('前回の料金が未確定', 'billing_pending')):
        if text in message:
            return reason
    # A local tool that ran past its limit (Python's "Command [...] timed out
    # after N seconds") is not an API network problem.
    if message.startswith("Command '") and 'timed out after' in message:
        return 'prepare_timeout' if 'crv_worker' in message else 'error'
    if 'HTTP 401' in message or 'HTTP 403' in message:
        return 'auth'
    if 'HTTP 402' in message:
        return 'credit'
    if 'HTTP 429' in message:
        return 'rate_limit'
    if '出力上限' in message or '（length）' in message:
        return 'output_limit'
    if 'JSON' in message or 'ツール出力が不正' in message:
        return 'response_format'
    if '接続できません' in message or 'timed out' in message or 'Timeout' in message:
        return 'network'
    if '確認できない箇所' in message or '確認が必要な指摘' in message or '食い違い' in message:
        return 'quality'
    return 'error'


def describe(folder, job, fingerprint=None):
    folder = Path(folder)
    report = job.get('report') or read(folder / 'run.json')
    recorded = read(folder / 'progress.json')
    usage = read(folder / 'usage.json')
    status = job.get('status', 'failed')
    current = recorded.get('current') if recorded.get('current') in STAGES else None
    stages = [{'id': name, **recorded.get('stages', {}).get(name, {'state': 'pending'})} for name in STAGES]
    reason = report.get('stop_code') or recorded.get('stop_code')
    if not reason and status in {'failed', 'needs_review'}:
        reason = stop_code(RuntimeError(report.get('review_note') or report.get('error') or job.get('message', '')))
    finished = sum(stage['state'] == 'complete' for stage in stages)
    updated = max(float(recorded.get('updated_at') or 0), float(job.get('updated_at') or 0))
    if (folder / 'usage.json').exists():
        updated = max(updated, (folder / 'usage.json').stat().st_mtime)
    pending = usage.get('pending')
    api_started = pending.get('started_at') if isinstance(pending, dict) and status == 'running' else None
    stopped = status in {'failed', 'needs_review'}
    if stopped:
        for stage in stages:
            if stage['id'] == current and stage['state'] == 'running':
                stage['state'] = 'stopped'
    resume = {'available': False, 'from_stage': None, 'reason': None, 'saved_checkpoint': False}
    if stopped:
        states = {name: read(folder / ('checkpoint-' + name + '.state.json'))
                  for name in ('content_plan', 'editor', 'document_content_review')}
        has_plan = bool(states['content_plan'].get('completed'))
        # The accepted plan may already be bound to an editor even if a later
        # interrupted planner session replaced its small completion marker.
        # UI polling checks only that binding; Pipeline revalidates the plan and
        # loads the full matching editor before it can make a paid request.
        if not has_plan and states['editor'].get('signature'):
            try:
                from app_version import editor_prompt_path
                from training_quality import editor_system
                from checkpoints import signature
                plan = read(folder / 'content-plan.json')
                system = editor_system(editor_prompt_path(Path(__file__).resolve().parent).read_text(encoding='utf-8'), report.get('purpose', 'auto'))
                has_plan = bool(plan and states['editor']['signature'] == signature(
                    {'prompt': report.get('prompt'), 'plan': plan, 'system': system}))
            except (OSError, ValueError, TypeError, KeyError):
                pass
        # Restyling reuses a verified source plan without an analysis checkpoint.
        # Revalidate the source, as run() will, instead of treating a JSON file alone
        # as an approved plan. This also handles older saved restyle runs.
        if not has_plan and report.get('restyle_from'):
            try:
                from restyle import restyle_source
                restyle_source(folder.parent.parent, report['restyle_from'])
                has_plan = True
            except (ValueError, OSError, TypeError, KeyError):
                pass
        has_review = bool(states['document_content_review'].get('completed') and states['document_content_review'].get('approved'))
        has_editor = bool(states['editor'])
        resume['saved_checkpoint'] = bool(states['content_plan']) or has_editor
        resume['from_stage'] = ('finish' if has_review and has_editor else
                                'verify' if states['document_content_review'] and not states['document_content_review'].get('completed') and has_plan and has_editor else
                                'document' if has_plan else 'analyze')
        evidence = Path(report.get('evidence_dir', folder / 'work' / 'crv'))
        ready = ((evidence / 'MANIFEST.txt').is_file() and bool(read(evidence / 'frames.json').get('frames'))
                 and bool(read(folder / 'evidence.json').get('frames')))
        costs_unknown = bool(pending) or any('cost_usd' not in c.get('usage', {}) for c in usage.get('api_calls', []))
        old_limit = usage.get('max_calls', report.get('max_api_calls', 12))
        spent, ceiling = usage.get('known_cost_usd'), usage.get('budget_usd')
        finish_reserve = (reason == 'call_limit' and has_plan and has_editor and old_limit in {12, 20}
                          and isinstance(usage.get('call_count'), int) and usage['call_count'] < DEFAULT_MAX_API_CALLS
                          and isinstance(spent, (int, float)) and isinstance(ceiling, (int, float)) and spent < ceiling)
        if report.get('quality_pipeline') != 'quality-first-v3':
            resume['reason'] = 'legacy'
        elif costs_unknown:
            resume['reason'] = 'billing_pending'
        elif reason in {'call_limit', 'round_limit', 'revision_limit', 'token_limit', 'estimate_limit'} and not finish_reserve:
            resume['reason'] = reason
        elif usage.get('call_count', 0) >= old_limit and not finish_reserve:
            resume['reason'] = 'call_limit'
        elif report.get('resume_fingerprint') and fingerprint and report['resume_fingerprint'] != fingerprint:
            resume['reason'] = 'version_changed'
        elif not ready:
            resume.update(reason='video_incomplete', from_stage='prepare')
        else:
            resume.update(available=True, reason=reason if reason in {'budget', 'estimate_confirm'} else None)
            if finish_reserve:
                resume.update(reason='finish_reserve', max_calls=DEFAULT_MAX_API_CALLS)
            if reason in {'budget', 'estimate_confirm'} and usage.get('estimate'):
                resume['estimate'] = {k: usage['estimate'].get(k) for k in ('low_usd', 'high_usd', 'spent_usd')}
            if not report.get('resume_fingerprint'):
                resume.update(from_stage='analyze', saved_checkpoint=False)
            if resume['from_stage'] == 'analyze' and recorded.get('stages', {}).get('analyze', {}).get('state') == 'complete':
                resume['restart_reason'] = 'plan_checkpoint_missing'
    now = time.time()
    elapsed = (now if status == 'running' else job.get('finished_at', updated or now)) - job.get('started', now)
    return {'available': bool(recorded), 'current': current, 'stages': stages, 'completed_count': finished,
            'total_stages': len(STAGES), 'updated_at': updated or None,
            'elapsed_seconds': max(0, elapsed),
            'api_wait_started_at': api_started, 'stop_requested': bool(job.get('stop_requested')),
            'stop_code': reason if stopped else None, 'resume': resume}
