"""
Delta engine — compares parsed Excel rows against the local state store.
"""
import json
import platform
from datetime import datetime, timezone
from pathlib import Path


def compute_delta(parsed_rows: list[dict], state_store: dict) -> dict:
    """
    Compare parsed rows against the state store.

    Returns a dict with keys: new, changed, unchanged, deleted.
    """
    checkpoints = state_store.get("checkpoints", {})
    existing_keys = set(checkpoints.keys())
    seen_keys = set()

    new_items = []
    changed_items = []
    unchanged_items = []

    for row in parsed_rows:
        key = row["checkpoint_key"]
        seen_keys.add(key)

        if key not in checkpoints:
            new_items.append(row)
        elif row["field_hash"] != checkpoints[key].get("field_hash"):
            changed_row = dict(row)
            changed_row["_old"] = checkpoints[key]
            changed_items.append(changed_row)
        else:
            unchanged_items.append(row)

    deleted_keys = existing_keys - seen_keys
    deleted_items = [
        {"checkpoint_key": k, **checkpoints[k]} for k in deleted_keys
    ]

    return {
        "new": new_items,
        "changed": changed_items,
        "unchanged": unchanged_items,
        "deleted": deleted_items,
    }


def load_state_store(path: str) -> dict:
    """Load the state store JSON from disk, with file locking on Linux."""
    p = Path(path)
    if not p.exists():
        return {"checkpoints": {}, "last_sync": None, "version": "1.0"}

    if platform.system() != "Windows":
        import fcntl
        with open(p, "r", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_SH)
            try:
                return json.load(f)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    else:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)


def save_state_store(path: str, store: dict) -> None:
    """Save the state store JSON to disk, with file locking on Linux."""
    p = Path(path)

    if platform.system() != "Windows":
        import fcntl
        with open(p, "w", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                json.dump(store, f, indent=2, default=str)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
    else:
        with open(p, "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2, default=str)


def update_state_store(store: dict, pushed_items: list[dict]) -> dict:
    """
    Merge successfully pushed items into the state store.

    Each pushed item must have: checkpoint_key, work_item_id, work_item_url,
    field_hash, and DQCP row fields (dqcp_id, dqcp_title, status, is_approved).
    """
    checkpoints = store.setdefault("checkpoints", {})
    now = datetime.now(timezone.utc).isoformat()

    for item in pushed_items:
        key = item["checkpoint_key"]
        checkpoints[key] = {
            "work_item_id": item["work_item_id"],
            "work_item_url": item.get("work_item_url", ""),
            "last_synced": now,
            "field_hash": item["field_hash"],
            "dqcp_id": item.get("dqcp_id", ""),
            "dqcp_title": item.get("dqcp_title", item.get("checkpoint_name", "")),
            "status": item.get("status", ""),
            "is_approved": item.get("is_approved", ""),
            "rollout": item.get("rollout", ""),
            "data_level_report_name": item.get("data_level_report_name", ""),
            "data_sub_level_report_name": item.get("data_sub_level_report_name", ""),
        }

    store["last_sync"] = now
    return store
