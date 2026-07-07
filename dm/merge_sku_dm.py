#!/usr/bin/env python3
"""
Merge SKU file into DM file by matching:
    sku["dm-line"]  ==  dm_config["config_heading_row"]

Output preserves the original DM file structure and adds an "ATT SKU"
field to each matched config entry.

Usage:
    python merge_sku_dm.py <sku.json> <dm.json> <output.json>
"""

import argparse
import json
import sys


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_sku_map(sku_data):
    """dm-line -> ATT SKU  (stringified key for safe lookup)."""
    m = {}
    for row in sku_data:
        dm_line = row.get("dm-line")
        att_sku = row.get("ATT SKU")
        if dm_line is None:
            continue
        key = str(dm_line)
        if key in m and m[key] != att_sku:
            print(f"[WARN] Duplicate dm-line={dm_line} in SKU file "
                  f"('{m[key]}' vs '{att_sku}'); keeping first",
                  file=sys.stderr)
            continue
        m[key] = att_sku
    return m


def merge_sku_into_dm(dm_data, sku_map):
    """
    Walks dm_data['configs'] and adds 'ATT SKU' to each config whose
    config_heading_row matches an SKU dm-line. Returns the modified
    (in-place) dm_data.
    """
    matched = 0
    unmatched = 0

    configs = dm_data.get("configs", [])
    for cfg in configs:
        row = cfg.get("config_heading_row")
        att_sku = sku_map.get(str(row)) if row is not None else None
        cfg["ATT SKU"] = att_sku          # None when no match
        if att_sku is not None:
            matched += 1
        else:
            unmatched += 1
            print(f"[WARN] No SKU match for config_heading_row={row} "
                  f"heading='{cfg.get('config_heading')}'",
                  file=sys.stderr)

    print(f"[INFO] Configs matched: {matched}, unmatched: {unmatched}, "
          f"total: {len(configs)}", file=sys.stderr)
    return dm_data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sku_file")
    ap.add_argument("dm_file")
    ap.add_argument("output_file")
    args = ap.parse_args()

    sku_data = load_json(args.sku_file)
    dm_data = load_json(args.dm_file)

    sku_map = build_sku_map(sku_data)
    merged = merge_sku_into_dm(dm_data, sku_map)

    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)

    print(f"Wrote merged DM to {args.output_file}")


if __name__ == "__main__":
    main()