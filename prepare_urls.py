#!/usr/bin/env python3
"""
prepare_urls.py

Generate download URL lists from GTEx portal CSV exports.

Provides a function to extract GTEx specimen IDs for breast/mammary female samples
and write a `breast_wsi_urls.txt` file (or custom paths).

This is a refactor of the old `script.py` to make it importable from `main.py`.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional


def generate_gtex_urls(
    csv_path: Path | str = "GTEx_Portal.csv",
    out_urls: Path | str = "breast_wsi_urls.txt",
    out_meta: Path | str = "breast_mammary_metadata.csv",
    max_ids: Optional[int] = None,
) -> List[str]:
    """Read GTEx CSV and write a list of download URLs.

    Returns the list of URLs written.
    """
    try:
        import pandas as pd
    except Exception as e:
        raise RuntimeError(
            "pandas is required to run this function: pip install pandas"
        ) from e

    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV not found: {csv_path.resolve()}")

    df = pd.read_csv(csv_path)

    # Detect tissue column
    tissue_col_candidates = ["Tissue Type", "Tissue"]
    tissue_col = next((c for c in tissue_col_candidates if c in df.columns), None)
    if tissue_col is None:
        tissue_col = next(
            (c for c in df.columns if re.search(r"^tissue(\s|_|-)?(type)?$", c, re.I)),
            None,
        )

    if tissue_col is None:
        raise KeyError(
            "Could not find a tissue column (expected one of: 'Tissue Type', 'Tissue')."
        )

    breast_mask = (
        df[tissue_col].astype(str).str.contains(r"Mammary|Breast", case=False, na=False)
    )
    breast_df = df[breast_mask].copy()

    if breast_df.empty:
        raise SystemExit("No breast/mammary rows found in CSV")

    # Filter by female
    sex_col_candidates = ["Sex", "Gender"]
    sex_col = next((c for c in sex_col_candidates if c in breast_df.columns), None)
    if sex_col is None:
        sex_col = next(
            (c for c in breast_df.columns if re.search(r"^sex$|^gender$", c, re.I)),
            None,
        )

    if sex_col is None:
        raise KeyError("Could not find a sex column (expected 'Sex' or 'Gender').")

    female_mask = (
        breast_df[sex_col]
        .astype(str)
        .str.strip()
        .str.match(r"(?i)^(f|female|fem)$", na=False)
    )
    breast_df = breast_df[female_mask].copy()
    if breast_df.empty:
        raise SystemExit("No female breast/mammary samples found.")

    # Find ID column
    id_col_candidates = ["Specimen ID", "Tissue Sample ID", "Sample ID", "Sample"]
    id_col = next((c for c in id_col_candidates if c in breast_df.columns), None)
    if id_col is None:
        pattern = re.compile(r"^GTEX-[A-Z0-9]{4,}-[A-Z0-9]{2,}$", re.I)
        for c in breast_df.columns:
            vals = breast_df[c].astype(str).head(50).tolist()
            if any(pattern.search(v) for v in vals):
                id_col = c
                break

    if id_col is None:
        raise KeyError("Could not find a specimen/sample ID column.")

    specimen_ids = (
        breast_df[id_col]
        .astype(str)
        .str.extract(r"(GTEX-[A-Z0-9\-]+)", expand=False)
        .dropna()
        .unique()
        .tolist()
    )

    if max_ids:
        specimen_ids = specimen_ids[: max(0, int(max_ids))]

    base_url = "https://brd.nci.nih.gov/brd/imagedownload/"
    urls = [f"{base_url}{sid}" for sid in specimen_ids]

    out_urls = Path(out_urls)
    out_urls.write_text("\n".join(urls) + ("\n" if urls else ""))

    out_meta = Path(out_meta)
    breast_df.to_csv(out_meta, index=False)

    return urls


def main():
    import argparse

    p = argparse.ArgumentParser(description="Generate GTEx WSI URL list from CSV")
    p.add_argument("--csv", default="GTEx_Portal.csv", help="GTEx CSV export path")
    p.add_argument("--out-urls", default="breast_wsi_urls.txt", help="Output URL list")
    p.add_argument(
        "--out-meta",
        default="breast_mammary_metadata.csv",
        help="Filtered metadata CSV",
    )
    p.add_argument(
        "--max", type=int, default=0, help="Limit number of specimen IDs (0 = no limit)"
    )
    args = p.parse_args()

    max_ids = args.max if args.max and args.max > 0 else None
    urls = generate_gtex_urls(args.csv, args.out_urls, args.out_meta, max_ids=max_ids)
    print(f"Wrote {len(urls)} URLs to {args.out_urls}")


if __name__ == "__main__":
    main()
