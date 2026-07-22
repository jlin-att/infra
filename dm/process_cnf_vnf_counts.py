#!/usr/bin/env python3
"""
Process a CNF/VNF counts XLSX file and export a flat CSV.

Sheet layout (sheet name: "CNF VNF Counts - 172M"):
  - Row 23              : "sites" header row. Site names start at column E and
                          continue to the right for as many columns as exist.
  - Column A (row 25+)  : "group". These are merged cells that span multiple
                          rows, so the value is forward-filled down the rows.
                          The same group may legitimately reappear later.
  - Column B (row 25+)  : Network Element name.
  - Column C (row 25+)  : cnf-vnf.
  - Column D (row 25+)  : subs.
  - Columns E.. (row 25+): the count for each site. Non-numeric cells -> 0.

Output CSV columns:
  row, group, network element, cnf-vnf, subs, <site 1>, <site 2>, ...
  ("row" is the 1-based source row number in the input sheet.)

Usage:
  python process_cnf_vnf_counts.py <input.xlsx> [-o output.csv]

Default output is written next to the input file as
  <input base name>-cnf-vnf-counts.csv
"""

import argparse
import csv
import os
import sys

import openpyxl

SHEET_NAME = "CNF VNF Counts - 172M"
HEADER_ROW = 23          # row that holds the site names
DATA_START_ROW = 25      # first row of network-element data
FIRST_SITE_COL = 5       # column E (1-based)
GROUP_COL = 1            # column A
NE_COL = 2               # column B
CNFVNF_COL = 3           # column C
SUBS_COL = 4             # column D


def to_count(value):
    """Return an integer count. Non-numeric / blank cells become 0."""
    if value is None:
        return 0
    # Already a real number in the cell.
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    # String cell: keep it only if it is a clean integer/float.
    text = str(value).strip()
    if not text:
        return 0
    try:
        # Handle things like "12" and "12.0" but reject "N/A", "-", etc.
        return int(float(text))
    except ValueError:
        return 0


def clean(value):
    """Normalize a text cell for output."""
    if value is None:
        return ""
    return str(value).strip()


def main():
    parser = argparse.ArgumentParser(
        description="Flatten the CNF/VNF site counts sheet into a CSV."
    )
    parser.add_argument("input", help="Path to the input .xlsx file")
    parser.add_argument(
        "-o", "--output",
        help="Path to the output .csv file "
             "(default: <input dir>/<input base name>-cnf-vnf-counts.csv)",
    )
    parser.add_argument(
        "-s", "--sheet", default=SHEET_NAME,
        help=f'Sheet name to read (default: "{SHEET_NAME}")',
    )
    args = parser.parse_args()

    if not os.path.isfile(args.input):
        sys.exit(f"ERROR: input file not found: {args.input}")

    output = args.output
    if not output:
        in_dir = os.path.dirname(os.path.abspath(args.input))
        base = os.path.splitext(os.path.basename(args.input))[0]
        output = os.path.join(in_dir, f"{base}-cnf-vnf-counts.csv")

    wb = openpyxl.load_workbook(args.input, data_only=True)
    if args.sheet not in wb.sheetnames:
        sys.exit(
            f'ERROR: sheet "{args.sheet}" not found. '
            f"Available sheets: {wb.sheetnames}"
        )
    ws = wb[args.sheet]

    # --- Read the site headers from the header row (column E onward). ---
    sites = []          # list of (column_index, site_name)
    for col in range(FIRST_SITE_COL, ws.max_column + 1):
        name = clean(ws.cell(row=HEADER_ROW, column=col).value)
        if name:
            sites.append((col, name))

    if not sites:
        sys.exit(
            f"ERROR: no site headers found on row {HEADER_ROW} "
            f"starting at column {FIRST_SITE_COL}."
        )

    site_names = [name for _, name in sites]

    # --- Walk the data rows and write the CSV. ---
    last_group = ""
    rows_written = 0

    with open(output, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["row", "group", "network element", "cnf-vnf", "subs"] + site_names
        )

        for row in range(DATA_START_ROW, ws.max_row + 1):
            ne = clean(ws.cell(row=row, column=NE_COL).value)

            # Forward-fill the merged "group" cell in column A.
            group_val = clean(ws.cell(row=row, column=GROUP_COL).value)
            if group_val:
                last_group = group_val

            # Skip fully blank rows (no network element name).
            if not ne:
                continue

            cnfvnf = clean(ws.cell(row=row, column=CNFVNF_COL).value)
            subs = clean(ws.cell(row=row, column=SUBS_COL).value)

            counts = [to_count(ws.cell(row=row, column=col).value)
                      for col, _ in sites]

            writer.writerow([row, last_group, ne, cnfvnf, subs] + counts)
            rows_written += 1

    print(f"Wrote {rows_written} network-element rows across "
          f"{len(site_names)} sites to: {output}")


if __name__ == "__main__":
    main()
