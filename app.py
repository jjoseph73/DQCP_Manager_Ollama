"""
DQCP ADO Sync (Ollama edition) — main Streamlit application.

Identical to the Anthropic edition except the Q&A backend uses a locally
running Ollama server instead of the Anthropic API.  No API key is required.
"""
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml
from dotenv import load_dotenv

load_dotenv()

# ── Page config ────────────────────────────────────────────────────────────────
st.set_page_config(page_title="DQCP ADO Sync · Ollama", layout="wide")

# ── Load config ────────────────────────────────────────────────────────────────
CONFIG_PATH = Path("config.yaml")


@st.cache_resource(show_spinner=False)
def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config()

# ── Role detection ─────────────────────────────────────────────────────────────
env_role = os.environ.get("DQCP_ROLE", "").lower()
sidebar_role = st.sidebar.selectbox(
    "Role",
    ["Sync Admin", "DQCP Analyst"],
    index=0 if env_role in ("admin", "sync admin") else 1,
)
role = "admin" if sidebar_role == "Sync Admin" else "analyst"

# ── Sidebar: Ollama status ─────────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("### Ollama")

from src.qa_agent import list_local_models

_available_models = list_local_models(config)
_configured_model = config.get("ollama", {}).get("model", "llama3.1")
_ollama_ok = bool(_available_models)

if _ollama_ok:
    if _configured_model in _available_models:
        st.sidebar.success(f"✅ {_configured_model}")
    else:
        st.sidebar.warning(
            f"Model **{_configured_model}** not found on server.\n\n"
            f"Available: {', '.join(_available_models)}"
        )
else:
    st.sidebar.error("Ollama server unreachable")

# ── Sidebar: knowledge stats ───────────────────────────────────────────────────
st.sidebar.markdown("---")
st.sidebar.markdown("### Knowledge Base")


@st.cache_resource(show_spinner=False)
def get_vector_store(_config):
    from src.vector_store import VectorStore
    return VectorStore(_config)


vector_store = get_vector_store(config)

try:
    kb_stats = vector_store.get_stats()
    st.sidebar.metric("Chunks", kb_stats["total_chunks"])
    st.sidebar.metric("Sources", kb_stats["unique_sources"])
except Exception:
    st.sidebar.info("Knowledge base unavailable.")

# ── Sidebar: ADO config override (admin only) ─────────────────────────────────
if role == "admin":
    with st.sidebar.expander("ADO Config Override"):
        st.text_input("Org URL", value=config["ado"]["org_url"], key="sidebar_org_url")
        st.text_input("Project", value=config["ado"]["project"], key="sidebar_project")
        st.text_input(
            "Work Item Type",
            value=config["ado"]["work_item_type"],
            key="sidebar_wi_type",
        )

# ── Credentials ────────────────────────────────────────────────────────────────
ado_pat = os.environ.get("ADO_PAT", "")

# ── Tab routing ────────────────────────────────────────────────────────────────
if role == "admin":
    tabs = st.tabs(["🔄 Sync Push", "📚 Knowledge Feed", "💬 Q&A Chat", "⚙️ Config & State"])
    tab_sync, tab_knowledge, tab_chat, tab_config = tabs
else:
    tabs = st.tabs(["💬 Q&A Chat", "📋 Status View"])
    tab_chat, tab_status = tabs

# ══════════════════════════════════════════════════════════════════════════════
# SYNC PUSH TAB (admin only)
# ══════════════════════════════════════════════════════════════════════════════
if role == "admin":
    with tab_sync:
        st.header("Sync Push")

        uploaded = st.file_uploader(
            "Upload DQCP Excel files",
            type=["xlsx", "xls"],
            accept_multiple_files=True,
        )
        preview_mode = st.toggle("Preview before push", value=True)

        if st.button("📊 Load & Analyse", disabled=not uploaded):
            from src.delta import load_state_store
            from src.parser import parse_excel_files

            tmp_paths = []
            for uf in uploaded:
                tmp_p = Path(f"/tmp/dqcp_upload_{uf.name}")
                tmp_p.write_bytes(uf.read())
                tmp_paths.append(str(tmp_p))

            with st.spinner("Parsing Excel files…"):
                try:
                    parsed = parse_excel_files(tmp_paths, config)
                except Exception as e:
                    st.error(f"Parse error: {e}")
                    st.stop()

            state_store = load_state_store(config["app"]["state_store_path"])

            from src.delta import compute_delta
            delta = compute_delta(parsed, state_store)

            st.session_state["_delta"] = delta
            st.session_state["_parsed"] = parsed
            st.session_state["_state_store"] = state_store

            st.success(
                f"Parsed {len(parsed)} rows from {len(uploaded)} file(s). "
                f"{len(delta['new'])} new · {len(delta['changed'])} changed · "
                f"{len(delta['unchanged'])} unchanged · {len(delta['deleted'])} deleted"
            )

        if "_delta" in st.session_state:
            delta = st.session_state["_delta"]

            if preview_mode:
                from src.ui_components import render_delta_preview_table
                confirmed = render_delta_preview_table(delta)
            else:
                confirmed = True

            if confirmed is True:
                from src.ado_agent import push_to_ado
                from src.delta import save_state_store, update_state_store
                from src.ui_components import render_push_progress

                if not ado_pat:
                    st.error("ADO_PAT not set in .env — cannot push.")
                else:
                    push_items = []
                    for row in delta["new"]:
                        push_items.append({**row, "is_new": True})
                    for row in delta["changed"]:
                        stored = st.session_state["_state_store"]["checkpoints"].get(
                            row["checkpoint_key"], {}
                        )
                        push_items.append({
                            **row,
                            "is_new": False,
                            "work_item_id": stored.get("work_item_id"),
                        })

                    if not push_items:
                        st.info("Nothing to push.")
                    else:
                        with st.spinner(f"Pushing {len(push_items)} items to ADO…"):
                            try:
                                results = push_to_ado(push_items, config, ado_pat)
                            except Exception as e:
                                st.error(f"ADO push failed: {e}")
                                results = []

                        render_push_progress(results)

                        successful = [r for r in results if r.get("success")]
                        if successful:
                            store = st.session_state["_state_store"]
                            store = update_state_store(store, successful)
                            save_state_store(config["app"]["state_store_path"], store)
                            st.success(f"State store updated with {len(successful)} items.")

                        del st.session_state["_delta"]

            elif confirmed is False:
                st.warning("Push cancelled.")
                del st.session_state["_delta"]

# ══════════════════════════════════════════════════════════════════════════════
# KNOWLEDGE FEED TAB (admin only)
# ══════════════════════════════════════════════════════════════════════════════
if role == "admin":
    with tab_knowledge:
        st.header("Knowledge Feed")

        kb_uploaded = st.file_uploader(
            "Upload knowledge documents",
            type=["pdf", "docx", "md", "txt", "sql", "py"],
            accept_multiple_files=True,
        )
        project_tag = st.text_input("Project tag (optional)", placeholder="e.g. V8-Migration-Specs")

        if st.button("📥 Ingest", disabled=not kb_uploaded):
            from src.knowledge_feed import ingest_documents

            with st.spinner("Ingesting documents…"):
                try:
                    summary = ingest_documents(kb_uploaded, config, vector_store)
                    for fname, info in summary.items():
                        if info["status"] == "success":
                            st.success(
                                f"✅ {fname} — {info['chunks_added']} chunks added"
                                + (f" ({info['chunks_replaced']} replaced)" if info["chunks_replaced"] else "")
                            )
                        else:
                            st.error(f"❌ {fname} — {info['status']}")
                    st.cache_resource.clear()
                except Exception as e:
                    st.error(f"Ingestion error: {e}")

        st.markdown("---")
        st.subheader("Knowledge Base Contents")
        from src.ui_components import render_knowledge_base_browser
        render_knowledge_base_browser(vector_store)

# ══════════════════════════════════════════════════════════════════════════════
# Q&A CHAT TAB (all users)
# ══════════════════════════════════════════════════════════════════════════════
with tab_chat:
    st.header("DQCP Q&A Assistant")
    st.caption(
        f"Powered by **{_configured_model}** via Ollama"
        + (f" · `{config.get('ollama', {}).get('base_url', 'localhost:11434')}`")
    )

    with st.expander("💡 What can I ask?"):
        st.markdown("""
**Examples:**
- What are the DQCP rules for member date-of-birth validation?
- Show me the SQL logic for the contribution reconciliation checkpoint.
- Which checkpoints are currently failing and who owns them?
- What does the V8 migration spec say about transfer values?
- Explain checkpoint CP-042 and its acceptance criteria.
        """)

    if not _ollama_ok:
        st.error(
            "Cannot reach the Ollama server. "
            "Make sure Ollama is running (`ollama serve`) and the base URL in "
            "`config.yaml → ollama.base_url` is correct."
        )
    elif _configured_model not in _available_models:
        st.warning(
            f"Model **{_configured_model}** is not pulled yet.  "
            f"Run: `ollama pull {_configured_model}`"
        )
    else:
        from src.qa_agent import answer_question
        from src.ui_components import render_chat_ui
        # api_key=None — Ollama doesn't need one; qa_agent.py ignores it
        render_chat_ui(answer_question, vector_store, config, api_key=None)

# ══════════════════════════════════════════════════════════════════════════════
# STATUS VIEW TAB (analyst)
# ══════════════════════════════════════════════════════════════════════════════
if role == "analyst":
    with tab_status:
        st.header("Checkpoint Status View")

        store_path = Path(config["app"]["state_store_path"])
        if not store_path.exists():
            st.info("No state store found — no syncs have been performed yet.")
        else:
            from src.delta import load_state_store
            store = load_state_store(str(store_path))

            last_sync = store.get("last_sync")
            st.caption(f"Last sync: {last_sync or 'Never'}")

            checkpoints = store.get("checkpoints", {})
            if not checkpoints:
                st.info("No checkpoints synced yet.")
            else:
                rows = []
                for key, val in checkpoints.items():
                    rows.append({
                        "DQCP ID": val.get("dqcp_id", ""),
                        "Title": val.get("dqcp_title", ""),
                        "Data Level": val.get("data_level_report_name", ""),
                        "Sub Level": val.get("data_sub_level_report_name", ""),
                        "Status": val.get("status", ""),
                        "Approved": val.get("is_approved", ""),
                        "Roll Out": val.get("rollout", ""),
                        "Work Item ID": val.get("work_item_id"),
                        "ADO Link": val.get("work_item_url", ""),
                        "Last Synced": val.get("last_synced", "")[:19] if val.get("last_synced") else "",
                    })

                df = pd.DataFrame(rows)

                col_status, col_level, col_approved = st.columns(3)
                with col_status:
                    status_opts = ["All"] + sorted(df["Status"].dropna().unique().tolist())
                    status_filter = st.selectbox("Filter by DQCP Status", status_opts)
                with col_level:
                    level_opts = ["All"] + sorted(df["Data Level"].dropna().unique().tolist())
                    level_filter = st.selectbox("Filter by Data Level", level_opts)
                with col_approved:
                    approved_opts = ["All", "Y", "N"]
                    approved_filter = st.selectbox("Filter by Approved", approved_opts)

                if status_filter != "All":
                    df = df[df["Status"] == status_filter]
                if level_filter != "All":
                    df = df[df["Data Level"] == level_filter]
                if approved_filter != "All":
                    df = df[df["Approved"] == approved_filter]

                st.dataframe(df, use_container_width=True, hide_index=True)

# ══════════════════════════════════════════════════════════════════════════════
# CONFIG & STATE TAB (admin only)
# ══════════════════════════════════════════════════════════════════════════════
if role == "admin":
    with tab_config:
        st.header("Config & State")

        st.subheader("ADO Settings")
        new_org_url = st.text_input("Org URL", value=config["ado"]["org_url"])
        new_project = st.text_input("Project", value=config["ado"]["project"])
        new_wi_type = st.text_input("Work Item Type", value=config["ado"]["work_item_type"])
        new_assigned_to = st.text_input("Assigned To", value=config["ado"]["assigned_to"])

        st.subheader("Ollama Settings")
        # Live model list from server (falls back gracefully if offline)
        model_options = _available_models or [_configured_model]
        current_idx = model_options.index(_configured_model) if _configured_model in model_options else 0
        new_model = st.selectbox("Model", model_options, index=current_idx)
        new_base_url = st.text_input(
            "Ollama base URL",
            value=config.get("ollama", {}).get("base_url", "http://localhost:11434"),
        )
        new_num_ctx = st.number_input(
            "Context window (num_ctx)",
            value=config.get("ollama", {}).get("num_ctx", 4096),
            step=512,
        )
        new_temperature = st.slider(
            "Temperature",
            min_value=0.0,
            max_value=1.0,
            value=float(config.get("ollama", {}).get("temperature", 0.1)),
            step=0.05,
        )

        st.subheader("Knowledge Settings")
        new_chunk_size = st.number_input("Chunk Size", value=config["knowledge"]["chunk_size"], step=50)
        new_chunk_overlap = st.number_input("Chunk Overlap", value=config["knowledge"]["chunk_overlap"], step=10)
        new_top_k = st.number_input("Top-K Results", value=config["knowledge"]["top_k_results"], step=1)

        if st.button("💾 Save Config"):
            config["ado"]["org_url"] = new_org_url
            config["ado"]["project"] = new_project
            config["ado"]["work_item_type"] = new_wi_type
            config["ado"]["assigned_to"] = new_assigned_to
            config.setdefault("ollama", {})
            config["ollama"]["model"] = new_model
            config["ollama"]["base_url"] = new_base_url
            config["ollama"]["num_ctx"] = int(new_num_ctx)
            config["ollama"]["temperature"] = float(new_temperature)
            config["knowledge"]["chunk_size"] = int(new_chunk_size)
            config["knowledge"]["chunk_overlap"] = int(new_chunk_overlap)
            config["knowledge"]["top_k_results"] = int(new_top_k)
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            st.success("Config saved. Reloading…")
            st.cache_resource.clear()
            st.rerun()

        st.markdown("---")
        st.subheader("State Store")

        store_path = Path(config["app"]["state_store_path"])
        if store_path.exists():
            with open(store_path, "r", encoding="utf-8") as f:
                raw_store = f.read()

            with st.expander("View raw state store"):
                st.code(raw_store, language="json")

            st.warning("Clearing the state store will cause all checkpoints to be treated as new on next sync.")
            confirm_clear = st.checkbox("I understand — clear the state store")
            if st.button("🗑️ Clear State Store", disabled=not confirm_clear):
                empty = {"checkpoints": {}, "last_sync": None, "version": "1.0"}
                with open(store_path, "w", encoding="utf-8") as f:
                    json.dump(empty, f, indent=2)
                st.success("State store cleared.")
        else:
            st.info("State store file not found.")
