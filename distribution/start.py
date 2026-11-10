"""One entry point for first setup and later launches; never calls an AI API."""
from pathlib import Path
import argparse
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    args = parser.parse_args()
    import setup_local
    # Check before downloading anything. Leave system dependencies to the user
    # or their coding agent rather than silently changing the whole PC.
    setup_local.prerequisites()
    if args.check_only:
        print('Ready for setup. No installation, video download or AI API call performed.')
        return
    if not setup_local.is_ready(ROOT):
        subprocess.run([sys.executable, str(ROOT / 'setup_local.py')], cwd=ROOT, check=True)
    command = [str(setup_local.python_path()), str(ROOT / 'launch.py')]
    if args.no_browser:
        command.append('--no-browser')
    subprocess.run(command, cwd=ROOT, check=True)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        print('Could not start:', error, file=sys.stderr)
        print('Open this folder in your coding agent and ask it to read LLM-START.md.', file=sys.stderr)
        raise SystemExit(1)
