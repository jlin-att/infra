#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from typing import Any, Dict, List


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def to_cell(v: Any) -> str:
    if isinstance(v, (dict, list)):
        return json.dumps(v, sort_keys=True, separators=(",", ":"))
    if v is None:
        return ""
    return str(v)


def get_configs(doc: Dict[str, Any]) -> List[Dict[str, Any]]:
    configs = doc.get("configs", [])
    if not isinstance(configs, list):
        raise ValueError("'configs' must be a list")
    return [c for c in configs if isinstance(c, dict)]


def index_by_heading(doc: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for cfg in get_configs(doc):
        heading = str(cfg.get("config_heading", ""))
        out[heading] = cfg
    return out


def index_items_in_config(cfg: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    items = cfg.get("items", [])
    if not isinstance(items, list):
        return out
    for item in items:
        if not isinstance(item, dict):
            continue
        pod_vm = item.get("pod_vm")
        if pod_vm is None:
            continue
        out[str(pod_vm)] = item
    return out


def presence(is_missing: bool) -> str:
    return "Missing" if is_missing else "Present"


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare two JSON files and output differences as CSV.")
    ap.add_argument("file1")
    ap.add_argument("file2")
    ap.add_argument(
        "--output", "-o", default="-",
        help="Output CSV path (default: stdout). Use '-' for stdout."
    )
    args = ap.parse_args()

    doc1 = load_json(args.file1)
    doc2 = load_json(args.file2)

    ver1 = to_cell(doc1.get("version", "UNKNOWN"))
    ver2 = to_cell(doc2.get("version", "UNKNOWN"))

    cfgs1 = index_by_heading(doc1)
    cfgs2 = index_by_heading(doc2)
    all_headings = sorted(set(cfgs1.keys()) | set(cfgs2.keys()))

    out_f = sys.stdout if args.output == "-" else open(args.output, "w", newline="", encoding="utf-8")
    try:
        w = csv.writer(out_f)
        w.writerow(["config_heading", "pod_vm", "field", "version1", "value1", "version2", "value2"])

        for heading in all_headings:
            c1 = cfgs1.get(heading)
            c2 = cfgs2.get(heading)

            # config_heading missing in one file
            if c1 is None or c2 is None:
                w.writerow([
                    heading,
                    "Only in one file",
                    "",
                    ver1, presence(c1 is None),
                    ver2, presence(c2 is None),
                ])
                continue

            # Both configs exist: compare pod_vm presence + field diffs
            items1 = index_items_in_config(c1)
            items2 = index_items_in_config(c2)
            all_pods = sorted(set(items1.keys()) | set(items2.keys()))

            for pod_vm in all_pods:
                i1 = items1.get(pod_vm)
                i2 = items2.get(pod_vm)

                # pod_vm missing in one file
                if i1 is None or i2 is None:
                    w.writerow([
                        heading,
                        pod_vm,
                        "Only in one file",
                        ver1, presence(i1 is None),
                        ver2, presence(i2 is None),
                    ])
                    continue

                # Both items exist: compare field-by-field (excluding pod_vm)
                fields = sorted(set(i1.keys()) | set(i2.keys()))
                for field in fields:
                    if field == "pod_vm":
                        continue
                    v1 = i1.get(field)
                    v2 = i2.get(field)
                    if v1 != v2:
                        w.writerow([heading, pod_vm, field, ver1, to_cell(v1), ver2, to_cell(v2)])

    finally:
        if out_f is not sys.stdout:
            out_f.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())