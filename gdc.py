#!/usr/bin/env python3
"""
Download all TCGA-BRCA Whole Slide Images using gdc-api-wrapper
"""

import argparse
import requests
import json
import os
import sys

# Configuration
OUTPUT_DIR = "./tcga_brca_slides"
BATCH_SIZE = 10  # Number of files to download at a time


def query_tcga_brca_slides():
    """Query GDC API for all TCGA-BRCA slide images"""

    files_endpt = "https://api.gdc.cancer.gov/files"

    # Build filter for TCGA-BRCA slide images
    filters = {
        "op": "and",
        "content": [
            {
                "op": "=",
                "content": {
                    "field": "cases.project.project_id",
                    "value": ["TCGA-BRCA"],
                },
            },
            {"op": "=", "content": {"field": "data_type", "value": ["Slide Image"]}},
        ],
    }

    params = {
        "filters": json.dumps(filters),
        "fields": "file_id,file_name,file_size",
        "format": "JSON",
        "size": "10000",  # Adjust if more than 10k files
    }

    print("Querying GDC API for TCGA-BRCA slide images...")
    response = requests.get(files_endpt, params=params)

    if response.status_code != 200:
        raise Exception(f"API request failed: {response.status_code}")

    data = response.json()
    files = data["data"]["hits"]

    print(f"Found {len(files)} slide images")
    return files


def download_slides(files, output_dir=OUTPUT_DIR, overwrite=False):
    """Download all slide images using gdc-api-wrapper"""

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # lazy import to allow --dry-run without having the wrapper installed
    try:
        from gdcapiwrapper.tcga import Data
    except ImportError:
        raise ImportError(
            "gdcapiwrapper is required to download files.\n"
            "Install it in your environment, for example: `pip install gdc-api-wrapper`"
        )

    total = len(files)

    for idx, file_info in enumerate(files, 1):
        file_id = file_info["file_id"]
        file_name = file_info["file_name"]
        file_size = file_info.get("file_size", 0) / (1024**3)  # Convert to GB

        print(f"\n[{idx}/{total}] Downloading: {file_name}")
        print(f"  File ID: {file_id}")
        print(f"  Size: {file_size:.2f} GB")

        # Check if file already exists
        output_path = os.path.join(output_dir, file_name)
        if os.path.exists(output_path) and not overwrite:
            print(f"  ✓ Already downloaded, skipping...")
            continue
        if os.path.exists(output_path) and overwrite:
            print(f"  ! File exists but --overwrite set: removing existing file")
            try:
                os.remove(output_path)
            except Exception as e:
                print(f"  ✗ Failed to remove existing file: {e}")
                continue

        try:
            # Download using gdc-api-wrapper
            Data.download(uuid=file_id, path=output_dir, name=file_name)
            print(f"  ✓ Download complete")
        except Exception as e:
            print(f"  ✗ Download failed: {str(e)}")
            continue


def download_slides_batch(files, output_dir=OUTPUT_DIR, overwrite=False):
    """Alternative: Download slides in batches using download_multiple"""

    os.makedirs(output_dir, exist_ok=True)

    # lazy import so dry-run doesn't require the package
    try:
        from gdcapiwrapper.tcga import Data
    except ImportError:
        raise ImportError(
            "gdcapiwrapper is required to download files.\n"
            "Install it in your environment, for example: `pip install gdc-api-wrapper`"
        )

    file_ids = [f["file_id"] for f in files]
    total = len(file_ids)

    print(f"\nDownloading {total} files in batches of {BATCH_SIZE}...")

    for i in range(0, total, BATCH_SIZE):
        batch = file_ids[i : i + BATCH_SIZE]
        batch_num = (i // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        print(
            f"\n[Batch {batch_num}/{total_batches}] Downloading {len(batch)} files..."
        )

        try:
            response, filename = Data.download_multiple(
                uuid_list=batch, path=output_dir
            )
            print(f"  ✓ Batch downloaded: {filename}")
            print(
                f"  Note: Files are in a compressed archive, you'll need to extract them"
            )
        except Exception as e:
            print(f"  ✗ Batch download failed: {str(e)}")
            continue


def main():
    parser = argparse.ArgumentParser(
        description="Download TCGA-BRCA Whole Slide Images (uses gdc-api-wrapper for downloads)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Query GDC and report counts/sizes without downloading",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Assume yes for prompts (non-interactive)",
    )
    parser.add_argument(
        "--method",
        choices=["1", "2"],
        help="Select download method non-interactively: 1=individual, 2=batch",
    )
    parser.add_argument(
        "--preview",
        type=int,
        default=10,
        help="Show the first N files when doing a dry-run (default: 10)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("TCGA-BRCA Whole Slide Images Downloader")
    print("=" * 60)

    # Query for files
    files = query_tcga_brca_slides()

    # Calculate total size
    total_size_gb = sum(f.get("file_size", 0) for f in files) / (1024**3)
    print(f"\nTotal download size: {total_size_gb:.2f} GB")
    print(f"Output directory: {OUTPUT_DIR}")

    if args.dry_run:
        # Show a small preview of files
        n = max(0, args.preview)
        print(f"\nDry run: showing first {n} files (name — size MB):\n")
        for i, f in enumerate(files[:n], 1):
            size_mb = f.get("file_size", 0) / (1024**2)
            print(f"[{i}] {f.get('file_name')} — {size_mb:.2f} MB")
        print(f"\nFound {len(files)} files totaling {total_size_gb:.2f} GB")
        return

    # Ask user to confirm (unless -y supplied)
    if not args.yes:
        user_input = input("\nProceed with download? (y/n): ")
        if user_input.lower() != "y":
            print("Download cancelled")
            return

    # Choose download method
    method = args.method
    if not method:
        print("\nDownload methods:")
        print("1. Individual files (recommended, allows resume)")
        print("2. Batch download (faster but files come in .tar.gz archives)")
        method = input("Select method (1 or 2): ")

    if method == "2":
        download_slides_batch(files)
    else:
        download_slides(files)

    print("\n" + "=" * 60)
    print("Download complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
