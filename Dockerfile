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
RUN useradd --create-home --uid 1000 appuser
COPY --chown=appuser:appuser *.py *.cjs *.css *.html *.js *.json /app/
COPY --chown=appuser:appuser editor.txt /app/prompts/editor.txt
RUN mkdir -p /app/work /app/cache && chown -R appuser:appuser /app /opt/pw
USER appuser
EXPOSE 7860
ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["python","cloud_entry.py"]
