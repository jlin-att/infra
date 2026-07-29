#!/usr/bin/env python3
"""
Process a "USP Evolution - 172M" sheet from an xlsx file.

Sheet layout:
  - Row 23: site names, starting at column E. Each site name spans the columns
    that make up its block (typically merged across its header group).
  - Column B: "Network Element" (row label).
  - Row 24: headers, starting at column E. The header group
    (vCPU, Memory (GiB), Root Disk (GB), Cinder (DB)) repeats for each site.
  - Row 25+: data.

The script lists all sites, prompts the user to choose one, then prints that
site's data in CSV format with headers:
  Network Element, vCPU, Memory (GiB), Root Disk (GB), Cinder (DB)
"""

import argparse
import csv
import os
import re
import sys

from openpyxl import load_workbook

SHEET_NAME = "USP Evolution - 172M"
SITE_ROW = 23          # site names
HEADER_ROW = 24        # per-site headers
DATA_START_ROW = 25    # first data row
NE_COL = 2             # column B = Network Element
FIRST_DATA_COL = 5     # column E = first header/site column

# Wanted headers (order preserved for output). Matched case-insensitively.
WANTED_HEADERS = ["vCPU", "Memory (GiB)", "Root Disk (GB)", "Cinder (GB)"]
OUTPUT_HEADERS = ["Network Element"] + WANTED_HEADERS


def norm(v):
    """Normalize a cell value to a stripped string ('' for None).

    Floats are limited to 2 decimal places, with trailing zeros/decimal
    point trimmed (e.g. 30.0 -> '30', 30.5 -> '30.5', 30.567 -> '30.57').
    """
    if v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return str(v).strip()


def is_zero_or_empty(s):
    """True if a normalized string is empty or numerically zero."""
    if s == "":
        return True
    try:
        return float(s) == 0.0
    except ValueError:
        return False


def build_merged_lookup(ws):
    """Map each cell coordinate covered by a merged range to the top-left value."""
    lookup = {}
    for mr in ws.merged_cells.ranges:
        top_left = ws.cell(row=mr.min_row, column=mr.min_col).value
        for row in range(mr.min_row, mr.max_row + 1):
            for col in range(mr.min_col, mr.max_col + 1):
                lookup[(row, col)] = top_left
    return lookup


def cell_value(ws, merged, row, col):
    """Get a cell value, resolving merged cells to their top-left value."""
    if (row, col) in merged:
        return merged[(row, col)]
    return ws.cell(row=row, column=col).value


def discover_sites(ws, merged, max_col):
    """
    Find each site block.

    Returns a list of dicts:
      { "name": <site>, "start_col": c, "cols": { header_lower: col_index } }
    A new site block starts at each column in SITE_ROW that has a (non-inherited)
    site name in the raw cell, i.e. the top-left of its merged range.
    """
    sites = []

    # Columns where a site name actually begins (top-left of merge, or a plain cell).
    start_cols = []
    for col in range(FIRST_DATA_COL, max_col + 1):
        raw = ws.cell(row=SITE_ROW, column=col).value  # raw, not merge-resolved
        if norm(raw):
            start_cols.append((col, norm(raw)))

    if not start_cols:
        return sites

    # Determine each block's column span (up to the next site start).
    for idx, (start_col, name) in enumerate(start_cols):
        end_col = start_cols[idx + 1][0] - 1 if idx + 1 < len(start_cols) else max_col

        header_cols = {}
        for col in range(start_col, end_col + 1):
            hdr = norm(cell_value(ws, merged, HEADER_ROW, col))
            if hdr:
                header_cols[hdr.lower()] = col

        sites.append({"name": name, "start_col": start_col, "cols": header_cols})

    return sites


def choose_site(sites):
    """Display the site list and prompt the user to pick one."""
    print("Available sites:", file=sys.stderr)
    for i, s in enumerate(sites, 1):
        print(f"  {i}. {s['name']}", file=sys.stderr)

    while True:
        try:
            choice = input("Select a site by number: ").strip()
        except EOFError:
            sys.exit("\nNo selection made.")
        if choice.isdigit() and 1 <= int(choice) <= len(sites):
            return sites[int(choice) - 1]
        print(f"Please enter a number between 1 and {len(sites)}.", file=sys.stderr)


def extract_site_rows(ws, merged, site, max_row):
    """Yield [Network Element, vCPU, Memory, Root Disk, Cinder] for each data row."""
    # Resolve the column for each wanted header (case-insensitive).
    col_map = []
    for hdr in WANTED_HEADERS:
        col = site["cols"].get(hdr.lower())
        if col is None:
            print(f"WARNING: header '{hdr}' not found for site '{site['name']}'; "
                  f"values will be blank.", file=sys.stderr)
        col_map.append(col)

    for row in range(DATA_START_ROW, max_row + 1):
        ne = norm(cell_value(ws, merged, row, NE_COL))
        values = ["" if col is None else norm(cell_value(ws, merged, row, col))
                  for col in col_map]
        # Skip rows with no Network Element label, or where every value
        # (all but Network Element) is empty or 0. Do NOT stop early — a blank
        # or all-zero row in the middle should be skipped, not treated as the end.
        if not ne:
            continue
        if all(is_zero_or_empty(v) for v in values):
            continue
        yield [ne] + values


def main():
    ap = argparse.ArgumentParser(description="Extract a site's data from the "
                                             "'USP Evolution - 172M' sheet.")
    ap.add_argument("xlsx", help="Path to the input .xlsx file")
    ap.add_argument("--sheet", default=SHEET_NAME,
                    help=f"Sheet name (default: '{SHEET_NAME}')")
    ap.add_argument("-o", "--output",
                    help="Write CSV to this file instead of stdout. If given a "
                         "value of 'auto' (or just the flag with no value), the "
                         "filename is derived from the input file and chosen "
                         "site, e.g. '<input>-<SITE>.csv'.",
                    nargs="?", const="auto", default=None)
    args = ap.parse_args()

    wb = load_workbook(args.xlsx, data_only=True)
    if args.sheet not in wb.sheetnames:
        sys.exit(f"ERROR: sheet '{args.sheet}' not found. "
                 f"Available: {', '.join(wb.sheetnames)}")
    ws = wb[args.sheet]

    merged = build_merged_lookup(ws)
    max_col, max_row = ws.max_column, ws.max_row

    sites = discover_sites(ws, merged, max_col)
    if not sites:
        sys.exit("ERROR: no site names found in row 23 (from column E onward).")

    site = choose_site(sites)
    rows = list(extract_site_rows(ws, merged, site, max_row))

    if args.output is None:
        # No file requested -> print to stdout as before.
        writer = csv.writer(sys.stdout)
        writer.writerow(OUTPUT_HEADERS)
        writer.writerows(rows)
        return

    # Resolve output path.
    if args.output == "auto":
        base = os.path.splitext(args.xlsx)[0]
        safe_site = re.sub(r"[^\w.-]+", "_", site["name"]).strip("_")
        out_path = f"{base}-{safe_site}.csv"
    else:
        out_path = args.output

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(OUTPUT_HEADERS)
        writer.writerows(rows)

    print(f"Wrote {len(rows)} row(s) for site '{site['name']}' to: {out_path}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
