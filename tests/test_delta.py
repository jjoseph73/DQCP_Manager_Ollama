"""
Tests for src/delta.py — DQCP_Master schema.

checkpoint_key format: "{filename}::{DQCP_Id}"
e.g. "dqcp.xlsx::01.03.0001"
"""
import pytest

from src.delta import compute_delta


def test_new_item(sample_parsed_rows, sample_state_store):
    """Row not in state store → appears in delta["new"]."""
    delta = compute_delta(sample_parsed_rows, sample_state_store)
    new_keys = [r["checkpoint_key"] for r in delta["new"]]
    # 01.03.0001 is in parsed_rows but not in sample_state_store
    assert "dqcp.xlsx::01.03.0001" in new_keys


def test_changed_item(sample_parsed_rows, sample_state_store):
    """Row in state store with a different hash → appears in delta["changed"]."""
    rows = [dict(r) for r in sample_parsed_rows]
    for row in rows:
        if row["dqcp_id"] == "01.03.0002":
            row["field_hash"] = "different_hash_xyz"

    delta = compute_delta(rows, sample_state_store)
    changed_keys = [r["checkpoint_key"] for r in delta["changed"]]
    assert "dqcp.xlsx::01.03.0002" in changed_keys


def test_unchanged_item(sample_parsed_rows, sample_state_store):
    """Row in state store with matching hash → appears in delta["unchanged"]."""
    # sample_parsed_rows[1] has hash_bbb; sample_state_store also has hash_bbb
    delta = compute_delta(sample_parsed_rows, sample_state_store)
    unchanged_keys = [r["checkpoint_key"] for r in delta["unchanged"]]
    assert "dqcp.xlsx::01.03.0002" in unchanged_keys


def test_deleted_item(sample_parsed_rows, sample_state_store):
    """Key in state store not present in parsed_rows → appears in delta["deleted"]."""
    delta = compute_delta(sample_parsed_rows, sample_state_store)
    deleted_keys = [r["checkpoint_key"] for r in delta["deleted"]]
    assert "dqcp.xlsx::01.03.DELETED" in deleted_keys
