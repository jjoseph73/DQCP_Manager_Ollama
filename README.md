# DQCP ADO Sync

Streamlit application that syncs **DQCP (Data Quality Control Process)** checkpoints from the `DQCP Master.xlsx` workbook into Azure DevOps work items, with a local ChromaDB knowledge base and an Ollama-powered Q&A assistant.

Built for the **V8-to-V3locity pension system migration** at Linea / ERS.

---

## Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running (`ollama serve`)
- Azure DevOps PAT with **Work Items: Read & Write** scope
- `DQCP Master.xlsx` workbook (not committed — place in project root)

> **WSL2 note:** If running on Windows, ChromaDB performs significantly better when the project lives on the Linux filesystem (e.g. `~/projects/`) rather than under `/mnt/c/`. The app runs fine on Windows natively for everything except ChromaDB-heavy workloads.

---

## Setup

```bash
git clone https://github.com/jjoseph73/DQCP_Manager_Ollama.git
cd DQCP_Manager_Ollama

# Create virtual environment
python -m venv .venv

# Activate — Windows CMD
.venv\Scripts\activate
# Activate — Windows PowerShell
.venv\Scripts\Activate.ps1
# Activate — WSL2 / bash
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure secrets
cp .env.example .env
# Edit .env — fill in ADO_PAT (OLLAMA_BASE_URL is optional, defaults to localhost)

# Configure ADO and Excel settings
# Edit config.yaml — set ado.org_url, ado.project, ado.work_item_type, ado.assigned_to
```

> **First run only:** `sentence-transformers` downloads `all-MiniLM-L6-v2` (~80 MB) to `~/.cache/huggingface/`.

---

## Pull an Ollama model before first use

```bash
# Recommended (default in config.yaml)
ollama pull llama3.1

# Alternatives
ollama pull mistral          # fast, good for structured Q&A
ollama pull qwen2.5          # strong on technical/SQL content
ollama pull deepseek-r1:8b   # chain-of-thought reasoning
ollama pull phi3             # lightweight — good for constrained hardware
```

Set the active model in `config.yaml → ollama.model`.

---

## First Run

```bash
# Terminal 1 — ensure Ollama is running
ollama serve

# Terminal 2 — start the app
streamlit run app.py
```

Open `http://localhost:8501`.

---

## DQCP Master.xlsx — Workbook Format

The app reads from the **`DQCP_Master`** sheet only. All other sheets are used as lookups.

### DQCP_Master columns

| Column | Description |
|---|---|
| `DQCP_Id` | **Natural key** — format `01.03.0001` (DataLevel.SubLevel.Sequence) |
| `Data_Level` | Integer FK → `Data_Level` sheet (1=Demographics, 2=Employment, 3=Contributions…) |
| `Data_Sub_Level` | Integer FK → `Data_Sub_Level` sheet (1=Org, 2=Employer, 3=Member, 4=Non-Member…) |
| `Sequence_Number` | Order within the sub-level group |
| `Data_Element` | The field being validated (e.g. `SSN`, `Birth Date`) |
| `DQCP_Title` | Short title — becomes the ADO work item title |
| `DQCP_Description` | Full rule description (multiline) |
| `DQCP_Pseudo_Code` | SQL / pseudo-SQL validation logic (multiline) |
| `Table_Name` | Source V8 table |
| `Column_Name` | Source V8 column |
| `Sys_Table_Name` | Target system table |
| `Sys_Column_Name` | Target system column |
| `Start_Date` | Date the checkpoint was introduced |
| `End_Date` | Date the checkpoint was retired (if applicable) |
| `Last_Modified_Date` | Last edit date |
| `DQCP_Resolved_Date` | Date the issue was resolved |
| `DQCP_Comments` | Developer/analyst notes |
| `DQCP_Questions` | Open questions (sparse) |
| `DQCP_Question_Status` | `Pending` / `Complete` / `Info` |
| `Is_Approved` | `Y` / `N` |
| `DQCP_Status` | `Active` / `WIP` / `Info` / `Removed` |
| `RollOut` | `Y` / `N` — included in migration rollout |
| `DQCP_Resolution` | Resolution notes (if removed/resolved) |
| `DQCP_Change_History` | Timestamped audit log |

### Sync filter

Only rows where `DQCP_Status` is `Active` or `WIP` are pushed to ADO.
`Info` and `Removed` rows are parsed but excluded (`excluded_from_sync = True`).

Configure the filter in `config.yaml → excel.sync_statuses`.

### Lookup sheets

| Sheet | Contents |
|---|---|
| `Data_Level` | 9 levels with names and descriptions |
| `Data_Sub_Level` | 7 sub-levels with names |
| `Lookup Values` | Status definitions, assignee options |

---

## ADO Work Item Type Setup

### 1 — Create the work item type

In your Azure DevOps project: **Project Settings → Process → [your process] → Work Item Types → New Work Item Type**

Name it exactly: **`DQCP Checkpoint`** (must match `config.yaml → ado.work_item_type`)

### 2 — Add custom fields

Add these 13 fields to the `DQCP Checkpoint` work item type:

| Reference Name | Display Name | Type |
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

### 3 — ADO status mapping

| `DQCP_Status` | ADO work item state |
|---|---|
| Active | Active |
| WIP | New |
| Info | Active |
| Removed | Resolved |
| Cutover | Active |

### 4 — Work item title format

```
[01.03.0001] Invalid SSN/ITIN Format - Member
```

---

## Configuration Reference

### `config.yaml`

```yaml
ado:
  org_url: "https://dev.azure.com/YOUR_ORG"
  project: "YOUR_PROJECT"
  work_item_type: "DQCP Checkpoint"      # must match ADO exactly
  assigned_to: "your.email@company.com"  # all work items assigned here

excel:
  master_sheet: "DQCP_Master"
  sync_statuses: ["Active", "WIP"]       # rows outside this are skipped
  # ... (column name mappings — defaults match the workbook; only change if columns are renamed)

ollama:
  base_url: "http://localhost:11434"
  model: "llama3.1"
  num_ctx: 4096
  temperature: 0.1

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

### `.env`

```
ADO_PAT=your_azure_devops_personal_access_token
DQCP_ROLE=admin                          # admin | analyst (optional — can set in UI)
OLLAMA_BASE_URL=http://localhost:11434   # optional — defaults to localhost
```

---

## Roles

| Role | `DQCP_ROLE` value | Tabs |
|---|---|---|
| **Sync Admin** | `admin` | Sync Push · Knowledge Feed · Q&A Chat · Config & State |
| **DQCP Analyst** | `analyst` | Q&A Chat · Status View (read-only) |

Set via the sidebar dropdown or the `DQCP_ROLE` environment variable in `.env`.

---

## Knowledge Base

The Q&A assistant is grounded in documents you ingest via the **Knowledge Feed** tab.

### Supported file types

| Extension | Treated as |
|---|---|
| `.pdf` | doc |
| `.docx` | doc |
| `.md`, `.txt` | doc |
| `.sql` | sql |
| `.py` | code |

Re-uploading a file with the same name automatically replaces its existing chunks — no duplicates.

---

## Running Tests

```bash
python -m pytest tests/ -v
```

Expected output: **7 passed**.

---

## Project Structure

```
DQCP_Manager_Ollama/
├── app.py                  # Streamlit app — role-based tab routing
├── config.yaml             # All configuration (edit before first run)
├── .env.example            # Template — copy to .env and fill in secrets
├── .env                    # gitignored — ADO_PAT + OLLAMA_BASE_URL
├── .gitignore
├── requirements.txt
├── state_store.json        # gitignored — local checkpoint sync state
├── DQCP Master.xlsx        # gitignored — source workbook (place here manually)
├── AGENT_BRIEF.md          # Self-contained context for AI agents resuming work
├── src/
│   ├── __init__.py
│   ├── parser.py           # Reads DQCP_Master; enriches from lookup sheets; hashes rows
│   ├── delta.py            # Detects new/changed/unchanged/deleted; state store I/O
│   ├── ado_agent.py        # Azure DevOps REST API 7.1 push (no SDK)
│   ├── knowledge_feed.py   # LangChain document ingestion → ChromaDB
│   ├── qa_agent.py         # Ollama RAG Q&A (retrieves chunks, calls model)
│   ├── vector_store.py     # ChromaDB wrapper + SentenceTransformer embeddings
│   └── ui_components.py    # Reusable Streamlit components
├── knowledge_base/         # gitignored — drop files here for bulk ingestion
├── .chroma/                # gitignored — ChromaDB persistent store
└── tests/
    ├── conftest.py         # Fixtures: config, parsed rows, state store, tmp workbook
    ├── test_parser.py      # Parse, skip-empty, hash consistency
    └── test_delta.py       # New, changed, unchanged, deleted detection
```

---

## Common Commands

```bash
# Run tests
python -m pytest tests/ -v

# Start app
streamlit run app.py

# Smoke-test parser against the real workbook
python -c "
import yaml
from src.parser import parse_excel_files
config = yaml.safe_load(open('config.yaml'))
rows = parse_excel_files(['DQCP Master.xlsx'], config)
included = [r for r in rows if not r['excluded_from_sync']]
print(f'{len(rows)} rows parsed, {len(included)} included in sync')
"

# Check which Ollama models are available
ollama list
```
