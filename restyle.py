"""Reuse only a completed, verified source in this server/browser session."""
import json
import re
from pathlib import Path
from content_quality import digest


def restyle_source(root, identity):
    root = Path(root).resolve()
    if not isinstance(identity, str) or not re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{6}', identity):
        raise ValueError('変更元の資料の識別子が不正です。')
    folder = (root / 'runs' / identity).resolve()
    if folder.parent != (root / 'runs').resolve():
        raise ValueError('同じブラウザ内の資料だけを変更できます。')
    def read(name):
        path = folder / name
        if not path.resolve().is_relative_to(folder):
            raise ValueError('資料の保存場所が不正です。')
        return json.loads(path.read_text(encoding='utf-8'))
    try:
        report, doc, review = read('run.json'), read('document.json'), read('content-review.json')
        evidence = Path(report['evidence_dir']).resolve()
        plan = read('content-plan.json')
        if (report.get('status') != 'complete' or not report.get('content_verified') or
                report.get('quality_pipeline') != 'quality-first-v3' or
                not review.get('approved') or review.get('document_sha256') != digest(doc)):
            raise ValueError('内容確認が完了した資料だけデザインを変更できます。')
        if not evidence.is_relative_to(root) or not (evidence / 'frames.json').is_file():
            raise ValueError('再利用する動画の解析データがありません。')
        if not (folder / 'evidence.json').is_file() or not isinstance(plan.get('units'), list):
            raise ValueError('再利用する内容案・画像がありません。')
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError('変更元の資料が見つからないか、保存データが不足しています。') from None
    return folder, report, plan
