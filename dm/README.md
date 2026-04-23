## Overview
Process the dimension matrix.

## 1) Generate a deprecated network element file (`process_deprecation.py`)
Over time, items in the dimension matrix become deprecated (often shown as grayed-out lines in the sheet). This script generates a file containing all network elements in the sheet and their status (**active** / **deprecated**).

```bash
python3 process_deprecation.py <filename>.xlsx

# Output:
# <filename>-deprecated.json
```

## 2) Get network element config (get_config.py)
Parse the detailed dimensioning sheet and save the configuration to a JSON file. Optionally, you can provide the deprecated file to skip deprecated network elements.

```bash
python3 get_config.py <filename>.xlsx

# Output:
# <filename>.json
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