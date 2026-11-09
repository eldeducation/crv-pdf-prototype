"""Build a secret-free local package from the same source as the running app."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

SOURCE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SOURCE))
from app_version import APP_FILES, source_hash


def build(output, revision, source=SOURCE):
    source = Path(source)
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('An exact Git commit SHA is required.')
    files = {}
    for name in APP_FILES:
        # Host paths are private and are generated on the recipient's PC.
        files['app/' + name] = b'{}\n' if name == 'runtime.local.json' else (source / name).read_bytes()
    files['app/prompts/editor.txt'] = (source / 'editor.txt').read_bytes()
    for path in sorted((source / 'distribution').iterdir()):
        if path.is_file() and path.name in {'setup_local.py','launch.py','setup.cmd','start.cmd','README.md','LLM-START.md','MANUAL-TEST.md'}:
            files[path.name] = path.read_bytes()
    files['requirements.txt'] = (source/'requirements.txt').read_bytes() + b'\nyt-dlp[default]==2026.10.26\n'
    files['package.json'] = json.dumps({'name':'crv-pdf-local','private':True,
        'dependencies':{'playwright':'1.56.1'}}, sort_keys=True).encode()
    files['SECURITY.md'] = (source / 'SECURITY.md').read_bytes()
    for name, data in files.items():
        if re.search(rb'sk-(?:or-v1-|ant-|proj-)[A-Za-z0-9_-]{20,}', data):
            raise ValueError('A credential-shaped value was found in a release source: ' + name)
    info = {'revision': revision, 'source_hash':source_hash(source)}
    files['app/build-info.json'] = json.dumps(info,sort_keys=True).encode()
    files['.gitignore'] = b'.venv/\nnode_modules/\napp/*.local.*\napp/.env*\napp/runs/\napp/uploads/\napp/work/\n__pycache__/\n*.log\n'
    manifest = {name:hashlib.sha256(data).hexdigest() for name,data in sorted(files.items())}
    files['MANIFEST.json'] = json.dumps({**info,'sha256':manifest},sort_keys=True,indent=2).encode()
    output = Path(output)
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,data in sorted(files.items()):
            item = zipfile.ZipInfo('crv-pdf-local/' + name, date_time=(2026,11,9,0,0,0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o644 << 16
            archive.writestr(item,data)
    return info


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output',default='dist/crv-pdf-local.zip')
    parser.add_argument('--revision',required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.output,args.revision)))
