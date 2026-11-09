"""Run once on each recipient's own PC. No API key is needed."""
from pathlib import Path
import argparse, json, os, shutil, subprocess, sys, venv
ROOT = Path(__file__).resolve().parent

def python_path(root=ROOT):
    return root / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')

def prerequisites():
    if not (3, 10) <= sys.version_info[:2] < (3, 13):
        raise RuntimeError('Use Python 3.10-3.12; Python 3.12 is recommended.')
    found = {name: shutil.which(name) for name in ('node', 'npm', 'ffmpeg', 'ffprobe')}
    missing = [name for name, path in found.items() if not path]
    if missing:
        raise RuntimeError('Install official dependencies and reopen the terminal: ' + ', '.join(missing))
    major = int(subprocess.check_output([found['node'], '--version'], text=True).strip().lstrip('v').split('.')[0])
    if major < 22:
        raise RuntimeError('Node.js 22 or later is required.')
    return found

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    found = prerequisites()
    if args.check_only:
        print('Prerequisites found. No installation or API call performed.')
        return
    print('Installing Python packages and a PDF browser into this folder. This may take several minutes.')
    env = dict(os.environ)
    # Installing dependencies must not inherit another Python environment.
    env.pop('PYTHONHOME', None)
    env.pop('PYTHONPATH', None)
    for name in ('OPENROUTER_API_KEY','ANTHROPIC_API_KEY','OPENAI_API_KEY','GH_TOKEN','GITHUB_TOKEN'):
        env.pop(name, None)
    if not python_path().exists():
        venv.EnvBuilder(with_pip=True).create(ROOT / '.venv')
    py = str(python_path())
    subprocess.run([py, '-m', 'pip', 'install', '--upgrade', 'pip'], check=True, cwd=ROOT, env=env)
    if sys.platform in ('win32', 'linux'):
        subprocess.run([py, '-m', 'pip', 'install', 'torch', '--index-url', 'https://download.pytorch.org/whl/cpu'], check=True, cwd=ROOT, env=env)
    subprocess.run([py, '-m', 'pip', 'install', '-r', str(ROOT / 'requirements.txt')], check=True, cwd=ROOT, env=env)
    # npm.cmd needs cmd.exe on Windows. All text after /c is fixed, never user input.
    npm = [env.get('COMSPEC', 'cmd.exe'), '/d', '/c', 'npm'] if os.name == 'nt' else [found['npm']]
    subprocess.run(npm + ['install', '--ignore-scripts', '--no-audit', '--no-fund'], check=True, cwd=ROOT, env=env)
    subprocess.run([found['node'], str(ROOT / 'node_modules/playwright/cli.js'), 'install', 'chromium'], check=True, cwd=ROOT, env=env)
    (ROOT / 'app/runtime.local.json').write_text(json.dumps({'node':found['node'], 'playwright':str(ROOT/'node_modules/playwright')}, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Ready. Run: python launch.py')

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError) as error:
        print('Setup failed:', error, file=sys.stderr)
        raise SystemExit(1)
