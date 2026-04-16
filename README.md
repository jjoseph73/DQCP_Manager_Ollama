# DQCP ADO Sync — Ollama Edition

Same application as `dqcp-ado-sync`, but the Q&A assistant runs entirely on a **local Ollama server** — no Anthropic API key or internet connection required for inference.

---

## Prerequisites

- Python 3.11+
- WSL2 (Ubuntu recommended)
- [Ollama](https://ollama.com) installed and running (`ollama serve`)
- At least one model pulled — see recommended models below
- Azure DevOps PAT with **Work Items: Read & Write** scope

---

## Setup

```bash
git clone <your-repo-url>
cd dqcp-ado-sync-ollama

python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — only ADO_PAT is required (no ANTHROPIC_API_KEY needed)

# Edit config.yaml — set ado section and choose your ollama.model
```

---

## Ollama: pull a model before first use

```bash
# Default (recommended general-purpose)
ollama pull llama3.1

# Alternatives
ollama pull mistral          # fast, good for structured Q&A
ollama pull qwen2.5          # strong on technical / SQL content
ollama pull deepseek-r1:8b   # chain-of-thought reasoning
ollama pull phi3              # lightweight — good for constrained hardware
```

Set the model name in `config.yaml → ollama.model` (or change it live in the Config & State tab).

---

## First Run

```bash
# In one terminal — make sure Ollama is already running:
ollama serve

# In another terminal:
streamlit run app.py
```

Open `http://localhost:8501`.

---

## Configuration: `config.yaml → ollama`

| Key | Default | Description |
|---|---|---|
| `base_url` | `http://localhost:11434` | Ollama server address (override with `OLLAMA_BASE_URL` env var) |
| `model` | `llama3.1` | Model tag — must be pulled first |
| `num_ctx` | `4096` | Context window size passed to the model |
| `temperature` | `0.1` | Low = more precise/factual, high = more creative |

All settings can also be changed live in the **Config & State** tab without restarting.

---

## Differences from the Anthropic edition

| | Anthropic edition | Ollama edition |
|---|---|---|
| Inference | `claude-sonnet-4-20250514` via API | Local model via `ollama` Python SDK |
| API key required | `ANTHROPIC_API_KEY` | None |
| Model config | Hardcoded in `qa_agent.py` | `config.yaml → ollama.model` |
| Model selector | — | Live dropdown from server's pulled models |
| Server status | — | Sidebar shows ✅/⚠️/❌ for server + model |
| `requirements.txt` | `anthropic>=0.28.0` | `ollama>=0.3.0` |

Everything else (Excel parsing, delta engine, ADO push, ChromaDB, embeddings) is identical.

---

## Excel Workbook Format

See the main `dqcp-ado-sync` README for the full column specification.

---

## ADO Work Item Type Setup

See the main `dqcp-ado-sync` README for the custom field setup instructions.

---

## Project Structure

```
dqcp-ado-sync-ollama/
├── app.py                  # Streamlit app (Ollama-aware)
├── config.yaml             # Includes ollama: section
├── .env.example            # Only ADO_PAT + optional OLLAMA_BASE_URL
├── requirements.txt        # ollama>=0.3.0 replaces anthropic
├── state_store.json
├── src/
│   ├── parser.py           # unchanged
│   ├── delta.py            # unchanged
│   ├── ado_agent.py        # unchanged
│   ├── knowledge_feed.py   # unchanged
│   ├── vector_store.py     # unchanged
│   ├── qa_agent.py         # ← Ollama client instead of Anthropic SDK
│   └── ui_components.py    # unchanged
└── tests/                  # identical to main edition
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Roles

Same as the main edition — `Sync Admin` or `DQCP Analyst`, set via sidebar or `DQCP_ROLE` env var.
