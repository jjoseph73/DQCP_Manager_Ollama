"""
Shared pytest fixtures for dqcp-ado-sync tests.
"""
import pytest
import openpyxl


SAMPLE_CONFIG = {
    "excel": {
        "header_row": 1,
        "checkpoint_column": "Checkpoint Name",
        "status_column": "Status",
        "severity_column": "Severity",
        "owner_column": "Owner",
        "due_date_column": "Due Date",
        "comments_column": "Comments",
        "source_tag_column": "Source",
    }
}


@pytest.fixture
def config():
    return SAMPLE_CONFIG


@pytest.fixture
def sample_parsed_rows():
    return [
        {
            "file_path": "/data/dqcp.xlsx",
            "sheet_name": "Sheet1",
            "row_number": 2,
            "checkpoint_name": "CP-001",
            "status": "Pass",
            "severity": "High",
            "owner": "Alice",
            "due_date": "2025-06-01",
            "comments": "All good",
            "source": "System A",
            "checkpoint_key": "dqcp.xlsx::Sheet1::CP-001",
            "field_hash": "hash_aaa",
        },
        {
            "file_path": "/data/dqcp.xlsx",
            "sheet_name": "Sheet1",
            "row_number": 3,
            "checkpoint_name": "CP-002",
            "status": "Fail",
            "severity": "Medium",
            "owner": "Bob",
            "due_date": "2025-07-01",
            "comments": "Needs review",
            "source": "System B",
            "checkpoint_key": "dqcp.xlsx::Sheet1::CP-002",
            "field_hash": "hash_bbb",
        },
    ]


@pytest.fixture
def sample_state_store():
    return {
        "checkpoints": {
            "dqcp.xlsx::Sheet1::CP-002": {
                "work_item_id": 100,
                "work_item_url": "https://dev.azure.com/...",
                "last_synced": "2025-03-01T10:00:00",
                "field_hash": "hash_bbb",
                "title": "CP-002",
                "status": "Fail",
                "severity": "Medium",
            },
            "dqcp.xlsx::Sheet1::CP-DELETED": {
                "work_item_id": 99,
                "work_item_url": "https://dev.azure.com/...",
                "last_synced": "2025-01-01T09:00:00",
                "field_hash": "hash_old",
                "title": "CP-DELETED",
                "status": "Pass",
                "severity": "Low",
            },
        },
        "last_sync": "2025-03-01T10:00:00",
        "version": "1.0",
    }


@pytest.fixture
def tmp_excel_file(tmp_path, config):
    """Creates a minimal Excel workbook in tmp_path for testing."""
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
    ws.append(["CP-001", "Pass", "High", "Alice", "2025-06-01", "All good", "System A"])
    ws.append(["CP-002", "Fail", "Medium", "Bob", "2025-07-01", "Needs review", "System B"])
    ws.append(["CP-003", "In Progress", "Low", "Carol", "2025-08-01", "WIP", "System C"])

    file_path = tmp_path / "test_dqcp.xlsx"
    wb.save(file_path)
    return str(file_path)
