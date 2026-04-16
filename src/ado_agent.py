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

STATUS_MAP = {
    "pass": "Resolved",
    "fail": "Active",
    "in progress": "Active",
    "blocked": "Blocked",
    "not started": "New",
    "n/a": "New",
}

SEVERITY_MAP = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 4,
}


def _auth_header(pat: str) -> dict:
    token = base64.b64encode(f":{pat}".encode()).decode()
    return {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json-patch+json",
    }


def _map_status(excel_status: Optional[str]) -> str:
    if not excel_status:
        return "New"
    return STATUS_MAP.get(excel_status.lower().strip(), "New")


def _map_severity(excel_severity: Optional[str]) -> int:
    if not excel_severity:
        return 3
    return SEVERITY_MAP.get(excel_severity.lower().strip(), 3)


def _build_patch_doc(item: dict, config: dict) -> list[dict]:
    """Build a JSON Patch document for a work item create or update."""
    return [
        {"op": "add", "path": "/fields/System.Title",
         "value": item.get("checkpoint_name", "")},
        {"op": "add", "path": "/fields/System.State",
         "value": _map_status(item.get("status"))},
        {"op": "add", "path": "/fields/Microsoft.VSTS.Common.Priority",
         "value": _map_severity(item.get("severity"))},
        {"op": "add", "path": "/fields/System.Description",
         "value": item.get("comments") or ""},
        {"op": "add", "path": "/fields/System.AssignedTo",
         "value": config["ado"]["assigned_to"]},
        {"op": "add", "path": "/fields/Custom.SourceFile",
         "value": item.get("file_path") or ""},
        {"op": "add", "path": "/fields/Custom.SheetName",
         "value": item.get("sheet_name") or ""},
        {"op": "add", "path": "/fields/Custom.CheckpointKey",
         "value": item.get("checkpoint_key") or ""},
    ]


def push_to_ado(
    items: list[dict],
    config: dict,
    pat: str,
    rate_limit_delay: float = 0.2,
) -> list[dict]:
    """
    Push new and changed checkpoint items to Azure DevOps via REST API.

    Each item must include: checkpoint_key, is_new (bool), and optionally
    work_item_id (for updates).

    Returns a list of result dicts per item.
    """
    org_url = config["ado"]["org_url"].rstrip("/")
    project = config["ado"]["project"]
    wi_type = config["ado"]["work_item_type"]
    headers = _auth_header(pat)

    results = []

    for item in items:
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
                "checkpoint_name": item.get("checkpoint_name", ""),
                "status": item.get("status", ""),
                "severity": item.get("severity", ""),
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
                "checkpoint_name": item.get("checkpoint_name", ""),
                "status": item.get("status", ""),
                "severity": item.get("severity", ""),
                "success": False,
                "error": error_body,
            })
        except Exception as exc:
            results.append({
                "checkpoint_key": item.get("checkpoint_key", ""),
                "work_item_id": item.get("work_item_id"),
                "work_item_url": None,
                "field_hash": item.get("field_hash", ""),
                "checkpoint_name": item.get("checkpoint_name", ""),
                "status": item.get("status", ""),
                "severity": item.get("severity", ""),
                "success": False,
                "error": str(exc),
            })

        time.sleep(rate_limit_delay)

    return results
