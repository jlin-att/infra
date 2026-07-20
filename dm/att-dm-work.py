#!/usr/bin/env python3
"""
Interactive viewer for the sitesku + dm output files.

Steps:
  1. Load both files.
  2. List sites from the sitesku file; user picks one.
  3. Print each network element under that site:
        network_element (site), CNF_VNF, Subs, count, ATT SKU
  4. For each NE with a non-null ATT SKU, look up the matching config in
     the DM file, sum the item resources, multiply by `count`, and print:
        network_element, total vcpu, total memory_G,
        total root_disk_GB, total cinder_gb
"""

import argparse
import json
import sys


# ---------- io ----------
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------- site chooser ----------
def choose_site(sitesku_data):
    sites = [s.get("site") for s in sitesku_data if s.get("site")]
    if not sites:
        print("[ERROR] No sites found in sitesku file.", file=sys.stderr)
        sys.exit(1)

    print("\nAvailable sites:")
    for i, name in enumerate(sites, start=1):
        print(f"  {i:>3}. {name}")

    while True:
        raw = input("\nChoose a site (number or name): ").strip()
        if not raw:
            continue
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(sites):
                chosen = sites[idx - 1]
                break
            print(f"  -> Out of range (1..{len(sites)}). Try again.")
            continue
        matches = [s for s in sites if s.lower() == raw.lower()]
        if not matches:
            matches = [s for s in sites if s.lower().startswith(raw.lower())]
        if len(matches) == 1:
            chosen = matches[0]
            break
        if len(matches) > 1:
            print(f"  -> Ambiguous, matched: {matches}. Be more specific.")
            continue
        print("  -> No match. Try again.")

    for site_obj in sitesku_data:
        if site_obj.get("site") == chosen:
            return chosen, site_obj
    return chosen, None


# ---------- table printer ----------
def print_table(title, headers, rows):
    widths = [len(h) for h in headers]
    str_rows = [[("" if c is None else str(c)) for c in r] for r in rows]
    for r in str_rows:
        for i, cell in enumerate(r):
            widths[i] = max(widths[i], len(cell))

    def fmt(cells):
        return "  ".join(c.ljust(widths[i]) for i, c in enumerate(cells))

    print(f"\n{title}\n")
    print(fmt(headers))
    print(fmt(["-" * w for w in widths]))
    for r in str_rows:
        print(fmt(r))


def print_site_elements(site_name, site_obj):
    nes = site_obj.get("network_elements", []) if site_obj else []
    if not nes:
        print(f"\nSite '{site_name}' has no network elements.")
        return
    headers = ["network_element (site)", "CNF_VNF", "Subs", "count", "ATT SKU"]
    rows = [[
        ne.get("network_element (site)"),
        ne.get("CNF_VNF"),
        ne.get("Subs"),
        ne.get("count"),
        ne.get("ATT SKU"),
    ] for ne in nes]
    print_table(f"=== Site: {site_name}  ({len(rows)} network elements) ===",
                headers, rows)


# ---------- DM lookup + resource math ----------
def build_dm_sku_map(dm_data):
    """
    { ATT SKU (str) : config_dict }
    Skips configs with null / empty ATT SKU. Warns on duplicates.
    """
    m = {}
    for cfg in dm_data.get("configs", []):
        sku = cfg.get("ATT SKU")
        if not sku:
            continue
        key = str(sku)
        if key in m:
            print(f"[WARN] Duplicate ATT SKU '{sku}' in DM file "
                  f"(rows {m[key].get('config_heading_row')} and "
                  f"{cfg.get('config_heading_row')}); keeping first.",
                  file=sys.stderr)
            continue
        m[key] = cfg
    return m


def _to_number(v):
    """Coerce a value to float; return 0.0 if unparseable/empty."""
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip()
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


RESOURCE_FIELDS = ["vcpu", "memory_G", "root_disk_GB", "cinder_gb"]


def sum_config_resources(cfg, printall=False):
    """Sum each resource field across all items[] in the config."""
    totals = {f: 0.0 for f in RESOURCE_FIELDS}
    for item in cfg.get("items", []):
        qty = _to_number(item.get("quantity")) or 0.0  # treat missing/0 qty as 0
        for f in RESOURCE_FIELDS:
            totals[f] += _to_number(item.get(f)) * qty
            if printall:
                print (_to_number(item.get(f)),qty,totals[f] )
    return totals


def compute_site_totals(site_obj, dm_sku_map):
    """
    For each NE in the site with a non-null ATT SKU that exists in DM,
    return a row: [ne_name, total vcpu, total memory_G,
                   total root_disk_GB, total cinder_gb]
    """
    rows = []
    for ne in site_obj.get("network_elements", []):
        sku = ne.get("ATT SKU")
        if not sku:
            continue
        cfg = dm_sku_map.get(str(sku))
        if cfg is None:
            print(f"[WARN] ATT SKU '{sku}' from site not found in DM file "
                  f"(NE='{ne.get('network_element (site)')}')",
                  file=sys.stderr)
            continue
        '''
        if sku == "a0cccf00a":
            print ("found mediation")
            print (json.dumps(cfg))
            sys.exit(0)
        '''

        count = _to_number(ne.get("count"))
        #per_config = sum_config_resources(cfg, sku == "a0cccf00a")
        per_config = sum_config_resources(cfg)
        totals = {f: per_config[f] * count for f in RESOURCE_FIELDS}

        rows.append([
            ne.get("network_element (site)"),
            _fmt_num(totals["vcpu"]),
            _fmt_num(totals["memory_G"]),
            _fmt_num(totals["root_disk_GB"]),
            _fmt_num(totals["cinder_gb"]),
        ])
    return rows


def _fmt_num(x):
    """Show ints as ints, floats rounded to 2 decimals."""
    if x == int(x):
        return str(int(x))
    return f"{x:.2f}"


def print_site_totals(site_name, rows):
    if not rows:
        print(f"\nNo DM-matched network elements for site '{site_name}'.")
        return
    headers = ["network_element",
               "total vcpu", "total memory_G",
               "total root_disk_GB", "total cinder_gb"]
    # grand totals row
    grand = [0.0] * 4
    for r in rows:
        for i, v in enumerate(r[1:]):
            grand[i] += float(v)
    grand_row = ["TOTAL"] + [_fmt_num(v) for v in grand]

    print_table(f"=== Site: {site_name}  resource totals ===",
                headers, rows + [grand_row])


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sitesku_file", help="Merged sitesku JSON (per-site NE list)")
    ap.add_argument("dm_file", help="DM JSON with ATT SKU merged in")
    args = ap.parse_args()

    sitesku_data = load_json(args.sitesku_file)
    dm_data = load_json(args.dm_file)

    print(f"[INFO] Loaded sitesku ({len(sitesku_data)} sites) and "
          f"dm file ({len(dm_data.get('configs', []))} configs).")

    site_name, site_obj = choose_site(sitesku_data)
    if site_obj is None:
        print(f"[ERROR] Site '{site_name}' not found in sitesku file.",
              file=sys.stderr)
        sys.exit(1)

    # Step 1: existing NE listing
    print_site_elements(site_name, site_obj)

    # Step 2: DM-matched resource totals
    dm_sku_map = build_dm_sku_map(dm_data)
    total_rows = compute_site_totals(site_obj, dm_sku_map)
    print_site_totals(site_name, total_rows)


if __name__ == "__main__":
    main()