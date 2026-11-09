"""List old generated data in runs/ and, only when asked, delete what is safe to remove.

    python cleanup_runs.py                 # list only (nothing is deleted)
    python cleanup_runs.py --delete        # list, then ask before deleting the candidates

Kept, never offered for deletion:
  * finished documents (complete / needs_review) - they are the restyle sources;
  * runs whose video, images or draft another kept run reuses (evidence_dir / restyle_from);
  * runs still marked running, and the newest failed run (it may be resumed);
  * anything newer than --keep-days (default 2), and any folder that is not a run.
Candidates are older failed runs and empty/unreadable leftovers.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN_NAME = re.compile(r'(\d{8})-(\d{6})-[a-f0-9]{6}')
FINISHED = ('complete', 'needs_review')


def folder_size(folder):
    total = 0
    for item in folder.rglob('*'):
        try:
            if item.is_file() and not item.is_symlink():
                total += item.stat().st_size
        except OSError:
            pass
    return total


def read_report(folder):
    try:
        report = json.loads((folder / 'run.json').read_text(encoding='utf-8'))
        return report if isinstance(report, dict) else None
    except (OSError, ValueError):
        return None


def referenced_runs(report, runs_dir):
    """Names of other runs this run reuses data from."""
    names = set()
    if not report:
        return names
    if isinstance(report.get('restyle_from'), str):
        names.add(report['restyle_from'])
    evidence = report.get('evidence_dir')
    if isinstance(evidence, str) and evidence:
        try:
            relative = Path(evidence).resolve().relative_to(runs_dir.resolve())
            names.add(relative.parts[0])
        except (ValueError, IndexError, OSError):
            pass
    return names


def survey(runs_dir, keep_days=2.0, now=None):
    """Return one dict per run folder: name, size, status, keep (bool), reason."""
    now = time.time() if now is None else now
    entries = []
    for folder in sorted(p for p in runs_dir.iterdir() if p.is_dir()):
        match = RUN_NAME.fullmatch(folder.name)
        report = read_report(folder)
        started = time.mktime(time.strptime(match[1] + match[2], '%Y%m%d%H%M%S')) if match else None
        entries.append({'name': folder.name, 'path': folder, 'run': bool(match), 'report': report,
                        'status': (report or {}).get('status') or ('(empty)' if not any(folder.iterdir()) else '(no run.json)'),
                        'started': started, 'size': folder_size(folder), 'keep': None, 'reason': ''})

    newest_failed = max((e['started'] for e in entries if e['run'] and e['status'] == 'failed'), default=None)
    for entry in entries:
        if not entry['run']:
            entry['keep'], entry['reason'] = True, 'not a run folder'
        elif entry['status'] in FINISHED:
            entry['keep'], entry['reason'] = True, 'finished document'
        elif entry['status'] == 'running':
            entry['keep'], entry['reason'] = True, 'running'
        elif now - entry['started'] < keep_days * 86400:
            entry['keep'], entry['reason'] = True, f'newer than {keep_days:g} days'
        elif entry['status'] == 'failed' and entry['started'] == newest_failed:
            entry['keep'], entry['reason'] = True, 'newest failed run (can be resumed)'

    # Whatever a kept run reuses is kept too (repeat: a kept source may reuse another run).
    by_name = {e['name']: e for e in entries}
    changed = True
    while changed:
        changed = False
        for entry in entries:
            if not entry['keep']:
                continue
            for name in referenced_runs(entry['report'], runs_dir):
                target = by_name.get(name)
                if target and not target['keep']:
                    target['keep'], target['reason'] = True, f'reused by {entry["name"]}'
                    changed = True

    for entry in entries:
        if not entry['keep']:
            entry['keep'] = False
            entry['reason'] = 'old failed run' if entry['status'] == 'failed' else 'leftover without a usable record'
    return entries


def megabytes(size):
    return f'{size / 1e6:8.1f} MB'


def delete(entries, runs_dir):
    base = runs_dir.resolve()
    removed = 0
    for entry in entries:
        path = entry['path'].resolve()
        if entry['keep'] or path.parent != base or not RUN_NAME.fullmatch(path.name):
            continue
        shutil.rmtree(path)
        removed += entry['size']
    return removed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--delete', action='store_true', help='delete the listed candidates after confirmation')
    parser.add_argument('--yes', action='store_true', help='with --delete: do not ask again')
    parser.add_argument('--keep-days', type=float, default=2.0)
    parser.add_argument('--runs', type=Path, default=ROOT / 'runs')
    args = parser.parse_args(argv)
    if not args.runs.is_dir():
        print('runs フォルダーがありません。')
        return 0
    entries = survey(args.runs, args.keep_days)
    for entry in entries:
        mark = '  keep  ' if entry['keep'] else 'DELETE? '
        print(f"{mark}{entry['name']:<26}{megabytes(entry['size'])}  {entry['status']:<14}{entry['reason']}")
    candidates = [e for e in entries if not e['keep']]
    total = sum(e['size'] for e in entries)
    freed = sum(e['size'] for e in candidates)
    print(f'\n合計 {megabytes(total).strip()} / 削除候補 {len(candidates)}件 {megabytes(freed).strip()}')
    if not candidates or not args.delete:
        if candidates:
            print('削除はしていません。削除するときは --delete を付けて実行してください。')
        return 0
    if not args.yes:
        answer = input(f'{len(candidates)}件を完全に削除します（元に戻せません）。よろしければ yes と入力: ')
        if answer.strip().lower() != 'yes':
            print('削除を中止しました。')
            return 0
    print(f'{megabytes(delete(candidates, args.runs)).strip()} を削除しました。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
