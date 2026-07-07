#!/usr/bin/env python3
"""
Merge SKU + Evolution + Site JSON files into a single per-site output.

Usage:
    python merge_site_evolution.py <sku.json> <site.json> <evolution.json> <output.json>
"""

import argparse
import json
import sys
from difflib import SequenceMatcher


# ---------- helpers ----------
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def norm(s):
    if s is None:
        return ""
    return "".join(ch.lower() for ch in str(s) if ch.isalnum())


def similar(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def subs_match(s1, s2):
    e1 = (s1 is None) or (str(s1).strip() == "")
    e2 = (s2 is None) or (str(s2).strip() == "")
    if e1 or e2:
        return True
    try:
        return float(s1) == float(s2)
    except (TypeError, ValueError):
        return str(s1).strip() == str(s2).strip()


def line_close(l1, l2, tol=10):
    try:
        return abs(int(l1) - int(l2)) <= tol
    except (TypeError, ValueError):
        return False


def ne_match(ne1, ne2, threshold=0.7):
    n1, n2 = norm(ne1), norm(ne2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    if n1 in n2 or n2 in n1:
        return True
    return similar(ne1, ne2) >= threshold


# ---------- flatten ----------
def build_sku_map(sku_data):
    m = {}
    for row in sku_data:
        dm_line = row.get("dm-line")
        att_sku = row.get("ATT SKU")
        if dm_line is None:
            continue
        m[str(dm_line)] = att_sku
    return m


def flatten_evolution(evo_data, sku_map):
    """
    { site_name: [ {network_element, CNF_VNF, Subs, line, DMrow, ATT SKU}, ... ] }
    """
    by_site = {}
    for site_obj in evo_data:
        site = site_obj.get("site")
        entries = by_site.setdefault(site, [])
        for tpl in site_obj.get("Site-Templates", []):
            for ne in tpl.get("network_elements", []):
                dmrow = ne.get("DMrow")
                att_sku = sku_map.get(str(dmrow)) if dmrow is not None else None
                entries.append({
                    "network_element": ne.get("network_element"),
                    "CNF_VNF": ne.get("CNF_VNF"),
                    "Subs": ne.get("Subs"),
                    "line": ne.get("line"),
                    "DMrow": dmrow,
                    "ATT SKU": att_sku,
                })
    return by_site


def flatten_site(site_data):
    """
    { site_name: [ {network_element, CNF_VNF, Subs, line, count}, ... ] }
    Walks Site-Templates -> network_elements. Rows with count == 0 are skipped.
    """
    by_site = {}
    items = site_data if isinstance(site_data, list) else [site_data]
    for site_obj in items:
        site = site_obj.get("site")
        entries = by_site.setdefault(site, [])

        # Same nested layout as evolution
        for tpl in site_obj.get("Site-Templates", []):
            for row in tpl.get("network_elements", []):
                cnt = row.get("count", 0)
                try:
                    cnt_val = float(cnt) if cnt not in (None, "") else 0.0
                except (TypeError, ValueError):
                    cnt_val = 0.0
                if cnt_val == 0:
                    continue
                entries.append({
                    "network_element": row.get("network_element"),
                    "CNF_VNF": row.get("CNF_VNF"),
                    "Subs": row.get("Subs"),
                    "line": row.get("line"),
                    "count": cnt,
                })
    return by_site


# ---------- merge ----------
def merge(site_by_site, evo_by_site):
    output = []
    for site, site_rows in site_by_site.items():
        evo_rows = evo_by_site.get(site, [])
        used_evo_idx = set()
        ne_list = []

        for s_row in site_rows:
            best_idx = None
            best_score = -1.0

            for i, e_row in enumerate(evo_rows):
                if i in used_evo_idx:
                    continue
                if not subs_match(s_row.get("Subs"), e_row.get("Subs")):
                    continue
                if not line_close(s_row.get("line"), e_row.get("line")):
                    continue
                if not ne_match(s_row.get("network_element"),
                                e_row.get("network_element")):
                    continue
                score = similar(s_row.get("network_element"),
                                e_row.get("network_element"))
                if score > best_score:
                    best_score = score
                    best_idx = i

            if best_idx is not None:
                e_row = evo_rows[best_idx]
                used_evo_idx.add(best_idx)
                ne_list.append({
                    "network_element (site)": s_row.get("network_element"),
                    "network_element (evolution)": e_row.get("network_element"),
                    "CNF_VNF": e_row.get("CNF_VNF") or s_row.get("CNF_VNF"),
                    "Subs": e_row.get("Subs") if (e_row.get("Subs") not in (None, ""))
                                              else s_row.get("Subs"),
                    "count": s_row.get("count"),
                    "ATT SKU": e_row.get("ATT SKU"),
                })
            else:
                ne_list.append({
                    "network_element (site)": s_row.get("network_element"),
                    "network_element (evolution)": None,
                    "CNF_VNF": s_row.get("CNF_VNF"),
                    "Subs": s_row.get("Subs"),
                    "count": s_row.get("count"),
                    "ATT SKU": None,
                })
                print(f"[WARN] No evolution match for site='{site}' "
                      f"NE='{s_row.get('network_element')}' "
                      f"line={s_row.get('line')} Subs={s_row.get('Subs')}",
                      file=sys.stderr)

        output.append({"site": site, "network_elements": ne_list})
    return output


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sku_file")
    ap.add_argument("site_file")
    ap.add_argument("evolution_file")
    ap.add_argument("output_file")
    args = ap.parse_args()

    sku_data = load_json(args.sku_file)
    site_data = load_json(args.site_file)
    evo_data = load_json(args.evolution_file)

    sku_map = build_sku_map(sku_data)
    evo_by_site = flatten_evolution(evo_data, sku_map)
    site_by_site = flatten_site(site_data)

    result = merge(site_by_site, evo_by_site)

    with open(args.output_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(result)} sites to {args.output_file}")


if __name__ == "__main__":
    main()