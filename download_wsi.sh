#!/usr/bin/env bash
# download_wsi.sh
# Usage: ./download_wsi.sh [concurrency]
# Reads breast_wsi_urls.txt in the current directory and downloads files into ./breast_wsi_downloads/
# Default concurrency: 4

set -euo pipefail
cd "$(dirname "$0")"
CONCURRENCY=${1:-4}
OUTDIR=./breast_wsi_downloads
URLFILE=breast_wsi_urls.txt

if [ ! -f "$URLFILE" ]; then
  echo "Missing $URLFILE. Run script.py first to generate it." >&2
  exit 2
fi
mkdir -p "$OUTDIR"

# Prefer aria2c if available (multi-connection per file)
if command -v aria2c >/dev/null 2>&1; then
  echo "Using aria2c with concurrency=$CONCURRENCY"
  # --auto-file-renaming=false keeps filenames exactly as provided
  aria2c -i "$URLFILE" -d "$OUTDIR" -x 4 -s 4 -j "$CONCURRENCY" --auto-file-renaming=false --continue
  exit 0
fi

# Fallback: use xargs + wget to spawn CONCURRENCY wget processes
if command -v wget >/dev/null 2>&1 && command -v xargs >/dev/null 2>&1; then
  echo "Using xargs + wget with concurrency=$CONCURRENCY"
  # -c to resume partials, --no-clobber to avoid overwriting
  cat "$URLFILE" | xargs -n1 -P "$CONCURRENCY" -I {} wget -c --no-clobber -P "$OUTDIR" "{}"
  exit 0
fi

# Very small Python fallback
python3 - <<'PY'
import sys, subprocess, queue, threading
from pathlib import Path
urls = Path('breast_wsi_urls.txt').read_text().strip().splitlines()
outdir = Path('./breast_wsi_downloads')
outdir.mkdir(parents=True, exist_ok=True)
import requests
from tqdm import tqdm
q = queue.Queue()
for u in urls:
    q.put(u)

concurrency = int(sys.argv[1]) if len(sys.argv)>1 else 4

def worker():
    while not q.empty():
        url = q.get()
        name = url.rstrip('/').split('/')[-1]
        dest = outdir / name
        if dest.exists():
            q.task_done(); continue
        try:
            r = requests.get(url, stream=True, timeout=30)
            r.raise_for_status()
            with open(dest, 'wb') as fh:
                for chunk in r.iter_content(1024*64):
                    fh.write(chunk)
        except Exception as e:
            print('ERROR', url, e)
        q.task_done()

threads = []
for _ in range(concurrency):
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    threads.append(t)
q.join()
PY

echo "Done."
