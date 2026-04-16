"""
Excel parser for DQCP checkpoint workbooks.
"""
import hashlib
import json
from pathlib import Path

import openpyxl


def parse_excel_files(file_paths: list[str], config: dict) -> list[dict]:
    """
    Parse a list of Excel file paths and extract DQCP checkpoint rows.

    Returns a list of dicts, each representing one checkpoint row.
    """
    excel_cfg = config["excel"]
    checkpoint_col = excel_cfg["checkpoint_column"]
    status_col = excel_cfg["status_column"]
    severity_col = excel_cfg["severity_column"]
    owner_col = excel_cfg["owner_column"]
    due_date_col = excel_cfg["due_date_column"]
    comments_col = excel_cfg["comments_column"]
    source_tag_col = excel_cfg["source_tag_column"]

    results = []

    for file_path in file_paths:
        wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))

            # Find the header row by scanning for the checkpoint column value
            header_row_idx = None
            col_map = {}
            for i, row in enumerate(rows):
                row_values = [str(v).strip() if v is not None else "" for v in row]
                if checkpoint_col in row_values:
                    header_row_idx = i
                    for j, val in enumerate(row_values):
                        col_map[val] = j
                    break

            if header_row_idx is None:
                # No header found in this sheet, skip it
                continue

            def _col(row_tuple, col_name):
                idx = col_map.get(col_name)
                if idx is None or idx >= len(row_tuple):
                    return None
                val = row_tuple[idx]
                if val is None:
                    return None
                return str(val).strip()

            for row_number, row in enumerate(
                rows[header_row_idx + 1:], start=header_row_idx + 2
            ):
                checkpoint_name = _col(row, checkpoint_col)
                if not checkpoint_name:
                    continue

                due_date_raw = _col(row, due_date_col)
                due_date = str(due_date_raw) if due_date_raw else None

                row_dict = {
                    "file_path": str(file_path),
                    "sheet_name": sheet_name,
                    "row_number": row_number,
                    "checkpoint_name": checkpoint_name,
                    "status": _col(row, status_col),
                    "severity": _col(row, severity_col),
                    "owner": _col(row, owner_col),
                    "due_date": due_date,
                    "comments": _col(row, comments_col),
                    "source": _col(row, source_tag_col),
                    "checkpoint_key": f"{Path(file_path).name}::{sheet_name}::{checkpoint_name}",
                }
                row_dict["field_hash"] = generate_field_hash(row_dict)
                results.append(row_dict)

        wb.close()

    return results


def generate_field_hash(row_dict: dict) -> str:
    """
    Generate a stable SHA-256 hash of the key mutable fields for change detection.
    """
    key_fields = {
        "status": row_dict.get("status"),
        "severity": row_dict.get("severity"),
        "comments": row_dict.get("comments"),
        "due_date": row_dict.get("due_date"),
    }
    serialised = json.dumps(key_fields, sort_keys=True, default=str)
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()
