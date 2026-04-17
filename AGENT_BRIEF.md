# DQCP ADO Sync — Agent Brief
> Self-contained context document for Claude or any AI agent resuming work on this project.
> Last updated: 2026-04-17

---

## Project Purpose

A Streamlit application (`dqcp-ado-sync-ollama`) that:
1. Reads DQCP checkpoint data from **DQCP Master.xlsx** (the source of truth)
2. Detects new/changed rows via a local **state store** (JSON)
3. Pushes work items to **Azure DevOps** via REST API
4. Maintains a **ChromaDB knowledge base** for Q&A
5. Answers questions via a local **Ollama LLM** (no cloud API key needed)

**Project:** V8-to-V3locity pension system migration at Linea
**Client:** ERS (Employees Retirement System)
**Repo:** https://github.com/jjoseph73/DQCP_Manager_Ollama
**Local path:** `C:\Users\JobyJoseph\OneDrive - Linea\998-Prototypes\DQCP_Manager\dqcp-ado-sync-ollama`

---

## Tech Stack

| Layer | Choice | Notes |
|---|---|---|
| UI | Streamlit | No JS/React |
| Excel parsing | openpyxl | Read-only, data_only mode |
| ADO integration | requests + REST API 7.1 | No azure-devops SDK (still in beta) |
| Vector store | ChromaDB (PersistentClient) | `.chroma/` dir — must be on Linux FS in WSL2 |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` | Downloads to `~/.cache/huggingface/` on first run |
| LLM | Ollama (local) | Default model: `llama3.1` — configurable in config.yaml |
| Document loading | LangChain community loaders | PDF/DOCX/MD/TXT/SQL/PY |
| State persistence | JSON file (`state_store.json`) | File-locked with `fcntl` on Linux |
| Tests | pytest | 7 tests, all passing |
| Python | 3.11+ (currently running 3.14.0) | |

---

## Source Data: DQCP Master.xlsx

**Location:** `DQCP Master.xlsx` in project root (gitignored — do not commit)

### Sheets

| Sheet | Purpose |
|---|---|
| `DQCP_Master` | **Primary data** — 72 rows, 30 columns |
| `Data_Level` | Lookup: 9 levels (1=Demographics … 9=Other) |
| `Data_Sub_Level` | Lookup: 7 sub-levels (1=Organization … 7=Other) |
| `Lookup Values` | DQCP_Status definitions + Assignees (Vitech/HIERS/Linea) |
| `Change Log` | Version history — not parsed |

### DQCP_Master Key Fields

| Column | Type | Notes |
|---|---|---|
| `DQCP_Id` | string | Natural key — format `01.03.0001` (Level.SubLevel.Seq) |
| `DQCP_Title` | string | ADO work item title (prefixed with DQCP_Id) |
| `DQCP_Description` | string (multiline) | Full rule description |
| `DQCP_Pseudo_Code` | string (multiline) | SQL / pseudo-SQL logic — 75% populated |
| `DQCP_Status` | enum | **Active** (36) · **WIP** (15) · **Info** (12) · **Removed** (9) |
| `Is_Approved` | Y/N | Y=59, N=13 |
| `RollOut` | Y/N | Y=66, N=6 |
| `Data_Level` | int | FK → Data_Level sheet |
| `Data_Sub_Level` | int | FK → Data_Sub_Level sheet |
| `Table_Name` | string | Source V8 table (14 unique values) |
| `Column_Name` | string | Source V8 column |
| `DQCP_Comments` | string | Sparse (10/72) |
| `DQCP_Questions` | string | Open questions (14/72) |
| `DQCP_Question_Status` | enum | Pending/Complete/Info |
| `DQCP_Change_History` | string | Audit trail (47/72) |

### Always-Empty Columns (skip)
`Doc_Ind`, `Assigned_To`, `DQCP_Resolved_By`, `OLD_DQCP_Id`

### Sync Filter
Only rows with `DQCP_Status` in `["Active", "WIP"]` are pushed to ADO.
- Active=36, WIP=15 → **51 rows included**
- Info=12, Removed=9 → **21 rows excluded** (parsed but `excluded_from_sync=True`)

---

## Checkpoint Key Format

```
"{filename}::{DQCP_Id}"
# e.g. "DQCP Master.xlsx::01.03.0001"
```

This key is stored in `state_store.json` and used for delta detection.

---

## Field Hash (change detection)

`generate_field_hash()` in `src/parser.py` hashes these 8 fields:
```python
["status", "is_approved", "rollout", "dqcp_description",
 "dqcp_pseudo_code", "dqcp_comments", "resolution", "end_date"]
```
A hash change triggers a re-push to ADO.

---

## ADO Integration

### Status Mapping (DQCP_Status → ADO State)
| DQCP_Status | ADO State |
|---|---|
| Active | Active |
| WIP | New |
| Info | Active |
| Removed | Resolved |
| Cutover | Active |

### ADO Work Item Title Format
```
[01.03.0001] Invalid SSN/DQCP Format - Member
```

### Custom Fields Required in ADO
These must be created in the **"DQCP Checkpoint"** work item type before any push:

| ADO Field Reference | Display Name | Type |
|---|---|---|
| `Custom.DQCPId` | DQCP ID | Text (single line) |
| `Custom.DataLevel` | Data Level | Text (single line) |
| `Custom.DataSubLevel` | Data Sub Level | Text (single line) |
| `Custom.DataElement` | Data Element | Text (single line) |
| `Custom.TableName` | Table Name | Text (single line) |
| `Custom.ColumnName` | Column Name | Text (single line) |
| `Custom.DQCPStatus` | DQCP Status | Text (single line) |
| `Custom.IsApproved` | Is Approved | Text (single line) |
| `Custom.RollOut` | Roll Out | Text (single line) |
| `Custom.StartDate` | Start Date | Date/Time |
| `Custom.EndDate` | End Date | Date/Time |
| `Custom.CheckpointKey` | Checkpoint Key | Text (single line) |
| `Custom.SourceFile` | Source File | Text (single line) |

---

## File Structure

```
dqcp-ado-sync-ollama/
├── app.py                  # Streamlit app — role-based tab routing
├── config.yaml             # All configuration (edit before first run)
├── .env.example            # → copy to .env, fill in secrets
├── .env                    # gitignored — ADO_PAT + OLLAMA_BASE_URL
├── .gitignore
├── requirements.txt
├── state_store.json        # gitignored — checkpoint sync state
├── AGENT_BRIEF.md          # ← this file
├── DQCP Master.xlsx        # gitignored — source data
├── src/
│   ├── __init__.py
│   ├── parser.py           # Excel → list[dict]; loads lookups; generates hashes
│   ├── delta.py            # New/changed/unchanged/deleted + state store I/O
│   ├── ado_agent.py        # REST API push (requests, not azure-devops SDK)
│   ├── knowledge_feed.py   # LangChain document ingestion → ChromaDB
│   ├── qa_agent.py         # Ollama RAG Q&A
│   ├── vector_store.py     # ChromaDB wrapper (SentenceTransformer embeddings)
│   └── ui_components.py    # Reusable Streamlit components
├── knowledge_base/         # gitignored — drop docs here for ingestion
├── .chroma/                # gitignored — ChromaDB persistent store
└── tests/
    ├── conftest.py         # Fixtures: config, sample_parsed_rows,
    │                       #   sample_state_store, tmp_excel_file
    ├── test_parser.py      # 3 tests — parse, skip empty, hash consistency
    └── test_delta.py       # 4 tests — new, changed, unchanged, deleted
```

---

## config.yaml Reference

```yaml
ado:
  org_url: "https://dev.azure.com/YOUR_ORG"
  project: "YOUR_PROJECT"
  work_item_type: "DQCP Checkpoint"      # must match ADO exactly
  assigned_to: "your.email@company.com"  # all WIs assigned to this address

excel:
  master_sheet: "DQCP_Master"
  id_column: "DQCP_Id"
  title_column: "DQCP_Title"
  description_column: "DQCP_Description"
  pseudo_code_column: "DQCP_Pseudo_Code"
  status_column: "DQCP_Status"
  is_approved_column: "Is_Approved"
  rollout_column: "RollOut"
  data_level_column: "Data_Level"
  data_sub_level_column: "Data_Sub_Level"
  sequence_column: "Sequence_Number"
  data_element_column: "Data_Element"
  table_name_column: "Table_Name"
  column_name_column: "Column_Name"
  sys_table_column: "Sys_Table_Name"
  sys_column_column: "Sys_Column_Name"
  start_date_column: "Start_Date"
  end_date_column: "End_Date"
  last_modified_column: "Last_Modified_Date"
  resolved_date_column: "DQCP_Resolved_Date"
  comments_column: "DQCP_Comments"
  questions_column: "DQCP_Questions"
  question_status_column: "DQCP_Question_Status"
  change_history_column: "DQCP_Change_History"
  resolution_column: "DQCP_Resolution"
  sync_statuses: ["Active", "WIP"]

ollama:
  base_url: "http://localhost:11434"
  model: "llama3.1"          # alternatives: mistral, qwen2.5, deepseek-r1:8b
  num_ctx: 4096
  temperature: 0.1
  stream: false

knowledge:
  chroma_path: ".chroma"
  collection_name: "dqcp_knowledge"
  embedding_model: "all-MiniLM-L6-v2"
  chunk_size: 800
  chunk_overlap: 100
  top_k_results: 5

app:
  default_role: "analyst"
  state_store_path: "state_store.json"
```

---

## .env File (gitignored)

```
ADO_PAT=<Azure DevOps Personal Access Token — Work Items Read/Write scope>
DQCP_ROLE=admin                          # or: analyst
OLLAMA_BASE_URL=http://localhost:11434   # optional — defaults to localhost
```

---

## Roles

| Role | Env value | Tabs visible |
|---|---|---|
| Sync Admin | `DQCP_ROLE=admin` | Sync Push · Knowledge Feed · Q&A Chat · Config & State |
| DQCP Analyst | `DQCP_ROLE=analyst` | Q&A Chat · Status View (read-only) |

---

## State Store Schema

```json
{
  "checkpoints": {
    "DQCP Master.xlsx::01.03.0001": {
      "work_item_id": 1234,
      "work_item_url": "https://dev.azure.com/.../workItems/1234",
      "last_synced": "2026-04-17T10:30:00+00:00",
      "field_hash": "0873caa248f1...",
      "dqcp_id": "01.03.0001",
      "dqcp_title": "Invalid SSN/ITIN Format - Member",
      "status": "Active",
      "is_approved": "Y",
      "rollout": "Y",
      "data_level_report_name": "01-Demographics",
      "data_sub_level_report_name": "03-Member"
    }
  },
  "last_sync": "2026-04-17T10:30:00+00:00",
  "version": "1.0"
}
```

---

## Test Suite

```
tests/test_parser.py   test_parse_single_sheet        PASS
                       test_skip_empty_dqcp_id        PASS
                       test_field_hash_consistency     PASS
tests/test_delta.py    test_new_item                  PASS
                       test_changed_item               PASS
                       test_unchanged_item             PASS
                       test_deleted_item               PASS
                       ─────────────────────────────────────
                       7 passed in 0.12s
```

Run with: `python -m pytest tests/ -v`

---

## What Remains (Priority Order)

### ✅ Done
- Full project scaffold
- Parser aligned to DQCP_Master schema (72 rows, 30 cols, lookup enrichment)
- Delta engine + state store I/O
- ADO agent (REST API 7.1, no SDK)
- ChromaDB vector store + SentenceTransformer embeddings
- LangChain document ingestion (PDF/DOCX/MD/SQL/PY)
- Ollama Q&A agent (RAG)
- Streamlit UI (role-based tabs, delta preview, push progress, KB browser, chat)
- All tests passing (7/7)
- Pushed to GitHub: https://github.com/jjoseph73/DQCP_Manager_Ollama

### 🟡 Priority 2 — Environment Setup (before first run)
1. Create `.venv` → `pip install -r requirements.txt`
2. Create `.env` from `.env.example` — fill in `ADO_PAT`
3. Install Ollama + pull model: `ollama pull llama3.1`
4. **Create ADO work item type** `DQCP Checkpoint` with all 13 custom fields (see table above)

### 🟢 Priority 3 — First Run & Validation
1. `streamlit run app.py`
2. Upload `DQCP Master.xlsx` → verify 51 rows preview correctly
3. Test push of 1–2 rows to ADO to confirm field mapping
4. Ingest DQCP spec documents into knowledge base
5. Test Ollama Q&A round-trip

### 🔵 Future Enhancements (not started)
- Scheduled/automated sync (no manual file upload)
- ADO → Excel writeback (sync resolved status back)
- Multi-workbook support (other data levels beyond L1)
- Export delta report to Word/PDF for ERS review meetings
- Dashboard charts: checkpoint status by data level, open questions trend

---

## Key Decisions & Rationale

| Decision | Reason |
|---|---|
| No `azure-devops` SDK | Package never shipped stable 7.x — REST API 7.1 is stable |
| Ollama instead of Claude/Anthropic | No cloud API key needed; runs fully local |
| `DQCP_Id` as natural key | More stable than a free-text title; survives renames |
| `sync_statuses` filter in config | Info and Removed rows shouldn't create ADO work items |
| ChromaDB on Linux FS | WSL2 `/mnt/c/` path causes severe ChromaDB performance degradation |
| `fcntl` file locking (Linux only) | Prevents state store corruption on concurrent Streamlit reruns; falls back to plain I/O on Windows |

---

## Common Commands

```bash
# Run tests
python -m pytest tests/ -v

# Start app
streamlit run app.py

# Check Ollama is running
ollama list

# Pull a model
ollama pull llama3.1

# Smoke-test parser against real Excel
python -c "
import yaml
from src.parser import parse_excel_files
config = yaml.safe_load(open('config.yaml'))
rows = parse_excel_files(['DQCP Master.xlsx'], config)
print(f'{len(rows)} rows, {sum(1 for r in rows if not r[\"excluded_from_sync\"])} included')
"
```
