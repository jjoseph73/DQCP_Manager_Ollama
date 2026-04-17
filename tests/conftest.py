"""
Shared pytest fixtures for dqcp-ado-sync (DQCP_Master schema).
"""
import pytest
import openpyxl


# ── Minimal config matching config.yaml ───────────────────────────────────────
SAMPLE_CONFIG = {
    "excel": {
        "master_sheet": "DQCP_Master",
        "id_column": "DQCP_Id",
        "title_column": "DQCP_Title",
        "description_column": "DQCP_Description",
        "pseudo_code_column": "DQCP_Pseudo_Code",
        "status_column": "DQCP_Status",
        "is_approved_column": "Is_Approved",
        "rollout_column": "RollOut",
        "data_level_column": "Data_Level",
        "data_sub_level_column": "Data_Sub_Level",
        "sequence_column": "Sequence_Number",
        "data_element_column": "Data_Element",
        "table_name_column": "Table_Name",
        "column_name_column": "Column_Name",
        "sys_table_column": "Sys_Table_Name",
        "sys_column_column": "Sys_Column_Name",
        "start_date_column": "Start_Date",
        "end_date_column": "End_Date",
        "last_modified_column": "Last_Modified_Date",
        "resolved_date_column": "DQCP_Resolved_Date",
        "comments_column": "DQCP_Comments",
        "questions_column": "DQCP_Questions",
        "question_status_column": "DQCP_Question_Status",
        "change_history_column": "DQCP_Change_History",
        "resolution_column": "DQCP_Resolution",
        "sync_statuses": ["Active", "WIP"],
    }
}

# Headers in the same order used by tmp_excel_file
_HEADERS = [
    "DQCP_Id", "Data_Level", "Data_Sub_Level", "Sequence_Number", "Data_Element",
    "DQCP_Title", "DQCP_Description", "DQCP_Pseudo_Code",
    "Table_Name", "Column_Name", "Sys_Table_Name", "Sys_Column_Name",
    "Start_Date", "End_Date", "Last_Modified_Date", "DQCP_Resolved_Date",
    "DQCP_Comments", "DQCP_Questions", "DQCP_Question_Status",
    "Is_Approved", "DQCP_Status", "RollOut", "DQCP_Resolution", "DQCP_Change_History",
]


def _make_row(dqcp_id, status="Active", is_approved="Y", rollout="Y",
              title=None, description=None, pseudo_code=None,
              data_level=1, data_sub_level=3, sequence=1,
              data_element="SSN", table="Person", column="SSN",
              comments=None, resolution=None):
    """Build a raw Excel data row matching _HEADERS order."""
    return [
        dqcp_id, data_level, data_sub_level, sequence, data_element,
        title or f"Check {dqcp_id}", description or f"Description for {dqcp_id}",
        pseudo_code or f"SELECT * FROM {table}",
        table, column, table, column,
        "2025-11-12", None, "2026-01-30", None,
        comments, None, None,
        is_approved, status, rollout, resolution, None,
    ]


@pytest.fixture
def config():
    return SAMPLE_CONFIG


@pytest.fixture
def sample_parsed_rows():
    """Two parsed rows using the DQCP_Master schema."""
    return [
        {
            "checkpoint_key": "dqcp.xlsx::01.03.0001",
            "file_path": "/data/dqcp.xlsx",
            "sheet_name": "DQCP_Master",
            "row_number": 2,
            "dqcp_id": "01.03.0001",
            "data_level": 1,
            "data_sub_level": 3,
            "sequence_number": "1",
            "data_element": "SSN",
            "data_level_name": "Demographics",
            "data_level_report_name": "01-Demographics",
            "data_sub_level_name": "Member",
            "data_sub_level_report_name": "03-Member",
            "checkpoint_name": "Invalid SSN/ITIN Format - Member",
            "dqcp_title": "Invalid SSN/ITIN Format - Member",
            "dqcp_description": "SSN must not be null or invalid.",
            "dqcp_pseudo_code": "SELECT * FROM Person WHERE SSN IS NULL",
            "table_name": "Person",
            "column_name": "SSN",
            "sys_table_name": "Person",
            "sys_column_name": "SSN",
            "status": "Active",
            "is_approved": "Y",
            "rollout": "Y",
            "start_date": "2025-11-12",
            "end_date": None,
            "last_modified_date": "2026-01-30",
            "resolved_date": None,
            "dqcp_comments": None,
            "dqcp_questions": None,
            "question_status": None,
            "change_history": None,
            "resolution": None,
            "excluded_from_sync": False,
            "field_hash": "hash_aaa",
        },
        {
            "checkpoint_key": "dqcp.xlsx::01.03.0002",
            "file_path": "/data/dqcp.xlsx",
            "sheet_name": "DQCP_Master",
            "row_number": 3,
            "dqcp_id": "01.03.0002",
            "data_level": 1,
            "data_sub_level": 3,
            "sequence_number": "2",
            "data_element": "First Name",
            "data_level_name": "Demographics",
            "data_level_report_name": "01-Demographics",
            "data_sub_level_name": "Member",
            "data_sub_level_report_name": "03-Member",
            "checkpoint_name": "Invalid First Name",
            "dqcp_title": "Invalid First Name",
            "dqcp_description": "First name must not contain numerics.",
            "dqcp_pseudo_code": "SELECT * FROM Person WHERE First_Name ~ '[0-9]'",
            "table_name": "Person",
            "column_name": "First_Name",
            "sys_table_name": "Person",
            "sys_column_name": "First_Name",
            "status": "Active",
            "is_approved": "Y",
            "rollout": "Y",
            "start_date": "2025-11-13",
            "end_date": None,
            "last_modified_date": "2026-03-27",
            "resolved_date": None,
            "dqcp_comments": None,
            "dqcp_questions": None,
            "question_status": None,
            "change_history": None,
            "resolution": None,
            "excluded_from_sync": False,
            "field_hash": "hash_bbb",
        },
    ]


@pytest.fixture
def sample_state_store():
    """State store with one known entry and one deleted entry."""
    return {
        "checkpoints": {
            # Matches sample_parsed_rows[1] → should be unchanged
            "dqcp.xlsx::01.03.0002": {
                "work_item_id": 100,
                "work_item_url": "https://dev.azure.com/...",
                "last_synced": "2025-03-01T10:00:00",
                "field_hash": "hash_bbb",
                "dqcp_id": "01.03.0002",
                "dqcp_title": "Invalid First Name",
                "status": "Active",
                "is_approved": "Y",
            },
            # Not in parsed_rows → should appear as deleted
            "dqcp.xlsx::01.03.DELETED": {
                "work_item_id": 99,
                "work_item_url": "https://dev.azure.com/...",
                "last_synced": "2025-01-01T09:00:00",
                "field_hash": "hash_old",
                "dqcp_id": "01.03.DELETED",
                "dqcp_title": "Obsolete Check",
                "status": "Removed",
                "is_approved": "N",
            },
        },
        "last_sync": "2025-03-01T10:00:00",
        "version": "1.0",
    }


@pytest.fixture
def tmp_excel_file(tmp_path, config):
    """
    Creates a minimal DQCP_Master workbook in tmp_path for parser tests.
    Three data rows: two Active, one Removed (excluded from sync).
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "DQCP_Master"

    ws.append(_HEADERS)
    ws.append(_make_row("01.03.0001", status="Active", title="Invalid SSN", sequence=1))
    ws.append(_make_row("01.03.0002", status="WIP",    title="Invalid First Name", sequence=2, is_approved="N", rollout="N"))
    ws.append(_make_row("01.03.0003", status="Removed", title="Obsolete Check",   sequence=3))

    file_path = tmp_path / "test_dqcp.xlsx"
    wb.save(file_path)
    return str(file_path)
