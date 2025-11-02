#!/usr/bin/env bash
# download_wsi.sh
# Usage: ./download_wsi.sh [concurrency] [outdir]
# Reads breast_wsi_urls.txt in the current directory and downloads files into the given directory (default: ./breast_wsi_downloads)

set -euo pipefail
cd "$(dirname "$0")"

CONCURRENCY=${1:-4}
OUTDIR=${2:-./breast_wsi_downloads}
DRY=${3:-""}
if [ "$DRY" = "--dry-run" ] || [ "$DRY" = "dry" ] || [ "${DRY_RUN:-}" = "1" ]; then
    DRY=1
else
    DRY=0
fi
URLFILE=breast_wsi_urls.txt

if [ ! -f "$URLFILE" ]; then
    echo "Missing $URLFILE. Run script.py first to generate it." >&2
    exit 2
fi

mkdir -p "$OUTDIR"

echo "Download directory: $OUTDIR"

# Prefer aria2c if available (multi-connection per file)
if command -v aria2c >/dev/null 2>&1; then
    echo "Using aria2c with concurrency=$CONCURRENCY (dry-run=$DRY)"
    # Filter URLs to only those whose basename is not already present in OUTDIR
    TMP=$(mktemp)
    while IFS= read -r url; do
        [ -z "$url" ] && continue
        name=$(basename "$url")
        if [ -f "$OUTDIR/$name" ]; then
            echo "Skipping existing: $name"
        else
            echo "$url" >> "$TMP"
        fi
    done < "$URLFILE"

    if [ "$DRY" -eq 1 ]; then
        echo "-- Dry run: the following URLs would be passed to aria2c:"
        if [ -s "$TMP" ]; then
            nl -ba "$TMP"
        else
            echo "(none)"
        fi
        rm -f "$TMP"
        exit 0
    fi

    if [ -s "$TMP" ]; then
        aria2c -i "$TMP" -d "$OUTDIR" -x 4 -s 4 -j "$CONCURRENCY" --auto-file-renaming=false --continue
    else
        echo "No new files to download."
    fi
    rm -f "$TMP"
    exit 0
fi

# Fallback: use xargs + wget to spawn CONCURRENCY wget processes
if command -v wget >/dev/null 2>&1 && command -v xargs >/dev/null 2>&1; then
        echo "Using xargs + wget with concurrency=$CONCURRENCY (dry-run=$DRY)"
        export OUTDIR
        if [ "$DRY" -eq 1 ]; then
            echo "-- Dry run: files that would be downloaded (or skipped):"
            while IFS= read -r url; do
                [ -z "$url" ] && continue
                name=$(basename "$url")
                if [ -f "$OUTDIR/$name" ]; then
                    echo "SKIP: $name"
                else
                    echo "DOWNLOAD: $name -> $url"
                fi
            done < "$URLFILE"
            exit 0
        fi

        # For each URL, xargs will call a shell that checks if the file exists before invoking wget
        cat "$URLFILE" | xargs -n1 -P "$CONCURRENCY" -I {} sh -c '
            name=$(basename "$1")
            if [ -f "$OUTDIR/$name" ]; then
                echo "Skipping existing: $name"
            else
                wget -c --no-clobber -P "$OUTDIR" "$1"
            fi
        ' _ {}
    exit 0
fi

# Very small Python fallback (single-machine parallelism)
python3 - <<'PY'
import sys, subprocess, queue, threading
from pathlib import Path
urls = Path('breast_wsi_urls.txt').read_text().strip().splitlines()
outdir = Path('./breast_wsi_downloads')
outdir.mkdir(parents=True, exist_ok=True)
import requests
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
                        print('Skipping existing:', name)
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
