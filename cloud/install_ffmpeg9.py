"""Install two verified FFmpeg binaries during the image build, not during extraction."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tarfile
import urllib.request

URL = "https://github.com/FFmpeg-Builds/FFmpeg-Builds/releases/download/latest/ffmpeg-n9.0-latest-linux64-lgpl-9.0.tar.xz"
EXPECTED = "3c75df2d1f129dd8a843d2835fee296916a3d78ae253665649f368dbcfe33fb2"
archive = Path("/tmp/ffmpeg9-verified.tar.xz")
digest = hashlib.sha256()
request = urllib.request.Request(URL, headers={"User-Agent": "crv-modal-extraction-test"})
with urllib.request.urlopen(request, timeout=90) as response, archive.open("wb") as handle:
    while block := response.read(1024 * 1024):
        digest.update(block)
        handle.write(block)
if digest.hexdigest() != EXPECTED:
    raise RuntimeError("FFmpeg release checksum changed; installation refused")
with tarfile.open(archive, "r:xz") as bundle:
    for name in ("ffmpeg", "ffprobe"):
        members = [m for m in bundle.getmembers() if m.isfile() and m.name.endswith("/bin/" + name)]
        if len(members) != 1:
            raise RuntimeError("Unexpected FFmpeg archive layout")
        destination = Path("/usr/local/bin") / name
        with bundle.extractfile(members[0]) as source, destination.open("wb") as target:
            shutil.copyfileobj(source, target)
        destination.chmod(0o755)
        version = subprocess.run([str(destination), "-version"], capture_output=True,
                                 text=True, check=True).stdout.splitlines()[0]
        if "version n9.0.2" not in version and "version 9.0.2" not in version:
            raise RuntimeError("Expected FFmpeg 9.0.2 build: " + version)
        print(version, flush=True)
archive.unlink()
