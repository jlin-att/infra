#!/usr/bin/env python3
import argparse
import json
import sys


NUM_FIELDS = ("vcpu", "memory_G", "root_disk_GB", "cinder_gb")


def to_number(val, default=0.0):
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        s = val.strip()
        if s == "":
            return default
        try:
            return float(s)
        except ValueError:
            return default
    return default


def is_deprecated(cfg) -> bool:
    """Return True if config status is 'deprecated'."""
    status = cfg.get("status")
    if status is None:
        return False
    if isinstance(status, str):
        return status.strip().lower() == "deprecated"
    return False


def main():
    ap = argparse.ArgumentParser(
        description=("Summarize configs (idx,heading,subscription_count,item_count + resource sums) or, "
                     "optionally, list per-item details including pod_vm and resource fields.")
    )
    ap.add_argument("json_file", help="Input JSON filename")
    ap.add_argument(
        "--pod-vm",
        action="store_true",
        help=("If set, print per-item details: idx,config_heading,item_idx,pod_vm,quantity,"
              "vcpu,memory_G,root_disk_GB,cinder_gb")
    )
    ap.add_argument(
        "--display-deprecate",
        action="store_true",
        help=("If set, include deprecated configs; otherwise skip configs with status=='deprecated'.")
    )

    args = ap.parse_args()

    try:
        with open(args.json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {args.json_file}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        sys.exit(2)

    configs = data.get("configs", [])
    if not isinstance(configs, list):
        print('"configs" exists but is not a list', file=sys.stderr)
        sys.exit(2)

    if args.pod_vm:
        print("idx,config_heading,item_idx,pod_vm,quantity,vcpu,memory_G,root_disk_GB,cinder_gb")

        for idx, cfg in enumerate(configs, start=1):
            # Skip deprecated configs unless explicitly requested to display them
            if (not args.display_deprecate) and is_deprecated(cfg):
                continue

            heading = cfg.get("config_heading")
            if heading is None or (isinstance(heading, str) and heading.strip() == ""):
                heading = "<missing>"

            items = cfg.get("items", [])
            if items is None:
                items = []
            if not isinstance(items, list):
                print(f'Warning: config #{idx} ("{heading}") has "items" not a list; skipping',
                      file=sys.stderr)
                continue

            for item_idx, item in enumerate(items, start=1):
                if not isinstance(item, dict):
                    print(f"{idx},{heading},{item_idx},<non-dict-item>,,,,,")
                    continue

                pod_vm = item.get("pod_vm", "<missing>")
                quantity = to_number(item.get("quantity"), default=0.0)

                vcpu = to_number(item.get("vcpu"))
                memory_G = to_number(item.get("memory_G"))
                root_disk_GB = to_number(item.get("root_disk_GB"))
                cinder_gb = to_number(item.get("cinder_gb"))

                print(f"{idx},{heading},{item_idx},{pod_vm},{quantity:g},{vcpu:g},{memory_G:g},{root_disk_GB:g},{cinder_gb:g}")

    else:
        print(f"configs count: {len(configs)}")
        print("idx,config_heading,subscription_count,item_count,summary_vcpu,summary_memory_G,summary_root_disk_GB,summary_cinder_gb")

        grand_item_count = 0
        grand_subscription_count = 0.0
        grand_sums = {k: 0.0 for k in NUM_FIELDS}

        for idx, cfg in enumerate(configs, start=1):
            # Skip deprecated configs unless explicitly requested to display them
            if (not args.display_deprecate) and is_deprecated(cfg):
                continue

            heading = cfg.get("config_heading")
            if heading is None or (isinstance(heading, str) and heading.strip() == ""):
                heading = "<missing>"

            subscription_count = to_number(cfg.get("subscription_count"), default=0.0)

            items = cfg.get("items", [])
            if items is None:
                items = []
            if not isinstance(items, list):
                print(f'Warning: config #{idx} ("{heading}") has "items" not a list; treating as 0',
                      file=sys.stderr)
                items = []

            item_count = len(items)
            grand_item_count += item_count
            grand_subscription_count += subscription_count

            sums = {k: 0.0 for k in NUM_FIELDS}

            for item in items:
                if not isinstance(item, dict):
                    continue
                quantity = to_number(item.get("quantity"), default=0.0)
                for field in NUM_FIELDS:
                    val = to_number(item.get(field), default=0.0)
                    sums[field] += val * quantity

            for field in NUM_FIELDS:
                grand_sums[field] += sums[field]

            print(
                f"{idx},{heading},{subscription_count:g},{item_count},"
                f"{sums['vcpu']:g},{sums['memory_G']:g},{sums['root_disk_GB']:g},{sums['cinder_gb']:g}"
            )

        print(
            f"total,,{grand_subscription_count:g},{grand_item_count},"
            f"{grand_sums['vcpu']:g},{grand_sums['memory_G']:g},{grand_sums['root_disk_GB']:g},{grand_sums['cinder_gb']:g}"
        )


if __name__ == "__main__":
    main()