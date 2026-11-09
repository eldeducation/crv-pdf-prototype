"""Public build identity and the single allowlist used by sessions and releases."""
import hashlib
import json
import os
from pathlib import Path
import re

APP_FILES = (
    'server.py', 'pipeline.py', 'openrouter_client.py', 'usage_guard.py', 'model_catalog.py',
    'youtube_support.py', 'home_fetch.py', 'video_upload.py', 'content_quality.py',
    'checkpoints.py', 'crv_worker.py', 'render.cjs', 'layout.css', 'index.html', 'ui.js',
    'runtime.local.json', 'security.py', 'document_options.py', 'document_design.py',
    'editorial_quality.py', 'restyle.py', 'source_references.py', 'job_progress.py',
    'action_grounding.py', 'manual_client.py', 'presentation_quality.py', 'web_research.py',
    'cost_estimate.py', 'markdown_export.py', 'prompt_cache.py', 'key_store.py', 'app_version.py',
)


def source_hash(root):
    root = Path(root)
    digest = hashlib.sha256()
    for name in sorted(set(APP_FILES) - {'runtime.local.json'}):
        digest.update(name.encode() + b'\0')
        digest.update((root / name).read_bytes().replace(b'\r\n', b'\n'))
        digest.update(b'\0')
    prompt = root / 'prompts/editor.txt'
    if not prompt.is_file():
        prompt = root / 'editor.txt'
    digest.update(prompt.read_bytes().replace(b'\r\n', b'\n'))
    return digest.hexdigest()


def version_info(root):
    root = Path(root)
    actual = source_hash(root)
    try:
        saved = json.loads((root / 'build-info.json').read_text(encoding='utf-8'))
    except (OSError, ValueError):
        saved = {}
    saved_hash = saved.get('source_hash')
    matches = (isinstance(saved_hash, str) and re.fullmatch(r'[a-f0-9]{64}', saved_hash)
               and saved.get('runtime_source_hash', saved_hash) == actual)
    fingerprint = saved.get('source_hash') if matches else actual
    revision = saved.get('revision') if matches else None
    revision = revision or os.getenv('RENDER_GIT_COMMIT', '')
    if not isinstance(revision, str) or not re.fullmatch(r'[a-f0-9]{40}', revision):
        revision = None
    return {'revision': revision, 'source_hash': fingerprint,
            'label': (revision[:8] if revision else 'local') + ' / ' + fingerprint[:8]}
