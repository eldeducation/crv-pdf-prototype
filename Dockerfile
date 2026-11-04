FROM node:24-bookworm-slim AS youtube_node
FROM youtube_node AS youtube_pot
WORKDIR /opt/bgutil
RUN node -e "fetch('https://codeload.github.com/Brainicism/bgutil-ytdlp-pot-provider/tar.gz/26475e9d3665b972c4aeb83b4dbaafcf64b88438').then(r=>{if(!r.ok)throw Error(r.status);return r.arrayBuffer()}).then(b=>require('fs').writeFileSync('/tmp/bgutil.tgz',Buffer.from(b)))" \
    && echo 'a8144eab6a4f38f320063688531f461afe18c0a58be2dd3152b780f4851e954d  /tmp/bgutil.tgz' | sha256sum -c - \
    && tar -xzf /tmp/bgutil.tgz --strip-components=1
WORKDIR /opt/bgutil/server
RUN npm ci --no-audit --no-fund && npx tsc && npm prune --omit=dev --no-audit --no-fund

FROM python:3.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/pw XDG_CACHE_HOME=/app/cache \
    HF_HOME=/app/cache/huggingface CRV_MEMORY_DB=/app/work/memory.db \
    PORT=7860 OMP_NUM_THREADS=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg nodejs npm fonts-noto-cjk ca-certificates tini && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && pip install -r /tmp/requirements.txt
RUN npm install --omit=dev playwright@1.56.1 && npx playwright install --with-deps chromium
COPY --from=youtube_node /usr/local/bin/node /usr/local/bin/node
RUN pip install 'yt-dlp[default]==2026.10.26'
RUN pip install --target /opt/youtube-plugins/bgutil 'bgutil-ytdlp-pot-provider==2.0.2'
COPY --from=youtube_pot /opt/bgutil/server /opt/bgutil/server
COPY --from=youtube_pot /opt/bgutil/LICENSE /opt/bgutil/LICENSE
RUN node /opt/bgutil/server/build/generate_once.js --version
RUN node --version && python -m yt_dlp --version
# Separate, pinned browser experiment; no account profile or proxy is used.
RUN apt-get update && apt-get install -y --no-install-recommends xvfb xauth && rm -rf /var/lib/apt/lists/*
RUN pip install 'nodriver==0.50.3' && pip install --no-deps --target /opt/wpc-plugins/wpc 'yt-dlp-getpot-wpc==1.1.2'
RUN python -c "from pathlib import Path; paths=list(Path('/opt/pw').glob('chromium-*/chrome-linux*/chrome')); assert len(paths)==1, paths; Path('/opt/youtube-chromium').symlink_to(paths[0])"
RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser *.py *.cjs *.css *.html *.js *.json /app/
COPY --chown=appuser:appuser editor.txt /app/prompts/editor.txt
RUN mkdir -p /app/work /app/cache && chown -R appuser:appuser /app /opt/pw
USER appuser
EXPOSE 7860
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["python","cloud_entry.py"]
