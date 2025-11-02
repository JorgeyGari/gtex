#!/usr/bin/env python3
"""
main.py

Interactive pipeline orchestrator:
 - prepare GTEx URL list (uses prepare_urls.py)
 - run gtex downloader (gtex.py)
 - run GDC downloader (gdc.py)

This script asks the user which portals to run, limits, and output directories.
It then executes the chosen steps using the local scripts.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List


def ask_choices(prompt: str, choices: List[str]) -> List[str]:
    print(prompt)
    for i, c in enumerate(choices, 1):
        print(f"  {i}. {c}")
    sel = input(
        "Select numbers separated by comma (e.g. 1,2) or press Enter for none: "
    )
    if not sel.strip():
        return []
    out = []
    for part in sel.split(","):
        p = part.strip()
        if not p:
            continue
        try:
            idx = int(p) - 1
            if 0 <= idx < len(choices):
                out.append(choices[idx])
        except ValueError:
            # allow matching by name
            if p in choices:
                out.append(p)
    return out


def run_prepare_gtex(csv_path: str, max_images: int, out_urls: str, out_meta: str):
    """Generate GTEx URL list. Prefer in-process run using prepare_urls.generate_gtex_urls
    so we can avoid creating a persistent urls file when the user only requests a small
    number of images. Returns (urlfile_path, cleanup_temp_bool).
    """
    # If user requested a limited number of images and didn't ask for a specific
    # persistent out_urls path, generate URLs in-memory and write to a temp file.
    try:
        max_n = int(max_images)
    except Exception:
        max_n = 0

    default_out = "breast_wsi_urls.txt"
    if max_n > 0 and out_urls == default_out:
        # generate in-process and write to a temporary file
        import tempfile

        from prepare_urls import generate_gtex_urls

        with tempfile.NamedTemporaryFile("w", delete=False) as tf_urls:
            tmp_urls = tf_urls.name
        # also create a temp metadata path
        with tempfile.NamedTemporaryFile("w", delete=False) as tf_meta:
            tmp_meta = tf_meta.name

        print(f"Generating {max_n} GTEx URLs in-memory (temp file: {tmp_urls})...")
        urls = generate_gtex_urls(csv_path, tmp_urls, tmp_meta, max_ids=max_n)
        # return the temp urls path and mark it for cleanup
        return tmp_urls, True
    else:
        # call prepare_urls.py as a subprocess and keep the out_urls path as requested
        # Use absolute script path so main.py works regardless of current working dir
        script_dir = Path(__file__).parent
        prepare_script = str(script_dir / "prepare_urls.py")
        cmd = [
            sys.executable,
            prepare_script,
            "--csv",
            csv_path,
            "--out-urls",
            out_urls,
            "--out-meta",
            out_meta,
        ]
        if max_n and max_n > 0:
            cmd += ["--max", str(max_n)]
        print("Running:", " ".join(cmd))
        subprocess.run(cmd, check=True)
        return out_urls, False


def run_gtex(urlfile: str, outdir: str, concurrency: int, sequential: bool):
    script_dir = Path(__file__).parent
    gtex_script = str(script_dir / "gtex.py")
    cmd = [
        sys.executable,
        gtex_script,
        "-u",
        urlfile,
        "-o",
        outdir,
        "-c",
        str(concurrency),
    ]
    if sequential:
        cmd += ["--sequential"]
    print("Running gtex downloader:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def run_gdc(dry_run: bool, yes: bool, max_images: int):
    """Run gdc.py with optional limit on number of images to download.

    max_images: 0 means no limit (download all)
    """
    script_dir = Path(__file__).parent
    gdc_script = str(script_dir / "gdc.py")
    cmd = [sys.executable, gdc_script]
    if dry_run:
        cmd += ["--dry-run"]
    if yes:
        cmd += ["-y"]
    # pass max images limit to gdc.py if > 0
    try:
        max_n = int(max_images)
    except Exception:
        max_n = 0
    if max_n and max_n > 0:
        cmd += ["--max", str(max_n)]
    print("Running GDC script:", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main():
    print("GTEx/GDC pipeline orchestrator")
    print("This will run local scripts: prepare_urls.py, gtex.py, gdc.py")

    choices = ["GTEx", "GDC"]
    selected = ask_choices("Which portals do you want to use?", choices)
    if not selected:
        print("No portals selected, exiting.")
        return

    if "GTEx" in selected:
        # Normalize user-supplied paths so Windows-style and ~ work across platforms.
        def _normalize_path(p: str, default: str) -> str:
            # Accept empty input -> default
            val = (p or default).strip()
            # Expand ~ and environment variables
            val = os.path.expanduser(os.path.expandvars(val))
            try:
                # Resolve to absolute path but do not require existence
                val_path = Path(val).resolve(strict=False)
                return str(val_path)
            except Exception:
                return val

        csv_path_raw = input("GTEx CSV path [GTEx_Portal.csv]: ") or "GTEx_Portal.csv"
        csv_path = _normalize_path(csv_path_raw, "GTEx_Portal.csv")
        max_images = input("Max number of images to include (0 = all) [0]: ") or "0"
        out_urls_raw = (
            input("URL list output file [breast_wsi_urls.txt]: ")
            or "breast_wsi_urls.txt"
        )
        out_urls = _normalize_path(out_urls_raw, "breast_wsi_urls.txt")
        out_meta_raw = (
            input("Filtered metadata output file [breast_mammary_metadata.csv]: ")
            or "breast_mammary_metadata.csv"
        )
        out_meta = _normalize_path(out_meta_raw, "breast_mammary_metadata.csv")
        outdir_raw = (
            input("Download directory for GTEx images [./breast_wsi_downloads]: ")
            or "./breast_wsi_downloads"
        )
        outdir = _normalize_path(outdir_raw, "./breast_wsi_downloads")
        concurrency = input("gtex concurrency (-c) [4]: ") or "4"
        sequential = (
            input("Run sequentially and show progress? (y/N): ").lower().strip() == "y"
        )

        # Run prepare step and get urlfile path (may be a temp file)
        urlfile, cleanup = run_prepare_gtex(
            csv_path, int(max_images), out_urls, out_meta
        )

        try:
            # Run downloader with the produced urlfile
            run_gtex(urlfile, outdir, int(concurrency), sequential)
        finally:
            # cleanup temporary url/meta files if we created them
            if cleanup:
                try:
                    os.unlink(urlfile)
                    print(f"Removed temporary URL file: {urlfile}")
                except Exception:
                    pass

    if "GDC" in selected:
        dr = input("GDC: run dry-run to preview files only? (Y/n): ")
        dry_run = not (dr.strip().lower() == "n")
        yes = False
        if not dry_run:
            y = input("Proceed non-interactively with downloads? (y/N): ")
            yes = y.strip().lower() == "y"
        # Ask for a max number of images (0 = all) — normalize numeric input
        max_images = (
            input("Max number of images to download from GDC (0 = all) [0]: ") or "0"
        )
        try:
            max_n = int(max_images)
        except Exception:
            max_n = 0
        run_gdc(dry_run=dry_run, yes=yes, max_images=max_n)

    print("Pipeline finished.")


if __name__ == "__main__":
    main()
