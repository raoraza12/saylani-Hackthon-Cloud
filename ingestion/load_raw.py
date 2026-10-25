"""Stage 1: ingest raw HCM exports, untouched, all columns as TEXT.

Idempotent: for each source file, old rows for that file are deleted
before re-inserting, so running twice does not duplicate rows.
Row counts per file and per table are logged and must match.
"""
import csv
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / "data"
DB_PATH = BASE / "indus_weave.db"

CSV_FILES = [
    "employees.csv", "employment_history.csv", "departments.csv",
    "shift_roster.csv", "device_mapping.csv", "biometric_punches.csv",
    "holidays.csv", "overtime_requests.csv", "payroll_lines.csv",
    "applications.csv",
]
JSON_FILES = ["shifts.json", "leave_requests.json"]


def row_hash(values):
    text = "|".join("" if v is None else str(v) for v in values)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_csv(conn, path):
    table = "raw_" + path.stem
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        cols = reader.fieldnames or []
        rows = list(reader)
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    col_defs = ", ".join(f'"{c}" TEXT' for c in cols)
    conn.execute(
        f'CREATE TABLE "{table}" ({col_defs}, '
        '"_source_file" TEXT, "_loaded_at" TEXT, "_row_hash" TEXT)'
    )
    loaded_at = datetime.now(timezone.utc).isoformat()
    for r in rows:
        vals = [r.get(c) for c in cols]
        conn.execute(
            f'INSERT INTO "{table}" VALUES ({",".join("?" * (len(cols) + 3))})',
            vals + [path.name, loaded_at, row_hash(vals)],
        )
    print(f"{path.name}: {len(rows)} rows -> {table}")
    return len(rows)


def load_json(conn, path):
    # Flatten nothing yet: one raw row per top-level record, whole record as JSON text.
    table = "raw_" + path.stem
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        records = data
    elif isinstance(data, dict):
        # e.g. shifts.json: {"shifts": [ ... 4 shifts ... ]}
        list_vals = [v for v in data.values() if isinstance(v, list)]
        records = list_vals[0] if len(list_vals) == 1 else [data]
    else:
        records = [data]
    conn.execute(f'DROP TABLE IF EXISTS "{table}"')
    conn.execute(
        f'CREATE TABLE "{table}" ("_record_json" TEXT, '
        '"_source_file" TEXT, "_loaded_at" TEXT, "_row_hash" TEXT)'
    )
    loaded_at = datetime.now(timezone.utc).isoformat()
    for rec in records:
        text = json.dumps(rec, ensure_ascii=False)
        conn.execute(
            f'INSERT INTO "{table}" VALUES (?,?,?,?)',
            [text, path.name, loaded_at, row_hash([text])],
        )
    print(f"{path.name}: {len(records)} records -> {table}")
    return len(records)


def main():
    if not DATA_DIR.exists():
        print(f"data/ folder not found: {DATA_DIR}", file=sys.stderr)
        print("Unzip indus_weave_hcm_data.zip into data/ first.", file=sys.stderr)
        return 1
    conn = sqlite3.connect(DB_PATH)
    total = 0
    for name in CSV_FILES:
        p = DATA_DIR / name
        if p.exists():
            total += load_csv(conn, p)
        else:
            print(f"MISSING: {name}")
    for name in JSON_FILES:
        p = DATA_DIR / name
        if p.exists():
            total += load_json(conn, p)
        else:
            print(f"MISSING: {name}")
    conn.commit()
    conn.close()
    print(f"Total raw rows loaded: {total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
