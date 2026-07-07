#!/usr/bin/env python3
"""
generate-att-sku.py

Reads an xlsx file, locates a sheet whose name contains "fc-match"
(e.g. "18.1-fc-match"), and extracts specific columns into a JSON file.

Usage:
    python generate-att-sku.py <input.xlsx> [output.json]
"""

import sys
import os
import json
from openpyxl import load_workbook


# Column name -> output JSON key
COLUMN_MAP = {
    "Network Element (function code doc)": "Network Element (function code doc)",
    "ATT SKU":                             "ATT SKU",
    "config_heading (DM)":                 "dm-ne",
    "config_heading_row":                  "dm-line",
}


def norm(s):
    """Normalize a header cell for case-/whitespace-insensitive matching."""
    if s is None:
        return ""
    return " ".join(str(s).split()).strip().lower()


def find_fc_match_sheet(wb):
    """Return the first sheet name containing 'fc-match' (case-insensitive)."""
    for name in wb.sheetnames:
        if "fc-match" in name.lower():
            return name
    return None


def process_file(input_path, output_path):
    wb = load_workbook(input_path, data_only=True, read_only=True)

    sheet_name = find_fc_match_sheet(wb)
    if not sheet_name:
        print(f"ERROR: No sheet containing 'fc-match' found in {input_path}",
              file=sys.stderr)
        sys.exit(1)
    print(f"Using sheet: {sheet_name}")

    ws = wb[sheet_name]
    rows = ws.iter_rows(values_only=True)

    # Read header row
    try:
        header = next(rows)
    except StopIteration:
        print("ERROR: Sheet is empty.", file=sys.stderr)
        sys.exit(1)

    # Build normalized header -> column index map
    header_norm = {norm(h): i for i, h in enumerate(header) if h is not None}

    # Resolve required columns
    col_idx = {}
    for src_col, out_key in COLUMN_MAP.items():
        key = norm(src_col)
        if key not in header_norm:
            print(f"WARNING: Column '{src_col}' not found in header.",
                  file=sys.stderr)
            col_idx[out_key] = None
        else:
            col_idx[out_key] = header_norm[key]

    # Extract data
    results = []
    for row in rows:
        # Skip completely empty rows
        if not any(c is not None and str(c).strip() != "" for c in row):
            continue

        record = {}
        for out_key, idx in col_idx.items():
            if idx is None or idx >= len(row):
                record[out_key] = None
            else:
                val = row[idx]
                if isinstance(val, str):
                    val = val.strip()
                record[out_key] = val
        results.append(record)

    # Write JSON
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(results)} records to {output_path}")


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("Usage: python process_fc_match.py <input.xlsx> [output.json]",
              file=sys.stderr)
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.isfile(input_path):
        print(f"ERROR: File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) == 3:
        output_path = sys.argv[2]
    else:
        base, _ = os.path.splitext(input_path)
        output_path = base + "-fc-match.json"

    process_file(input_path, output_path)


if __name__ == "__main__":
    main()