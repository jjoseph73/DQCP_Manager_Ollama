"""
Tests for src/parser.py — DQCP_Master schema.
"""
import openpyxl
import pytest

from src.parser import generate_field_hash, parse_excel_files
from tests.conftest import _HEADERS, _make_row


def test_parse_single_sheet(tmp_excel_file, config):
    """Parser returns rows from DQCP_Master; excluded rows still parsed but flagged."""
    rows = parse_excel_files([tmp_excel_file], config)

    # All 3 rows parsed regardless of sync filter
    assert len(rows) == 3

    # First row checks
    r = rows[0]
    assert r["dqcp_id"] == "01.03.0001"
    assert r["dqcp_title"] == "Invalid SSN"
    assert r["status"] == "Active"
    assert r["table_name"] == "Person"
    assert r["column_name"] == "SSN"
    assert r["excluded_from_sync"] is False

    # Second row — WIP, should NOT be excluded (WIP is in sync_statuses)
    assert rows[1]["dqcp_id"] == "01.03.0002"
    assert rows[1]["excluded_from_sync"] is False

    # Third row — Removed, SHOULD be excluded
    assert rows[2]["dqcp_id"] == "01.03.0003"
    assert rows[2]["excluded_from_sync"] is True

    # checkpoint_key format: filename::DQCP_Id
    assert "::" in rows[0]["checkpoint_key"]
    assert "01.03.0001" in rows[0]["checkpoint_key"]

    # field_hash present and non-empty
    assert rows[0]["field_hash"]


def test_skip_empty_dqcp_id(tmp_path, config):
    """Rows where DQCP_Id is empty or None are silently skipped."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DQCP_Master"

    ws.append(_HEADERS)
    ws.append(_make_row("01.03.0001", status="Active"))   # valid
    ws.append([None] + [""] * (len(_HEADERS) - 1))        # DQCP_Id = None → skip
    ws.append([""] + [""] * (len(_HEADERS) - 1))          # DQCP_Id = ""   → skip

    file_path = tmp_path / "skip_test.xlsx"
    wb.save(file_path)

    rows = parse_excel_files([str(file_path)], config)
    assert len(rows) == 1
    assert rows[0]["dqcp_id"] == "01.03.0001"


def test_field_hash_consistency():
    """Same hash-relevant fields → same hash; any change → different hash."""
    base = {
        "status": "Active",
        "is_approved": "Y",
        "rollout": "Y",
        "dqcp_description": "SSN must not be null.",
        "dqcp_pseudo_code": "SELECT * FROM Person WHERE SSN IS NULL",
        "dqcp_comments": None,
        "resolution": None,
        "end_date": None,
    }
    row1 = dict(base)
    row2 = dict(base)
    assert generate_field_hash(row1) == generate_field_hash(row2)

    # status change → different hash
    row3 = dict(base)
    row3["status"] = "WIP"
    assert generate_field_hash(row1) != generate_field_hash(row3)

    # description change → different hash
    row4 = dict(base)
    row4["dqcp_description"] = "Updated description text."
    assert generate_field_hash(row1) != generate_field_hash(row4)

    # is_approved change → different hash
    row5 = dict(base)
    row5["is_approved"] = "N"
    assert generate_field_hash(row1) != generate_field_hash(row5)
