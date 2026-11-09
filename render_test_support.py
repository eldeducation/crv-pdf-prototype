"""Only missing renderer prerequisites may skip a local test, never a render error."""
import json
import os
from pathlib import Path
import shutil
import subprocess


def require_renderer(case):
    import pipeline
    settings = pipeline.runtime()
    node = settings.get('node') or shutil.which('node')
    missing = None
    if not node or not Path(node).is_file():
        missing = 'Node.js is not installed'
    else:
        script = '''
const fs = require('fs');
let p;
try { p = require(process.argv[1]); }
catch (e) { if (e.code === 'MODULE_NOT_FOUND') process.exit(42); throw e; }
const browser = process.argv[2] || p.chromium.executablePath();
if (!fs.existsSync(browser)) process.exit(43);
'''
        result = subprocess.run([node, '-e', script, settings.get('playwright') or 'playwright',
                                 settings.get('browser') or ''], cwd=pipeline.ROOT,
                                capture_output=True, text=True, encoding='utf-8', timeout=20)
        if result.returncode in (42, 43):
            missing = 'Playwright or its Chromium browser is not installed'
        elif result.returncode:
            raise RuntimeError('Renderer prerequisite check failed: ' + result.stderr[:500])
    if missing:
        if os.getenv('VIDEO_PDF_REQUIRE_RENDER_TESTS') == '1':
            case.fail(missing + '; rendering is required in this test environment')
        case.skipTest(missing)
