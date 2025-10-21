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

	# default concurrency 4
	chmod +x download_wsi.sh
	./download_wsi.sh 4

The downloader prefers `aria2c` (if installed) for faster segmented downloads. Otherwise it falls back to `xargs + wget`. There's also a simple Python fallback.

Windows (PowerShell) instructions

1. Open PowerShell and set execution policy for the session:

	Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

2. Ensure Python is installed and create a venv (optional):

	python -m venv .venv
	.\.venv\Scripts\Activate.ps1
	pip install -r requirements.txt

3. Generate the URL list (same as above):

	.venv\Scripts\python.exe script.py

4. Download using PowerShell script (prefers aria2c if installed):

	.\download_wsi.ps1 -Concurrency 4

Notes on Windows downloader
- `download_wsi.ps1` will use `aria2c` if present. Otherwise it uses `Start-BitsTransfer` in parallel background jobs.
- If you want more advanced resumable segmented downloads on Windows, install `aria2` and the script will use it automatically.

Files of interest
- `script.py` — filters `GTEx_Portal.csv` and writes `breast_wsi_urls.txt` and `breast_mammary_metadata.csv`.
- `breast_wsi_urls.txt` — the URL list used by the downloader.
- `download_wsi.sh` — convenience downloader (aria2c preferred, fallback to xargs+wget or a Python downloader).
- `requirements.txt` — Python runtime deps for the helper script.

Notes
- The downloaded WSIs are stored in `breast_wsi_downloads/` (this directory is gitignored).
- The script expects `GTEx_Portal.csv` to be present in the repository root. If you downloaded a fresh CSV with different column names, edit `script.py` to match the tissue and sample ID columns or open an issue.

QuickStart one-liners

Linux / macOS (single line; concurrency 4):

```bash
git clone <repo-url> && cd gtex && python3 -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && .venv/bin/python script.py && chmod +x download_wsi.sh && ./download_wsi.sh 4
```

Windows PowerShell (single line; concurrency 4):

```powershell
git clone <repo-url>; cd gtex; python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt; .venv\Scripts\python.exe script.py; .\download_wsi.ps1 -Concurrency 4
```

