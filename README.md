(Project README)

This repo helps generate download URLs for GTEx breast/mammary whole-slide images (WSIs) and download them.

Quick start

1. Clone the repo

	git clone <repo-url>
	cd gtex

2. Create a virtual environment and install Python deps

	python3 -m venv .venv
	source .venv/bin/activate
	pip install -r requirements.txt

3. Generate the URL list

	# the repository includes `GTEx_Portal.csv` downloaded from GTEx histology page
	# run the provided script to filter breast samples and create `breast_wsi_urls.txt`
	.venv/bin/python script.py


4. Download the WSIs

	# default concurrency 4, default outdir ./breast_wsi_downloads
	chmod +x download_wsi.py
	
	# Usage: ./download_wsi.py [--concurrency N] [--outdir DIR]
	./download_wsi.py --concurrency 4 --outdir ./breast_wsi_downloads

	# Dry run (show what would be downloaded, don't actually fetch files)
	./download_wsi.py --dry-run

	# Example: specify a custom directory
	./download_wsi.py --concurrency 8 --outdir /data/gtex_wsis

The downloader prefers `aria2c` (if installed) for faster segmented downloads. Otherwise it falls back to `xargs + wget`. There's also a simple Python fallback.

Windows users

This repository now focuses on POSIX-compatible shell usage via `download_wsi.sh` (Linux/macOS). If you're on Windows, run the shell script under WSL, Git Bash, or similar environments. The previous PowerShell downloader was removed to simplify maintenance.

Files of interest
- `script.py` — filters `GTEx_Portal.csv` and writes `breast_wsi_urls.txt` and `breast_mammary_metadata.csv`.
- `breast_wsi_urls.txt` — the URL list used by the downloader.
- `download_wsi.sh` — convenience downloader (aria2c preferred, fallback to xargs+wget or a Python downloader).
- `requirements.txt` — Python runtime deps for the helper script.

Notes
- The downloaded WSIs are stored in `breast_wsi_downloads/` (this directory is gitignored).
- **Downloaded files will have the `.svs` extension** (Aperio ScanScope Virtual Slide format, which is TIFF-based).
- The download scripts now properly handle the `Content-Disposition` header from the server to preserve the correct filename.
- The script expects `GTEx_Portal.csv` to be present in the repository root. If you downloaded a fresh CSV with different column names, edit `script.py` to match the tissue and sample ID columns or open an issue.

## Recent Bug Fixes

**File Extension Issue (Fixed Nov 2025):** 
Previously downloaded files were missing the `.svs` extension. This has been fixed:
- `download_wsi.sh` now uses `--content-disposition` (aria2/wget) to get filenames from the server
- All active download methods now correctly save files with `.svs` extension
- If you have old files without extensions, you can rename them: `mv GTEX-XXXXX-XXXX GTEX-XXXXX-XXXX.svs`

See `BUGFIX_SUMMARY.md` for detailed information about the fix.

QuickStart one-liners

Linux / macOS (single line; concurrency 4):

```bash
git clone <repo-url> && cd gtex && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && .venv/bin/python script.py && chmod +x download_wsi.sh && ./download_wsi.sh 4
```


