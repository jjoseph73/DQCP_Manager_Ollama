"""
Azure DevOps push agent — creates and updates DQCP work items.
"""
import os
import time
from typing import Optional

from azure.devops.connection import Connection
from azure.devops.v7_1.work_item_tracking.models import JsonPatchOperation
from msrest.authentication import BasicAuthentication


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


def _map_status(excel_status: Optional[str]) -> str:
    if not excel_status:
        return "New"
    return STATUS_MAP.get(excel_status.lower().strip(), "New")


def _map_severity(excel_severity: Optional[str]) -> int:
    if not excel_severity:
        return 3
    return SEVERITY_MAP.get(excel_severity.lower().strip(), 3)


def _make_patch_document(item: dict, config: dict) -> list[JsonPatchOperation]:
    ops = [
        JsonPatchOperation(
            op="add",
            path="/fields/System.Title",
            value=item.get("checkpoint_name", ""),
        ),
        JsonPatchOperation(
            op="add",
            path="/fields/System.State",
            value=_map_status(item.get("status")),
        ),
        JsonPatchOperation(
            op="add",
            path="/fields/Microsoft.VSTS.Common.Priority",
            value=_map_severity(item.get("severity")),
        ),
        JsonPatchOperation(
            op="add",
            path="/fields/System.Description",
            value=item.get("comments") or "",
        ),
        JsonPatchOperation(
            op="add",
            path="/fields/System.AssignedTo",
            value=config["ado"]["assigned_to"],
        ),
        JsonPatchOperation(
            op="add",
            path="/fields/Custom.SourceFile",
            value=item.get("file_path") or "",
        ),
        JsonPatchOperation(
            op="add",
            path="/fields/Custom.SheetName",
            value=item.get("sheet_name") or "",
        ),
        JsonPatchOperation(
            op="add",
            path="/fields/Custom.CheckpointKey",
            value=item.get("checkpoint_key") or "",
        ),
    ]
    return ops


def push_to_ado(
    items: list[dict],
    config: dict,
    pat: str,
    rate_limit_delay: float = 0.2,
) -> list[dict]:
    """
    Push new and changed checkpoint items to Azure DevOps.

    Each item in `items` must have: checkpoint_key, is_new (bool), and optionally
    work_item_id (for updates).

    Returns a list of result dicts per item.
    """
    credentials = BasicAuthentication("", pat)
    connection = Connection(base_url=config["ado"]["org_url"], creds=credentials)
    wit_client = connection.clients.get_work_item_tracking_client()

    project = config["ado"]["project"]
    work_item_type = config["ado"]["work_item_type"]

    results = []
    for item in items:
        try:
            patch_doc = _make_patch_document(item, config)
            is_new = item.get("is_new", True)

            if is_new:
                wi = wit_client.create_work_item(
                    document=patch_doc,
                    project=project,
                    type=work_item_type,
                )
            else:
                wi = wit_client.update_work_item(
                    document=patch_doc,
                    id=item["work_item_id"],
                    project=project,
                )

            results.append({
                "checkpoint_key": item["checkpoint_key"],
                "work_item_id": wi.id,
                "work_item_url": wi.url,
                "field_hash": item.get("field_hash", ""),
                "checkpoint_name": item.get("checkpoint_name", ""),
                "status": item.get("status", ""),
                "severity": item.get("severity", ""),
                "success": True,
                "error": None,
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
