"""References use validated unit/frame timestamps, never model-written URLs."""
import html
import json
import math
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from security import normalized_video_url


def clock(value):
    seconds = max(0, int(float(value)))
    return f'{seconds//60:02}:{seconds%60:02}'


def youtube_link(source, seconds=0):
    try:
        parsed = urlsplit(str(source))
        port = parsed.port
    except ValueError:
        return None
    if parsed.scheme != 'https' or parsed.username or parsed.password or port not in {None, 443}:
        return None
    identity = None
    if parsed.hostname in {'youtube.com', 'www.youtube.com', 'm.youtube.com'} and parsed.path == '/watch':
        identity = parse_qs(parsed.query).get('v', [None])[0]
    elif parsed.hostname == 'youtu.be':
        identity = parsed.path.strip('/')
    if not identity or not re.fullmatch(r'[A-Za-z0-9_-]{11}', identity):
        return None
    return f'https://www.youtube.com/watch?v={identity}&t={max(0, int(float(seconds)))}s'


def source_link(source):
    """X links open the post; only YouTube links support timestamp seeking."""
    if youtube_link(source):
        return youtube_link(source)
    try:
        return normalized_video_url(source)
    except ValueError:
        return None


def citation_html(unit, source):
    start, end = float(unit['start']), float(unit['end'])
    label = clock(start) if start == end else clock(start) + '–' + clock(end)
    url = youtube_link(source, start)
    text = f'<a href="{html.escape(url, quote=True)}" rel="noopener noreferrer">{label}</a>' if url else label
    return f'<small class="source-ref">[{text}]</small>'


def markdown_references(units, source, language='auto'):
    if not units:
        return ''
    title = 'Source scenes' if language == 'en' else '元動画の該当場面'
    lines = ['\n\n## ' + title, '']
    for unit in units:
        label = clock(unit['start']) + '–' + clock(unit['end'])
        url = youtube_link(source, unit['start'])
        time = f'[{label}]({url})' if url else label
        name = re.sub(r'[\[\]<>\r\n]', ' ', str(unit['title']))
        lines.append(f'- {name} — {time}')
    return '\n'.join(lines) + '\n'


def _read(path, default):
    try:
        return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return default


def write_index(folder):
    """Expose only reader-facing data. Never publish source paths or checkpoints."""
    folder = Path(folder)
    plan = _read(folder / 'content-plan.json', {})
    evidence = _read(folder / 'evidence.json', {})
    if not plan.get('units') or not evidence.get('frames'):
        return False
    duration = float(evidence['duration'])
    records = {r['file']: r for r in evidence['frames']}
    review = _read(folder / 'content-review.json', {})
    review_kind = 'document'
    if not review.get('unit_checks'):
        review = _read(folder / 'plan-review.json', {})
        review_kind = 'plan'
    document = _read(folder / 'document.json', {})
    report = _read(folder / 'run.json', {})
    if document and review.get('document_sha256'):
        # Never apply approval from a previous draft to the current document.
        from content_quality import digest
        if digest(document) != review['document_sha256']:
            review = {}
    checks = {c['id']: c for c in review.get('unit_checks', [])}
    from web_research import WebResearch
    research = WebResearch(folder, evidence.get('source', ''))
    try:
        external = research.facts(plan['units'])
    except ValueError:
        external = {}
    external_checks = {c.get('fact_id'): c for c in review.get('external_checks', [])}
    units = []
    for unit in plan['units']:
        start, end = float(unit['start']), float(unit['end'])
        if not all(math.isfinite(t) for t in (start, end)) or not 0 <= start < end <= duration:
            continue
        frames = [records[f] for f in unit.get('evidence_files', []) if f in records and re.fullmatch(r'assets/[A-Za-z0-9_.-]+\.(?:jpg|jpeg|png)', f)]
        frames.sort(key=lambda r:r['seconds'])
        if len(frames) > 3:
            frames = [frames[0], frames[len(frames)//2], frames[-1]]
        check = checks.get(unit['id'], {})
        pages = [i+1 for i, page in enumerate(document.get('pages', []))
                 if unit['id'] in page.get('source_units', []) or re.search(
                     r'data-source-unit=[\"\x27]' + re.escape(unit['id']) + r'[\"\x27]', page.get('html', ''))]
        units.append({'id': unit['id'], 'title': unit['title'], 'explanation': unit['explanation'],
                      'start': start, 'end': end, 'video_url': youtube_link(evidence.get('source'), start),
                      'frames': [{'file': r['file'], 'seconds': r['seconds']} for r in frames],
                      'verdict': check.get('verdict', 'unverified'), 'finding': check.get('finding', ''),
                      'review_kind': review_kind if check else None, 'pages': pages,
                      'external_facts': [{**f, 'review': external_checks.get(f['id'], {})}
                                         for f in external.values() if f['unit_id'] == unit['id']]})
    data = {'version': 1, 'title': document.get('title', plan.get('overview', '')),
            'source_kind': 'youtube' if youtube_link(evidence.get('source')) else 'x' if source_link(evidence.get('source')) else 'upload',
            'source_url': source_link(evidence.get('source')),
            'duration': duration, 'units': units, 'coverage_gaps': review.get('coverage_gaps', []),
            'document_verified': bool(report.get('content_verified') and review_kind == 'document' and review.get('approved')),
            'purpose': report.get('purpose', 'auto'), 'output_language': report.get('output_language', 'auto')}
    temporary = folder / 'source-index.tmp'
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(folder / 'source-index.json')
    return True


def local_video(root, run_folder):
    """Only sources inside this session's runs/uploads may be streamed."""
    root, folder = Path(root).resolve(), Path(run_folder).resolve()
    if not folder.is_relative_to(root / 'runs'):
        return None
    report = _read(folder / 'run.json', {})
    candidates = []
    evidence = Path(report.get('evidence_dir', folder / 'work' / 'crv')).resolve()
    if evidence.is_relative_to(root / 'runs'):
        candidates.extend(evidence.glob('source.*'))
    source = Path(report.get('source', 'missing')).resolve()
    if source.is_relative_to(root / 'uploads'):
        candidates.append(source)
    for candidate in candidates:
        resolved = candidate.resolve()
        if not (resolved.is_relative_to(root / 'runs') or resolved.is_relative_to(root / 'uploads')):
            continue
        if resolved.suffix.lower() in {'.mp4', '.webm', '.mov', '.mkv'} and resolved.is_file():
            return resolved
    return None


def byte_range(header, size):
    """Bound each media response; browsers request subsequent chunks as needed."""
    match = re.fullmatch(r'bytes=(\d+)-(\d*)', header or 'bytes=0-')
    if not match or size < 1:
        raise ValueError('Invalid video byte range.')
    start = int(match.group(1))
    end = min(int(match.group(2)) if match.group(2) else size-1, start+2*1024**2-1, size-1)
    if start >= size or end < start:
        raise ValueError('Video byte range is out of bounds.')
    return start, end
