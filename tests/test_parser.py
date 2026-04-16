"""
Tests for src/parser.py
"""
import openpyxl
import pytest

from src.parser import generate_field_hash, parse_excel_files


def test_parse_single_sheet(tmp_excel_file, config):
    rows = parse_excel_files([tmp_excel_file], config)
    assert len(rows) == 3
    assert rows[0]["checkpoint_name"] == "CP-001"
    assert rows[0]["status"] == "Pass"
    assert rows[0]["severity"] == "High"
    assert rows[0]["owner"] == "Alice"
    assert rows[0]["comments"] == "All good"
    assert rows[1]["checkpoint_name"] == "CP-002"
    assert rows[2]["checkpoint_name"] == "CP-003"
    # checkpoint_key format
    assert "::" in rows[0]["checkpoint_key"]
    assert "CP-001" in rows[0]["checkpoint_key"]
    # field_hash is present and non-empty
    assert rows[0]["field_hash"]


def test_skip_empty_checkpoint_name(tmp_path, config):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    excel_cfg = config["excel"]
    headers = [
        excel_cfg["checkpoint_column"],
        excel_cfg["status_column"],
        excel_cfg["severity_column"],
        excel_cfg["owner_column"],
        excel_cfg["due_date_column"],
        excel_cfg["comments_column"],
        excel_cfg["source_tag_column"],
    ]
    ws.append(headers)
    ws.append(["CP-001", "Pass", "High", "Alice", "2025-06-01", "OK", "Sys"])
    ws.append([None, "Fail", "Low", "Bob", "2025-07-01", "Empty name", "Sys"])
    ws.append(["", "Pass", "Medium", "Carol", "2025-08-01", "Empty str", "Sys"])

    file_path = tmp_path / "skip_test.xlsx"
    wb.save(file_path)

    rows = parse_excel_files([str(file_path)], config)
    assert len(rows) == 1
    assert rows[0]["checkpoint_name"] == "CP-001"


def test_field_hash_consistency():
    base = {
        "status": "Pass",
        "severity": "High",
        "comments": "All good",
        "due_date": "2025-06-01",
    }
    row1 = dict(base)
    row2 = dict(base)
    assert generate_field_hash(row1) == generate_field_hash(row2)

    row3 = dict(base)
    row3["status"] = "Fail"
    assert generate_field_hash(row1) != generate_field_hash(row3)

    row4 = dict(base)
    row4["comments"] = "Changed comment"
    assert generate_field_hash(row1) != generate_field_hash(row4)
