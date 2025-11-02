#!/usr/bin/env python3
"""
gtex.py

Simple WSI downloader using wget.

Usage examples:
  python3 gtex.py                 # default: concurrency=4, outdir=./breast_wsi_downloads
  python3 gtex.py -c 8 -o /data/wsis --dry-run

Features:
 - Reads URLs from `breast_wsi_urls.txt` by default (one URL per line).
 - Uses `wget` to download files (respects server content-disposition).
 - Optional concurrency (ThreadPoolExecutor) but runs individual `wget` calls.
 - Skips existing files (checks with and without .svs extension).
 - Writes per-download logs to OUTDIR/.logs
 - Prints concise progress messages.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download GTEx WSI files using wget")
    p.add_argument(
        "-c",
        "--concurrency",
        type=int,
        default=4,
        help="number of parallel wget processes (default: 4)",
    )
    p.add_argument(
        "-o", "--outdir", default="./breast_wsi_downloads", help="output directory"
    )
    p.add_argument(
        "-u",
        "--urlfile",
        default="breast_wsi_urls.txt",
        help="file with list of WSI URLs (one per line)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="show which files would be downloaded and which skipped",
    )
    p.add_argument(
        "--no-skip-existing",
        dest="skip_existing",
        action="store_false",
        help="do not skip existing files",
    )
    p.add_argument(
        "--sequential",
        action="store_true",
        help="download files one-by-one and display wget progress for each (no concurrency)",
    )
    p.add_argument(
        "--use-aria",
        action="store_true",
        help="use aria2c (if available) to download URLs (aria2c must be on PATH)",
    )
    return p.parse_args()


def check_wget_exists() -> None:
    if (
        subprocess.run(
            ["which", "wget"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode
        != 0
    ):
        print(
            "Error: `wget` is not available on PATH. Please install wget and retry.",
            file=sys.stderr,
        )
        sys.exit(2)


def find_aria() -> str | None:
    """Return path to aria2c if available, otherwise None."""
    try:
        p = subprocess.run(
            ["which", "aria2c"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
        )
        path = p.stdout.decode().strip()
        return path if path else None
    except Exception:
        return None


def load_urls(path: Path) -> List[str]:
    if not path.exists():
        print(f"Missing URL file: {path}", file=sys.stderr)
        sys.exit(2)
    raw = path.read_text(encoding="utf-8", errors="ignore")
    lines = [l.strip() for l in raw.splitlines()]
    urls = [l for l in lines if l and not l.startswith("#")]
    return urls


def file_already_exists(outdir: Path, basename: str) -> bool:
    # check with and without .svs extension
    cand1 = outdir / basename
    cand2 = outdir / (basename + ".svs")
    return cand1.exists() or cand2.exists()


def wget_download(
    url: str, outdir: Path, log_dir: Path, stream: bool = False
) -> tuple[str, int]:
    """Run wget for a single URL. Returns (name, returncode).

    If stream=True the wget output is streamed to the terminal and also written to the
    per-file log using `tee` (shell). If stream=False the wget output is captured to the
    log file and not printed (clean concurrent runs).
    """
    # basename from URL (server may send different filename via content-disposition)
    name = url.rstrip("/").split("/")[-1]
    # sanitize empty name
    if not name:
        name = "download"

    log_path = log_dir / f"{name}.log"
    base_cmd = [
        "wget",
        "-c",
        "--content-disposition",
        "--trust-server-names",
        "-P",
        str(outdir),
        url,
    ]

    if stream:
        # Stream output to terminal and save to log via tee. Use a shell wrapper.
        # Quote minimal values (paths may contain spaces).
        cmd_str = (
            "wget -c --content-disposition --trust-server-names -P '"
            + str(outdir)
            + "' '"
            + url
            + "' 2>&1 | tee '"
            + str(log_path)
            + "'"
        )
        try:
            proc = subprocess.run(cmd_str, shell=True)
            return name, proc.returncode
        except Exception as e:
            with open(log_path, "wb") as fh:
                fh.write(str(e).encode("utf-8", errors="ignore"))
            return name, 3
    else:
        # Non-streaming: capture output to log file to avoid interleaving
        try:
            with open(log_path, "wb") as fh:
                proc = subprocess.run(
                    base_cmd + ["-nv"], stdout=fh, stderr=subprocess.STDOUT
                )
            return name, proc.returncode
        except Exception as e:
            with open(log_path, "wb") as fh:
                fh.write(str(e).encode("utf-8", errors="ignore"))
            return name, 3


def main() -> None:
    args = parse_args()
    check_wget_exists()
    aria_path = find_aria()
    if aria_path:
        print(f"aria2c found at: {aria_path}")
    else:
        print("aria2c not found on PATH")

    urlfile = Path(args.urlfile)
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    log_dir = outdir / ".logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    urls = load_urls(urlfile)
    if not urls:
        print("No URLs found in", urlfile)
        return

    # Filter URLs to those that need download (unless skip disabled)
    to_download = []
    skipped = []
    for url in urls:
        basename = url.rstrip("/").split("/")[-1]
        if args.skip_existing and file_already_exists(outdir, basename):
            skipped.append(basename)
        else:
            to_download.append(url)

    # If user requested aria2c and it's available, use it for the list of URLs
    if args.use_aria:
        if not aria_path:
            print(
                "--use-aria requested but aria2c was not found on PATH", file=sys.stderr
            )
            sys.exit(2)
        if not to_download:
            print("No new files to download (aria2c).")
            return
        # write urls to a temporary file and call aria2c
        import tempfile

        with tempfile.NamedTemporaryFile("w", delete=False) as tf:
            for u in to_download:
                tf.write(u + "\n")
            tmpname = tf.name

        aria_log = log_dir / "aria2c.log"
        aria_cmd = [
            "aria2c",
            "-i",
            tmpname,
            "-d",
            str(outdir),
            "-x",
            "4",
            "-s",
            "4",
            "-j",
            str(max(1, args.concurrency)),
            "--auto-file-renaming=false",
            "--continue",
            "--content-disposition=true",
        ]
        print(
            f"Using aria2c to download {len(to_download)} files (concurrency={args.concurrency})"
        )
        with open(aria_log, "wb") as fh:
            proc = subprocess.run(aria_cmd, stdout=fh, stderr=subprocess.STDOUT)
        print(f"aria2c exit code: {proc.returncode}; see {aria_log}")
        # cleanup tmp file
        try:
            os.unlink(tmpname)
        except Exception:
            pass
        return

    if args.dry_run:
        print("Dry run:")
        print("  Outdir:", outdir)
        if skipped:
            print("\n  Skipped (already exist):")
            for s in skipped:
                print("   -", s)
        if to_download:
            print("\n  Would download:")
            for u in to_download:
                print("   -", u)
        else:
            print("\n  Nothing to download.")
        return

    total = len(to_download)
    print(f"Starting downloads: {total} file(s) (concurrency={args.concurrency})")

    results = []
    # Sequential mode: stream progress for each wget and run one-by-one
    if args.sequential or args.concurrency <= 1:
        print("Sequential mode: streaming wget progress for each file")
        for i, url in enumerate(to_download, 1):
            name = url.rstrip("/").split("/")[-1]
            name, code = wget_download(url, outdir, log_dir, stream=True)
            if code == 0:
                print(f"[{i}/{total}] Downloaded: {name}")
                results.append((name, True, code))
            else:
                print(
                    f"[{i}/{total}] Failed: {name} (exit {code}) - see {log_dir / (name + '.log')}"
                )
                results.append((name, False, code))
    else:
        # Use ThreadPoolExecutor to run wget processes in parallel (non-streaming)
        with ThreadPoolExecutor(max_workers=max(1, args.concurrency)) as exe:
            future_to_url = {
                exe.submit(wget_download, url, outdir, log_dir, False): url
                for url in to_download
            }
            for i, fut in enumerate(as_completed(future_to_url), 1):
                url = future_to_url[fut]
                try:
                    name, code = fut.result()
                except Exception as e:
                    name = url.rstrip("/").split("/")[-1]
                    code = 3
                    print(f"[{i}/{total}] ERROR {name}: {e}")
                    results.append((name, False, code))
                    continue

                if code == 0:
                    print(f"[{i}/{total}] Downloaded: {name}")
                    results.append((name, True, code))
                else:
                    print(
                        f'[{i}/{total}] Failed: {name} (exit {code}) - see {log_dir / (name + ".log")}'
                    )
                    results.append((name, False, code))

    # Summary
    succ = sum(1 for _, ok, _ in results if ok)
    fail = sum(1 for _, ok, _ in results if not ok)
    print("\nSummary:")
    print("  Total attempted:", total)
    print("  Successful:", succ)
    print("  Failed:", fail)
    if skipped:
        print("  Skipped (already present):", len(skipped))


if __name__ == "__main__":
    main()
