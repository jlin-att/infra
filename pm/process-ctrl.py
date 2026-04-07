import argparse
import sys
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser(
        description=(
            "Per site: max metrics + time (and optional entity/controller); output CSV to stdout; "
            "print WARNING alerts after."
        )
    )
    ap.add_argument("input_file", help="Path to the input file")
    ap.add_argument("--encoding", default="utf-8")

    ap.add_argument("--time-col", default="PERIOD_START_TIME")
    ap.add_argument("--site-col", default="CBIS name")

    # For this file, controller identity is typically in CTRL name
    ap.add_argument(
        "--entity-col",
        default="CTRL name",
        help="Optional column for controller/entity name (default: CTRL name)",
    )

    # Controller metric columns (as in your sample)
    ap.add_argument("--cpu-col", default="Controller CPU Utilization")
    ap.add_argument("--mem-col", default="Controller Memory In Use Ratio")
    ap.add_argument("--thr-col", default="Controller Data Throughput")
    ap.add_argument("--disk-col", default="Controller VFS Disk Usage")

    # Thresholds (warnings)
    ap.add_argument("--cpu-threshold", type=float, default=80.0, help="CPU warning threshold (default: 80)")
    ap.add_argument("--mem-threshold", type=float, default=95.0, help="MEM warning threshold (default: 95)")
    ap.add_argument("--disk-threshold", type=float, default=80.0, help="DISK warning threshold (default: 80)")

    args = ap.parse_args()

    df = pd.read_csv(Path(args.input_file), sep=";", header=0, encoding=args.encoding)

    # Optional: strip whitespace from headers in case the file has "colname " etc.
    df.columns = df.columns.str.strip()

    # Require only what this file actually needs
    must_have = [args.time_col, args.site_col, args.cpu_col, args.mem_col, args.thr_col, args.disk_col]
    missing = [c for c in must_have if c not in df.columns]
    if missing:
        raise SystemExit(f"Missing required columns: {missing}. Columns present: {list(df.columns)}")

    # Parse time: MM.DD.YYYY HH:MM:SS
    dt = pd.to_datetime(df[args.time_col], format="%m.%d.%Y %H:%M:%S", errors="coerce")
    if dt.isna().any():
        bad = df.loc[dt.isna(), args.time_col].dropna().astype(str).unique()
        raise SystemExit(
            f"Failed to parse some '{args.time_col}' values. Example bad (up to 10): {', '.join(bad[:10])}"
        )
    df["_dt"] = dt

    # Enforce single unique date
    dates = df["_dt"].dt.date.dropna().unique()
    if len(dates) != 1:
        dates_sorted = sorted(dates)
        print(
            f"ERROR: Multiple dates found in '{args.time_col}'. Dates present ({len(dates_sorted)}): "
            + ", ".join(d.isoformat() for d in dates_sorted),
            file=sys.stderr,
        )
        sys.exit(2)

    # Safe site column name
    df["site"] = df[args.site_col]

    # Optional entity (CTRL name)
    entity_present = args.entity_col in df.columns
    if entity_present:
        df["entity"] = df[args.entity_col]
    else:
        df["entity"] = pd.NA

    # Numeric conversions
    df["_cpu"] = pd.to_numeric(df[args.cpu_col], errors="coerce")
    df["_mem"] = pd.to_numeric(df[args.mem_col], errors="coerce")
    df["_thr"] = pd.to_numeric(df[args.thr_col], errors="coerce")
    df["_disk"] = pd.to_numeric(df[args.disk_col], errors="coerce")

    base = df.dropna(subset=["site", "_dt"]).copy()

    def max_with_time_and_entity(value_col: str, out_value: str, out_time: str, out_entity: str) -> pd.DataFrame:
        tmp = base.dropna(subset=[value_col]).copy()

        # Highest value wins; tie -> earliest time; then entity name stable ordering
        tmp = tmp.sort_values(
            ["site", value_col, "_dt", "entity"],
            ascending=[True, False, True, True],
        )
        tmp = tmp.groupby("site", as_index=False).first()

        tmp[out_value] = tmp[value_col]
        tmp[out_time] = tmp["_dt"].dt.strftime("%H:%M:%S")
        tmp[out_entity] = tmp["entity"]
        return tmp[["site", out_value, out_time, out_entity]]

    cpu_max = max_with_time_and_entity("_cpu", "max_cpu", "max_cpu_time", "max_cpu_entity")
    mem_max = max_with_time_and_entity("_mem", "max_mem", "max_mem_time", "max_mem_entity")
    thr_max = max_with_time_and_entity("_thr", "max_throughput", "max_throughput_time", "max_throughput_entity")
    disk_max = max_with_time_and_entity("_disk", "max_disk_usage", "max_disk_usage_time", "max_disk_usage_entity")

    summary = (
        cpu_max.merge(mem_max, on="site", how="outer")
        .merge(thr_max, on="site", how="outer")
        .merge(disk_max, on="site", how="outer")
        .sort_values("site")
    )

    # If the entity column wasn't present, drop the entity outputs (keeps output clean)
    if not entity_present:
        summary = summary.drop(
            columns=[
                "max_cpu_entity",
                "max_mem_entity",
                "max_throughput_entity",
                "max_disk_usage_entity",
            ],
            errors="ignore",
        )

    # Summary CSV to stdout
    print(summary.to_csv(index=False).rstrip("\n"))

    # Alerts after summary
    print()

    def print_alerts(metric_col: str, label: str, threshold: float, value_name: str):
        cols = ["site", metric_col, "_dt"]
        if entity_present:
            cols.append("entity")

        tmp = base.dropna(subset=[metric_col]).copy()
        alerts = (
            tmp.loc[tmp[metric_col] > threshold, cols]
            .sort_values(["site", "_dt"])
            .rename(columns={metric_col: value_name})
        )

        if alerts.empty:
            print(f"No {label} WARNING alerts (threshold={threshold}).")
        else:
            for rec in alerts.to_records(index=False):
                t = pd.Timestamp(rec["_dt"]).strftime("%H:%M:%S")
                if entity_present:
                    print(
                        f"WARNING {label} threshold={threshold}: "
                        f"site={rec['site']}, entity={rec['entity']}, {value_name}={rec[value_name]}, time={t}"
                    )
                else:
                    print(
                        f"WARNING {label} threshold={threshold}: "
                        f"site={rec['site']}, {value_name}={rec[value_name]}, time={t}"
                    )

    print_alerts("_cpu", "CPU", args.cpu_threshold, "cpu")
    print_alerts("_mem", "MEM", args.mem_threshold, "mem")
    print_alerts("_disk", "DISK", args.disk_threshold, "disk_usage")


if __name__ == "__main__":
    main()