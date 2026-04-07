#!/usr/bin/env python3
import json
import argparse
from typing import Any, Dict, List, Set, Tuple, Optional

SKIP_CNF_VNF = {"infra", "appliance"}
SERVERS_PER_VCPU_DIVISOR = 72.0  # servers_count = total_vcpu / 72


def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def derive_main_path(cnfvnf_path: str) -> str:
    if not cnfvnf_path.endswith(".json"):
        raise ValueError('Input file must end with ".json"')
    if not cnfvnf_path.endswith("-cnfvnf.json"):
        raise ValueError('Input file must be named like "<base-name>-cnfvnf.json"')
    return cnfvnf_path[: -len("-cnfvnf.json")] + ".json"


def to_number(x: Any) -> float:
    if x is None:
        return 0.0
    if isinstance(x, (int, float)):
        return float(x)
    if isinstance(x, str):
        s = x.strip()
        if not s:
            return 0.0
        try:
            return float(s)
        except ValueError:
            return 0.0
    return 0.0


def csv_escape(s: str) -> str:
    if any(ch in s for ch in [",", '"', "\n", "\r"]):
        return '"' + s.replace('"', '""') + '"'
    return s


def norm_key(s: str) -> str:
    return str(s).strip().casefold()


def get_locations(cnfvnf_data: Dict[str, Any]) -> List[str]:
    locs = cnfvnf_data.get("locations", [])
    return [str(x) for x in locs] if isinstance(locs, list) else []


def get_site_templates(cnfvnf_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    st = cnfvnf_data.get("Site-Templates", cnfvnf_data.get("site_templates", []))
    return st if isinstance(st, list) else []


def get_site_template_name(st_obj: Dict[str, Any]) -> str:
    if "site-template" in st_obj:
        return str(st_obj["site-template"])
    if "site_template" in st_obj:
        return str(st_obj["site_template"])
    if "siteTemplate" in st_obj:
        return str(st_obj["siteTemplate"])
    return ""


def extract_network_elements_for_selected_site_template(
    cnfvnf_data: Dict[str, Any], selected_site_template: str
) -> List[Dict[str, Any]]:
    for st in get_site_templates(cnfvnf_data):
        if not isinstance(st, dict):
            continue
        if get_site_template_name(st) == selected_site_template:
            nes = st.get("network_elements", st.get("networkElements", []))
            if isinstance(nes, list):
                return [ne for ne in nes if isinstance(ne, dict)]
            return []
    return []


def build_config_heading_map(main_data: Any) -> Dict[str, Dict[str, Any]]:
    items: List[Any] = []
    if isinstance(main_data, list):
        items = main_data
    elif isinstance(main_data, dict):
        for k in ("items", "rows", "data", "configs", "configurations"):
            if isinstance(main_data.get(k), list):
                items = main_data[k]
                break

    out: Dict[str, Dict[str, Any]] = {}
    for obj in items:
        if isinstance(obj, dict) and "config_heading" in obj:
            out[norm_key(obj["config_heading"])] = obj
    return out


def should_skip_cnf_vnf(ne: Dict[str, Any]) -> bool:
    v = ne.get("CNF_VNF")
    if v is None:
        return False
    return str(v).strip().lower() in SKIP_CNF_VNF


def normalize_network_element(name: str) -> str:
    idx = name.find("(DNP")
    if idx == -1:
        return name.strip()
    return name[:idx].rstrip()


def load_dd_mapping(path: str) -> Dict[str, str]:
    try:
        data = load_json(path)
    except FileNotFoundError:
        return {}

    mappings = data.get("ne-mappings", [])
    if not isinstance(mappings, list):
        return {}

    out: Dict[str, str] = {}
    for m in mappings:
        if isinstance(m, dict) and "original" in m and "dd-name" in m:
            out[norm_key(m["original"])] = str(m["dd-name"])
    return out


def prompt_menu(title: str, options: List[str]) -> str:
    if not options:
        raise ValueError(f"No options available for {title}")

    while True:
        print(title)
        for i, opt in enumerate(options, start=1):
            print(f"  {i}) {opt}")

        choice = input(f"Enter choice (1-{len(options)}): ").strip()
        try:
            n = int(choice)
            if 1 <= n <= len(options):
                return options[n - 1]
        except ValueError:
            pass

        print("Invalid choice. Please try again.\n")


def all_locations_are_zero(ne: Dict[str, Any], locations: List[str]) -> bool:
    if not locations:
        return False
    for loc in locations:
        if to_number(ne.get(loc, 0)) != 0.0:
            return False
    return True


def compute_totals_for_config(
    config_obj: Dict[str, Any], multiply_factor: float
) -> Tuple[float, float, float, float]:
    items = config_obj.get("items", [])
    if not isinstance(items, list):
        items = []

    vcpu_sum = 0.0
    mem_sum = 0.0
    root_sum = 0.0
    cinder_sum = 0.0

    for it in items:
        if not isinstance(it, dict):
            continue
        qty = to_number(it.get("quantity", 1))
        vcpu_sum += to_number(it.get("vcpu", 0)) * qty
        mem_sum += to_number(it.get("memory_g", it.get("memory_G", it.get("memory", 0)))) * qty
        root_sum += to_number(it.get("root_disk_GB", it.get("root_disk_gb", it.get("root_disk", 0)))) * qty
        cinder_sum += to_number(it.get("cinder_gb", it.get("cinder_GB", it.get("cinder", 0)))) * qty

    return (
        vcpu_sum * multiply_factor,
        mem_sum * multiply_factor,
        root_sum * multiply_factor,
        cinder_sum * multiply_factor,
    )


def write_lines(lines: List[str], out_path: Optional[str]) -> None:
    for line in lines:
        print(line)

    if out_path:
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            for line in lines:
                f.write(line + "\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cnfvnf_json", help='Path to "<base-name>-cnfvnf.json"')
    ap.add_argument("--ddmapping", default="ddmapping.json", help="Path to ddmapping.json")
    ap.add_argument(
        "--out-csv",
        default=None,
        help="Optional path to write the TOTALS CSV output (network_element rows). "
             "If omitted, output is only printed to stdout.",
    )
    args = ap.parse_args()

    cnfvnf_path = args.cnfvnf_json
    main_path = derive_main_path(cnfvnf_path)

    cnfvnf_data = load_json(cnfvnf_path)
    main_data = load_json(main_path)
    dd_map = load_dd_mapping(args.ddmapping)

    locations = get_locations(cnfvnf_data)
    if not locations:
        raise ValueError('No "locations" list found in the *-cnfvnf.json file.')

    selected_location = prompt_menu("Select a location:", locations)
    print(f"Chosen location: {selected_location}")

    st_names: List[str] = []
    for st in get_site_templates(cnfvnf_data):
        if isinstance(st, dict):
            name = get_site_template_name(st)
            if name:
                st_names.append(name)

    seen = set()
    st_names = [x for x in st_names if not (x in seen or seen.add(x))]
    if not st_names:
        raise ValueError('No "site-template" fields found inside "Site-Templates".')

    selected_site_template = prompt_menu("Select a site-template:", st_names)
    print(f"Chosen site-template: {selected_site_template}")

    ne_list = extract_network_elements_for_selected_site_template(cnfvnf_data, selected_site_template)

    config_map = build_config_heading_map(main_data)
    config_headings_norm: Set[str] = set(config_map.keys())

    print("\n# NOT FOUND")
    print("network_element,status")
    for ne in ne_list:
        if should_skip_cnf_vnf(ne):
            continue
        raw_name = ne.get("network_element")
        if raw_name is None:
            continue
        ne_name = normalize_network_element(str(raw_name))
        mapped = dd_map.get(norm_key(ne_name))
        if mapped is not None:
            ne_name = mapped
        if all_locations_are_zero(ne, locations):
            continue
        if norm_key(ne_name) in config_headings_norm:
            continue
        print(f"{csv_escape(ne_name)},not found")

    totals_lines: List[str] = []
    totals_lines.append("# TOTALS (matched network_element -> config_heading)")
    totals_lines.append(
        "network_element,CNF_VNF,Subs,"
        "total_vcpu,total_memory_g,total_root_disk_GB,total_cinder_gb,"
        "servers_count"
    )

    for ne in ne_list:
        raw_name = ne.get("network_element")
        if raw_name is None:
            continue

        multiply_factor = to_number(ne.get(selected_location, 0))

        ne_name = normalize_network_element(str(raw_name))
        mapped = dd_map.get(norm_key(ne_name))
        if mapped is not None:
            ne_name = mapped

        cnf_vnf = ne.get("CNF_VNF", "")
        subs = ne.get("Subs", "")

        cfg = config_map.get(norm_key(ne_name))
        if cfg is None:
            tvcpu, tmem, troot, tcinder = 0.0, 0.0, 0.0, 0.0
        else:
            tvcpu, tmem, troot, tcinder = compute_totals_for_config(cfg, multiply_factor)

        servers_count = tvcpu / SERVERS_PER_VCPU_DIVISOR if SERVERS_PER_VCPU_DIVISOR else 0.0

        totals_lines.append(
            f"{csv_escape(ne_name)},"
            f"{csv_escape(str(cnf_vnf))},"
            f"{csv_escape(str(subs))},"
            f"{tvcpu:.6g},{tmem:.6g},{troot:.6g},{tcinder:.6g},"
            f"{servers_count:.6g}"
        )

    print()
    write_lines(totals_lines, args.out_csv)


if __name__ == "__main__":
    main()