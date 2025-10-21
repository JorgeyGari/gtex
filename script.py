import pandas as pd
import re
from pathlib import Path

# Read the CSV downloaded from GTEx Portal histologyPage
csv_path = Path("GTEx_Portal.csv")
if not csv_path.exists():
    raise FileNotFoundError(f"CSV not found: {csv_path.resolve()}")

df = pd.read_csv(csv_path)

# Display column names to understand structure
print("CSV Columns:")
print(df.columns.tolist())
print(f"\nTotal rows: {len(df)}")

# Try to detect the tissue column (some CSVs use 'Tissue', others 'Tissue Type')
tissue_col_candidates = [
    "Tissue Type",
    "Tissue",
]
tissue_col = next((c for c in tissue_col_candidates if c in df.columns), None)
if tissue_col is None:
    # broader heuristic search
    tissue_col = next(
        (c for c in df.columns if re.search(r"^tissue(\s|_|-)?(type)?$", c, re.I)), None
    )

if tissue_col is None:
    raise KeyError(
        "Could not find a tissue column (expected one of: 'Tissue Type', 'Tissue')."
    )

# Filter for breast/mammary tissue
breast_mask = (
    df[tissue_col].astype(str).str.contains(r"Mammary|Breast", case=False, na=False)
)
breast_df = df[breast_mask].copy()

print(f"\nBreast/Mammary tissue samples found: {len(breast_df)}")

if breast_df.empty:
    print(
        "No rows matched 'Breast' or 'Mammary' in the detected tissue column. Exiting without writing files."
    )
    raise SystemExit(0)

# Detect an ID column that looks like a GTEx sample/specimen ID
id_col_candidates = [
    "Specimen ID",
    "Tissue Sample ID",
    "Sample ID",
    "Sample",
]
id_col = next((c for c in id_col_candidates if c in breast_df.columns), None)
if id_col is None:
    # heuristic: any column that has values like GTEX-XXXXX-XXXX
    pattern = re.compile(r"^GTEX-[A-Z0-9]{4,}-[A-Z0-9]{2,}$", re.I)
    for c in breast_df.columns:
        vals = breast_df[c].astype(str).head(50).tolist()
        if any(pattern.search(v) for v in vals):
            id_col = c
            break

if id_col is None:
    raise KeyError(
        "Could not find a specimen/sample ID column (tried common variants and heuristics)."
    )

specimen_ids = (
    breast_df[id_col]
    .astype(str)
    .str.extract(r"(GTEX-[A-Z0-9\-]+)", expand=False)
    .dropna()
    .unique()
    .tolist()
)

print(f"Detected ID column: {id_col}")
print(f"Unique specimen/sample IDs extracted: {len(specimen_ids)}")

# Construct SVS download URLs
# NOTE: This base URL may need adjustment depending on the BRD download API.
base_url = "https://brd.nci.nih.gov/brd/imagedownload/"

urls = [f"{base_url}{sid}" for sid in specimen_ids]

# Save URLs to text file for wget
out_urls = Path("breast_wsi_urls.txt")
with out_urls.open("w") as f:
    for url in urls:
        f.write(url + "\n")

print(f"\nSaved {len(urls)} URLs to {out_urls.resolve()}")

# Optional: Save filtered metadata
out_meta = Path("breast_mammary_metadata.csv")
breast_df.to_csv(out_meta, index=False)
print(f"Saved filtered metadata to {out_meta.resolve()}")
