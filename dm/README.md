# Overview
Process the dimension matrix.

## 1) Generate a deprecated network element file (`process_deprecation.py`)
Over time, items in the dimension matrix become deprecated (often shown as grayed-out lines in the sheet). This script generates a file containing all network elements in the sheet and their status (**active** / **deprecated**).

```bash
python3 process_deprecation.py <filename>.xlsx

# Output:
# <filename>-deprecated.json
```

## 2) Get network element config (get_config.py)
Parse the detailed dimensioning sheet and save the configuration to a JSON file.

```bash
python3 get_config.py <filename>.xlsx

# Output:
# <filename>.json
```
Without "<b>--read-deprecate-json</b>" flag, the output file's status will be "null".
```
    {
      "config_heading": "vCSCF Core (W/SC/SE Regions)",
      "config_heading_row": 24,
      "CNF_VNF": "CNF",
      "subscription_count": 3.6,
      "status": null,
    }
```

Optionally, you can provide the deprecated file to skip deprecated network elements. <b> Note, you must generate the deprecated file first. </b>
```bash
python3 get_config.py --read-deprecate-json <filename>.xlsx

# Output:
# <filename>.json
```
Example output with status populated:
```
    {
      "config_heading": "vCSCF Core (W/SC/SE Regions)",
      "config_heading_row": 24,
      "CNF_VNF": "CNF",
      "subscription_count": 3.6,
      "status": "deprecated",
    }
```

## 3) Retrieve site info / site-templates (process-site.py)
Retrieve all site-templates.

```bash
python3 process-site.py <filename>.xlsx

# Output:
# <filename>-cnfvnf.json
```

## 4) Network element name mapping (ddmapping.json)
<b>ddmapping.json</b> maps the network element (NE) names in the cnfvnf output to the names used in the detailed dimensioning config.

## 5) Verify the generated site-template file (verify-site.py)
Menu-driven command to verify the generated cnfvnf file. This script is not fully completed yet (current focus is CB 5.0), but it is included so the work can be continued later.

```bash
python3 verify-site.py <cnfvnf file>.json
```

## 6) Verify the config file (verify_config.py)
Validate the generated dimensioning config JSON.

```bash
python3 verify_config.py
usage: verify_config.py [-h] [--pod-vm] [--display-deprecate] json_file
```

## 7) Compare two DM JSON files (compare-dd.py)
Compare a newly published DM config file against an existing one. Generate the config files first, then pass both JSON outputs to this script.

```bash
python3 compare-dd.py <file1>.json <file2>.json

options:
  --output OUTPUT, -o OUTPUT
```

## 8) verify CPU Memory limit table
It is a good idea to verify the CPU memory limit table is consistent between all the sites before we generate the json file for consumption.

```bash
# this will display discrepencies for all non-lab sites.
# NOTE, the lab column may move in the future, so this script may need to modified
python3 verify_limits.py <xlsx file>

options:
  --show-lab  Display 'diff in lab only' entries (hidden by default)
```

## 9) generate CPU Memoery limit json file
You should verify the table first (previous step) before generating this table. This table is for use with cluster design to check on the max limit of the pod/container.  It only use the first limit (from the xlsx sheet) for the output.

```bash
 python3 generate_limit.py <file>.xlsx

    output: <file>-limit.json
```

# DM intake
Creating a POC for DM intake.  What we trying to do is introducing a "ATT SKU" to the DM data.

## 1) get the json format of the DM data (preferrably filter out the deprecated data)
See above for instructions

## 2) map the network element to the "ATT SKU".
This step is a little involved, but it has nothing to do with instruction here, so i am going to skip it.  Basically, we need to have a json file which contains a list of mappings. the mapping includes "network element", "att sku" and optionally line number of DM.

```bash
Usage:
    python3 generate-att-sku.py <input.xlsx> [output.json]
```

## 3) generate site info

```bash
python3 generate-site-info.py <file>.xlsx

    output: <file>-siteinfo.json
```
Process the sheet "CNF VNF Counts - 172M" and write all NE info into a json formated file.  the file is organized based on site (location) then placement group then Network Element.

Example output:
```
[
  {
    "site": "Seattle",
    "Site-Templates": [
      {
        "site-template": "Blue Print Group 1",
        "network_elements": [
          {
            "network_element": "CSCF Core",
            "CNF_VNF": "CNF",
            "Subs": "3.6",
            "line": 25,
            "count": 0
          },
        ]
      }
  }
]
```

The site info includes all network elements.

## 4) generate DM reference from USP Evolution sheet

This step is used to better match the Network Element name from the site-info to the DM's Network Element name.

It records the line number of the reference value for the Network Element (DMrow).

```bash
python3 generate-usp-evolution.py <file>.xlsx

    output: <file>-usp-evolution.json
```

Example output:
```
[
  {
    "site": "Seattle",
    "Site-Templates": [
      {
        "site-template": "Blue Print Group 1",
        "network_elements": [
          {
            "network_element": "vCSCF Core",
            "CNF_VNF": "CNF",
            "Subs": "3.6",
            "line": 25,
            "DMrow": 24
          },
        ]
      }
  }
]
```

## 5) create a site info with att sku

```bash
usage: generate-site-sku.py [-h] sku_file site_file evolution_file output_file

positional arguments:
  sku_file
  site_file
  evolution_file
  output_file

options:
  -h, --help      show this help message and exit
```

try to merge sku file with site and evolution data.

## 6) merge sku file with dm file

```bash
python3 merge_sku_dm.py 18.1-sku.json dmdata/USP_Evolution_CNF_VNF_Resources_2023TPA_v18.1_VM_AZ_Assignment_e2603.json 18.1-new-dm.json
```

## 7) now the main event. show us the calculation using sku

```bash
python3 att-dm-work.py site-with-sku.json 18.1-new-dm.json
```

## 8) compare the output of the "att-dm-work.py" to the DM excel sheet

Use the "--output-csv" option to save a copy of the output to a csv file.

```bash
python3 att-dm-work.py site-with-sku.json 18.1-dm-with-sku.json --output-csv houston-att.csv
```

then grab a copy of the same site from USP evolution sheet (DM file)

```bash
python3 process_usp_evolution.py USP_Evolution_CNF_VNF_Resources_2023TPA_v18.1_VM_AZ_Assignment_e2603.xlsx -o houston.csv
```

compare the output of "houston-att.csv" to "houston.csv".


# DM consumption for current DM

## 1) create simple filterable cnf vnf count file.

use "process_cnf_vnf_counts.py" to convert the "cnf vnf counts" sheet into a csv file.

```bash
$ python3 process_cnf_vnf_counts.py <xlsx file>

Output: <filename>-cnf-vnf-counts.csv
```
