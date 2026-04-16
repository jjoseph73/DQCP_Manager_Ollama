"""
Tests for src/delta.py
"""
import pytest

from src.delta import compute_delta


def test_new_item(sample_parsed_rows, sample_state_store):
    # CP-001 is not in the state store — should appear in delta["new"]
    delta = compute_delta(sample_parsed_rows, sample_state_store)
    new_keys = [r["checkpoint_key"] for r in delta["new"]]
    assert "dqcp.xlsx::Sheet1::CP-001" in new_keys


def test_changed_item(sample_parsed_rows, sample_state_store):
    # Modify CP-002's hash so it differs from the stored hash
    rows = [dict(r) for r in sample_parsed_rows]
    for row in rows:
        if row["checkpoint_name"] == "CP-002":
            row["field_hash"] = "different_hash_xyz"

    delta = compute_delta(rows, sample_state_store)
    changed_keys = [r["checkpoint_key"] for r in delta["changed"]]
    assert "dqcp.xlsx::Sheet1::CP-002" in changed_keys


def test_unchanged_item(sample_parsed_rows, sample_state_store):
    # CP-002 in sample_parsed_rows has hash_bbb, same as state store — unchanged
    delta = compute_delta(sample_parsed_rows, sample_state_store)
    unchanged_keys = [r["checkpoint_key"] for r in delta["unchanged"]]
    assert "dqcp.xlsx::Sheet1::CP-002" in unchanged_keys


def test_deleted_item(sample_parsed_rows, sample_state_store):
    # CP-DELETED is in state store but not in parsed_rows
    delta = compute_delta(sample_parsed_rows, sample_state_store)
    deleted_keys = [r["checkpoint_key"] for r in delta["deleted"]]
    assert "dqcp.xlsx::Sheet1::CP-DELETED" in deleted_keys
