"""Windows-safe replace for atomic JSON/state writes.

On Windows, os.replace() fails with PermissionError (WinError 5/32) while
another thread or process (UI status polling, antivirus, indexer) has the
destination open. Retry briefly instead of failing the whole job.
Behaviour on Linux/macOS is unchanged (the first attempt succeeds).
"""
import os
import time


def safe_replace(source, destination, attempts=50, delay=0.05):
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(delay)
