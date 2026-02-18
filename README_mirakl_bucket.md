## Mirakl Excel Bucketing System

This script buckets Mirakl product exports by FET_FRA category and generates Excel files whose columns match Mirakl template headers exactly.

### 1) Where to put the CSV

- Place your Mirakl export CSV file somewhere accessible on your system.
- Default path used in the script is:
  - `"/mnt/data/export-products-20260218123930.csv"`
- You can either:
  - Save your export under that exact path, **or**
  - Pass a custom path as a parameter when running the script (see section 4).

Requirements for the CSV:
- Must be comma‑separated.
- Must contain a `CATEGORY` column (the FET_FRA code key).
- Read with `dtype=str`, so values are preserved exactly.

### 2) Where to put the templates

- Create a `templates` folder in the project root (same level as `mirakl_bucket.py`):
  - `./templates/`
- Put all your Mirakl Excel templates (`.xlsx`) into this folder.
- Each template:
  - The **first row** must contain the final header row to be used.
  - Any additional example rows in the template will be ignored.

### 3) How to create `fetfra_to_template.xlsx`

- Create an Excel file named `fetfra_to_template.xlsx` in the project root:
  - `./fetfra_to_template.xlsx`
- The file must have at least these two columns (exact names):
  - `FET_FRA_CODE`
  - `TEMPLATE_FILE`

Example rows:

```text
FET_FRA_CODE     TEMPLATE_FILE
FET_FRA_1106     klima_template.xlsx
FET_FRA_1201     tv_template.xlsx
```

Rules:
- Every FET_FRA code (i.e., every `CATEGORY` value in your CSV) must map to **exactly one** template file.
- `TEMPLATE_FILE` must be the exact file name of a template located under `./templates/`.

### 4) How to run the script and what it produces

#### Running with default paths

From the project root directory:

```bash
python mirakl_bucket.py
```

This uses:
- CSV: `"/mnt/data/export-products-20260218123930.csv"`
- Mapping: `"./fetfra_to_template.xlsx"`
- Templates: `"./templates/"`

#### Running with custom CSV / mapping

You can also call the `run` function from another script or an interactive session:

```python
from mirakl_bucket import run

run(
    csv_path="/path/to/your/export-products.csv",
    mapping_path="./fetfra_to_template.xlsx",
)
```

### 5) Outputs

The script automatically creates folders if needed:
- `./output/`
- `./logs/`

#### a) Per‑template Excel outputs (`./output/*.xlsx`)

For each template file `TEMPLATE_FILE` referenced in the mapping and found under `./templates/`, the script creates:

- `./output/{TEMPLATE_FILE_without_ext}_out.xlsx`

Behavior:
- Reads the header from the **first row** of the template.
- Builds an output dataframe with exactly those columns, in the same order.
- For each product row assigned to that template:
  - If a target column exists in the CSV, the value is copied as‑is.
  - If a target column does **not** exist in the CSV, that cell is left empty.
- Extra columns in the CSV that are **not** in the template header are ignored.

#### b) Unmapped or missing‑template rows (`./output/_UNMAPPED_OR_MISSING_TEMPLATE.xlsx`)

Rows are written here when:
- `CATEGORY` (FET_FRA code) is missing or not found in `fetfra_to_template.xlsx`, or
- The mapped template file does **not** exist under `./templates/`.

The file contains all original columns from the CSV for those rows.

#### c) Bucket report (`./logs/bucket_report.xlsx`)

This report has two sheets:

- `summary`:
  - `TEMPLATE_FILE`
  - `row_count` (number of rows mapped to that template)
  - `template_found` (TRUE/FALSE – whether the template file existed in `./templates/`)
  - `unmapped_fetfra_count` (rows that should have used this template but were sent to the unmapped file because the template file was missing)

- `unmapped_fetfra`:
  - `FET_FRA_CODE` (CATEGORY value from the CSV)
  - `row_count`
  - `reason`:
    - `missing_mapping` – FET_FRA code not present in `fetfra_to_template.xlsx` or CATEGORY empty
    - `template_not_found` – mapping exists but the template Excel file was not found under `./templates/`

### 6) Data‑loss safety

- The script performs a row‑count sanity check to ensure:
  - **Total input rows** equals
  - **Rows distributed to template outputs + rows written to `_UNMAPPED_OR_MISSING_TEMPLATE.xlsx`** (logically).
- If a discrepancy is detected, it raises a runtime error instead of silently losing data.

