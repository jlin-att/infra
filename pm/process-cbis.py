import argparse
import sys
from pathlib import Path

import pandas as pd


def main():
    ap = argparse.ArgumentParser(
        description="Per site: max metrics + time; output CSV to stdout; print WARNING alerts after."
    )
    ap.add_argument("input_file", help="Path to the input file")
    ap.add_argument("--time-col", default="PERIOD_START_TIME")
    ap.add_argument("--site-col", default="CBIS name")
    ap.add_argument("--encoding", default="utf-8")

    # Compute columns
    ap.add_argument("--cpu-col", default="Compute CPU Utilization")
    ap.add_argument("--mem-col", default="Compute Memory In Use Ratio")
    ap.add_argument("--thr-col", default="Compute Data Throughput")
    ap.add_argument("--disk-col", default="Compute VFS Disk Usage")

    # Controller columns
    ap.add_argument("--ctrl-cpu-col", default="Controller CPU Utilization")
    ap.add_argument("--ctrl-mem-col", default="Controller Memory In Use Ratio")
    ap.add_argument("--ctrl-thru-col", default="Controller Data Throughput")
    ap.add_argument("--ctrl-disk-col", default="Controller VFS Disk Usage")

    # Storage columns
    ap.add_argument("--storage-cpu-col", default="Storage CPU Utilization")
    ap.add_argument("--storage-mem-col", default="Storage Memory In Use Ratio")
    ap.add_argument("--storage-thru-col", default="Storage Data Throughput")

    # Thresholds (warnings)
    ap.add_argument("--cpu-threshold", type=float, default=23.0, help="Compute CPU warning threshold (default: 23)")
    ap.add_argument("--mem-threshold", type=float, default=65.0, help="Compute MEM warning threshold (default: 65)")
    ap.add_argument("--disk-threshold", type=float, default=80.0, help="Compute DISK warning threshold (default: 80)")

    ap.add_argument("--ctrl-cpu-threshold", type=float, default=23.0, help="Controller CPU warning threshold")
    ap.add_argument("--ctrl-mem-threshold", type=float, default=65.0, help="Controller MEM warning threshold")
    ap.add_argument("--ctrl-disk-threshold", type=float, default=80.0, help="Controller DISK warning threshold")

    ap.add_argument("--storage-cpu-threshold", type=float, default=23.0, help="Storage CPU warning threshold")
    ap.add_argument("--storage-mem-threshold", type=float, default=65.0, help="Storage MEM warning threshold")

    args = ap.parse_args()

    df = pd.read_csv(Path(args.input_file), sep=";", header=0, encoding=args.encoding)

    # Validate required columns
    required_cols = (
        args.time_col,
        args.site_col,
        args.cpu_col,
        args.mem_col,
        args.thr_col,
        args.disk_col,
        args.ctrl_cpu_col,
        args.ctrl_mem_col,
        args.ctrl_thru_col,
        args.ctrl_disk_col,
        args.storage_cpu_col,
        args.storage_mem_col,
        args.storage_thru_col,
    )
    for c in required_cols:
        if c not in df.columns:
            raise SystemExit(f"Missing column '{c}'. Columns: {list(df.columns)}")

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

    # Numeric conversions (Compute)
    df["_cpu"] = pd.to_numeric(df[args.cpu_col], errors="coerce")
    df["_mem"] = pd.to_numeric(df[args.mem_col], errors="coerce")
    df["_thr"] = pd.to_numeric(df[args.thr_col], errors="coerce")
    df["_disk"] = pd.to_numeric(df[args.disk_col], errors="coerce")

    # Numeric conversions (Controller)
    df["_ctrl_cpu"] = pd.to_numeric(df[args.ctrl_cpu_col], errors="coerce")
    df["_ctrl_mem"] = pd.to_numeric(df[args.ctrl_mem_col], errors="coerce")
    df["_ctrl_thru"] = pd.to_numeric(df[args.ctrl_thru_col], errors="coerce")
    df["_ctrl_disk"] = pd.to_numeric(df[args.ctrl_disk_col], errors="coerce")

    # Numeric conversions (Storage)
    df["_storage_cpu"] = pd.to_numeric(df[args.storage_cpu_col], errors="coerce")
    df["_storage_mem"] = pd.to_numeric(df[args.storage_mem_col], errors="coerce")
    df["_storage_thru"] = pd.to_numeric(df[args.storage_thru_col], errors="coerce")

    base = df.dropna(subset=["site", "_dt"]).copy()

    def max_with_time(value_col: str, out_value: str, out_time: str) -> pd.DataFrame:
        tmp = base.dropna(subset=[value_col]).copy()
        # Highest value wins; tie -> earliest time
        tmp = tmp.sort_values(["site", value_col, "_dt"], ascending=[True, False, True])
        tmp = tmp.groupby("site", as_index=False).first()
        tmp[out_value] = tmp[value_col]
        tmp[out_time] = tmp["_dt"].dt.strftime("%H:%M:%S")
        return tmp[["site", out_value, out_time]]

    # Compute maxima
    cpu_max = max_with_time("_cpu", "max_cpu", "max_cpu_time")
    mem_max = max_with_time("_mem", "max_mem", "max_mem_time")
    thr_max = max_with_time("_thr", "max_throughput", "max_throughput_time")
    disk_max = max_with_time("_disk", "max_disk_usage", "max_disk_usage_time")

    # Controller maxima
    ctrl_cpu_max = max_with_time("_ctrl_cpu", "max_ctrl_cpu", "max_ctrl_cpu_time")
    ctrl_mem_max = max_with_time("_ctrl_mem", "max_ctrl_mem", "max_ctrl_mem_time")
    ctrl_thru_max = max_with_time("_ctrl_thru", "max_ctrl_throughput", "max_ctrl_throughput_time")
    ctrl_disk_max = max_with_time("_ctrl_disk", "max_ctrl_disk_usage", "max_ctrl_disk_usage_time")

    # Storage maxima
    storage_cpu_max = max_with_time("_storage_cpu", "max_storage_cpu", "max_storage_cpu_time")
    storage_mem_max = max_with_time("_storage_mem", "max_storage_mem", "max_storage_mem_time")
    storage_thru_max = max_with_time("_storage_thru", "max_storage_throughput", "max_storage_throughput_time")

    summary = (
        cpu_max.merge(mem_max, on="site", how="outer")
        .merge(thr_max, on="site", how="outer")
        .merge(disk_max, on="site", how="outer")
        .merge(ctrl_cpu_max, on="site", how="outer")
        .merge(ctrl_mem_max, on="site", how="outer")
        .merge(ctrl_thru_max, on="site", how="outer")
        .merge(ctrl_disk_max, on="site", how="outer")
        .merge(storage_cpu_max, on="site", how="outer")
        .merge(storage_mem_max, on="site", how="outer")
        .merge(storage_thru_max, on="site", how="outer")
        .sort_values("site")
    )

    # Summary CSV to stdout
    print(summary.to_csv(index=False).rstrip("\n"))

    # Alerts after summary
    print()

    def print_alerts(metric_col: str, label: str, threshold: float, value_name: str):
        alerts = (
            base.dropna(subset=[metric_col])
            .loc[base[metric_col] > threshold, ["site", metric_col, "_dt"]]
            .sort_values(["site", "_dt"])
            .rename(columns={metric_col: value_name})
        )
        if alerts.empty:
            print(f"No {label} WARNING alerts (threshold={threshold}).")
        else:
            for rec in alerts.to_records(index=False):
                print(
                    f"WARNING {label} threshold={threshold}: "
                    f"site={rec['site']}, {value_name}={rec[value_name]}, "
                    f"time={pd.Timestamp(rec['_dt']).strftime('%H:%M:%S')}"
                )

    # Compute warnings
    print_alerts("_cpu", "CPU", args.cpu_threshold, "cpu")
    print_alerts("_mem", "MEM", args.mem_threshold, "mem")
    print_alerts("_disk", "DISK", args.disk_threshold, "disk_usage")

    # Controller warnings
    print_alerts("_ctrl_cpu", "CTRL_CPU", args.ctrl_cpu_threshold, "ctrl_cpu")
    print_alerts("_ctrl_mem", "CTRL_MEM", args.ctrl_mem_threshold, "ctrl_mem")
    print_alerts("_ctrl_disk", "CTRL_DISK", args.ctrl_disk_threshold, "ctrl_disk_usage")

    # Storage warnings
    print_alerts("_storage_cpu", "STORAGE_CPU", args.storage_cpu_threshold, "storage_cpu")
    print_alerts("_storage_mem", "STORAGE_MEM", args.storage_mem_threshold, "storage_mem")


if __name__ == "__main__":
    main()