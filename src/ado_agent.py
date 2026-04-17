"""
Azure DevOps push agent — creates and updates DQCP work items via REST API.

Uses the stable ADO REST API 7.1 directly with requests + Basic auth.
No azure-devops SDK required.
"""
import base64
import time
from typing import Optional

import requests

API_VERSION = "7.1"

# DQCP_Status → ADO work item state
# "Active"  = fully approved, being reported
# "WIP"     = still being defined
# "Info"    = informational only, no filter action
# "Removed" = no longer needed
DQCP_STATUS_MAP = {
    "active":   "Active",
    "wip":      "New",
    "info":     "Active",
    "removed":  "Resolved",
    "cutover":  "Active",
}


def _auth_header(pat: str) -> dict:
    token = base64.b64encode(f":{pat}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json-patch+json",
    }


def _map_ado_state(dqcp_status: Optional[str]) -> str:
    return DQCP_STATUS_MAP.get((dqcp_status or "").lower().strip(), "New")


def _build_description_html(item: dict) -> str:
    """Compose a rich HTML description for the ADO work item."""
    parts = []

    if item.get("dqcp_description"):
        parts.append(
            f"<h3>Description</h3><pre>{item['dqcp_description']}</pre>"
        )
    if item.get("dqcp_pseudo_code"):
        parts.append(
            f"<h3>Pseudo Code / SQL</h3><pre>{item['dqcp_pseudo_code']}</pre>"
        )

    meta = []
    if item.get("data_level_name"):
        meta.append(f"<b>Data Level:</b> {item['data_level_report_name'] or item['data_level_name']}")
    if item.get("data_sub_level_name"):
        meta.append(f"<b>Sub-Level:</b> {item['data_sub_level_report_name'] or item['data_sub_level_name']}")
    if item.get("data_element"):
        meta.append(f"<b>Data Element:</b> {item['data_element']}")
    if item.get("table_name"):
        meta.append(f"<b>Table:</b> {item['table_name']}.{item.get('column_name', '')}")
    if item.get("sys_table_name"):
        meta.append(f"<b>System Table:</b> {item['sys_table_name']}.{item.get('sys_column_name', '')}")
    if meta:
        parts.append("<h3>Source Mapping</h3>" + "<br>".join(meta))

    if item.get("dqcp_comments"):
        parts.append(f"<h3>Comments</h3><pre>{item['dqcp_comments']}</pre>")
    if item.get("dqcp_questions"):
        q_status = item.get("question_status") or ""
        parts.append(
            f"<h3>Open Questions [{q_status}]</h3><pre>{item['dqcp_questions']}</pre>"
        )
    if item.get("change_history"):
        parts.append(f"<h3>Change History</h3><pre>{item['change_history']}</pre>")

    return "".join(parts)


def _build_patch_doc(item: dict, config: dict) -> list[dict]:
    """Build a JSON Patch document for a DQCP work item create or update."""
    title = f"[{item.get('dqcp_id', '')}] {item.get('dqcp_title', '')}"
    description_html = _build_description_html(item)

    ops = [
        {"op": "add", "path": "/fields/System.Title",
         "value": title},
        {"op": "add", "path": "/fields/System.State",
         "value": _map_ado_state(item.get("status"))},
        {"op": "add", "path": "/fields/System.Description",
         "value": description_html},
        {"op": "add", "path": "/fields/System.AssignedTo",
         "value": config["ado"]["assigned_to"]},

        # ── Custom DQCP fields ────────────────────────────────────────────
        {"op": "add", "path": "/fields/Custom.DQCPId",
         "value": item.get("dqcp_id") or ""},
        {"op": "add", "path": "/fields/Custom.DataLevel",
         "value": item.get("data_level_report_name") or str(item.get("data_level") or "")},
        {"op": "add", "path": "/fields/Custom.DataSubLevel",
         "value": item.get("data_sub_level_report_name") or str(item.get("data_sub_level") or "")},
        {"op": "add", "path": "/fields/Custom.DataElement",
         "value": item.get("data_element") or ""},
        {"op": "add", "path": "/fields/Custom.TableName",
         "value": item.get("table_name") or ""},
        {"op": "add", "path": "/fields/Custom.ColumnName",
         "value": item.get("column_name") or ""},
        {"op": "add", "path": "/fields/Custom.DQCPStatus",
         "value": item.get("status") or ""},
        {"op": "add", "path": "/fields/Custom.IsApproved",
         "value": item.get("is_approved") or ""},
        {"op": "add", "path": "/fields/Custom.RollOut",
         "value": item.get("rollout") or ""},
        {"op": "add", "path": "/fields/Custom.CheckpointKey",
         "value": item.get("checkpoint_key") or ""},
        {"op": "add", "path": "/fields/Custom.SourceFile",
         "value": item.get("file_path") or ""},
    ]

    # Optional date fields — only add when populated
    if item.get("start_date"):
        ops.append({"op": "add", "path": "/fields/Custom.StartDate",
                    "value": item["start_date"]})
    if item.get("end_date"):
        ops.append({"op": "add", "path": "/fields/Custom.EndDate",
                    "value": item["end_date"]})

    return ops


def push_to_ado(
    items: list[dict],
    config: dict,
    pat: str,
    rate_limit_delay: float = 0.2,
) -> list[dict]:
    """
    Push new and changed DQCP checkpoint items to Azure DevOps via REST API.

    Each item must include: checkpoint_key, is_new (bool), and optionally
    work_item_id (for updates). Items with excluded_from_sync=True are skipped.

    Returns a list of result dicts per item.
    """
    org_url = config["ado"]["org_url"].rstrip("/")
    project = config["ado"]["project"]
    wi_type = config["ado"]["work_item_type"]
    headers = _auth_header(pat)

    results = []

    for item in items:
        # Skip rows filtered out by sync_statuses config
        if item.get("excluded_from_sync"):
            results.append({
                "checkpoint_key": item.get("checkpoint_key", ""),
                "work_item_id": None,
                "work_item_url": None,
                "field_hash": item.get("field_hash", ""),
                "dqcp_id": item.get("dqcp_id", ""),
                "dqcp_title": item.get("dqcp_title", ""),
                "status": item.get("status", ""),
                "success": True,
                "skipped": True,
                "error": None,
            })
            continue

        patch_doc = _build_patch_doc(item, config)
        is_new = item.get("is_new", True)

        try:
            if is_new:
                url = (
                    f"{org_url}/{project}/_apis/wit/workitems"
                    f"/${wi_type}?api-version={API_VERSION}"
                )
                resp = requests.post(url, json=patch_doc, headers=headers, timeout=30)
            else:
                wi_id = item["work_item_id"]
                url = (
                    f"{org_url}/{project}/_apis/wit/workitems"
                    f"/{wi_id}?api-version={API_VERSION}"
                )
                resp = requests.patch(url, json=patch_doc, headers=headers, timeout=30)

            resp.raise_for_status()
            data = resp.json()

            results.append({
                "checkpoint_key": item["checkpoint_key"],
                "work_item_id": data["id"],
                "work_item_url": data["_links"]["html"]["href"],
                "field_hash": item.get("field_hash", ""),
                "dqcp_id": item.get("dqcp_id", ""),
                "dqcp_title": item.get("dqcp_title", ""),
                "checkpoint_name": item.get("checkpoint_name", ""),
                "status": item.get("status", ""),
                "skipped": False,
                "success": True,
                "error": None,
            })

        except requests.HTTPError as exc:
            error_body = ""
            try:
                error_body = exc.response.json().get("message", str(exc))
            except Exception:
                error_body = str(exc)
            results.append({
                "checkpoint_key": item.get("checkpoint_key", ""),
                "work_item_id": item.get("work_item_id"),
                "work_item_url": None,
                "field_hash": item.get("field_hash", ""),
                "dqcp_id": item.get("dqcp_id", ""),
                "dqcp_title": item.get("dqcp_title", ""),
                "checkpoint_name": item.get("checkpoint_name", ""),
                "status": item.get("status", ""),
                "skipped": False,
                "success": False,
                "error": error_body,
            })
        except Exception as exc:
            results.append({
                "checkpoint_key": item.get("checkpoint_key", ""),
                "work_item_id": item.get("work_item_id"),
                "work_item_url": None,
                "field_hash": item.get("field_hash", ""),
                "dqcp_id": item.get("dqcp_id", ""),
                "dqcp_title": item.get("dqcp_title", ""),
                "checkpoint_name": item.get("checkpoint_name", ""),
                "status": item.get("status", ""),
                "skipped": False,
                "success": False,
                "error": str(exc),
            })

        time.sleep(rate_limit_delay)

    return results
