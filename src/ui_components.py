"""
Reusable Streamlit UI components for the DQCP ADO Sync app.
"""
from typing import Callable

import pandas as pd
import streamlit as st

from src.vector_store import VectorStore


def render_delta_preview_table(delta: dict) -> bool:
    """
    Render a colour-coded preview of new/changed/unchanged/deleted rows.

    Returns True if the user clicks "Confirm & Push", False if "Cancel".
    """
    n_new = len(delta["new"])
    n_changed = len(delta["changed"])
    n_unchanged = len(delta["unchanged"])
    n_deleted = len(delta["deleted"])

    st.markdown(
        f"**{n_new} new** &nbsp;·&nbsp; **{n_changed} changed** &nbsp;·&nbsp; "
        f"**{n_unchanged} unchanged** &nbsp;·&nbsp; **{n_deleted} deleted**"
    )

    _DISPLAY_COLS = ["checkpoint_key", "status", "severity", "owner", "due_date", "comments"]

    # NEW rows
    if delta["new"]:
        st.markdown("#### 🟢 New")
        df_new = pd.DataFrame(delta["new"])
        cols = [c for c in _DISPLAY_COLS if c in df_new.columns]
        styled = df_new[cols].style.apply(
            lambda _: ["background-color: #d4edda"] * len(cols), axis=1
        )
        st.dataframe(styled, use_container_width=True)

    # CHANGED rows
    if delta["changed"]:
        st.markdown("#### 🟡 Changed")
        rows = []
        for item in delta["changed"]:
            old = item.get("_old", {})
            row = {c: item.get(c) for c in _DISPLAY_COLS if c in item}
            for field in ("status", "severity", "comments", "due_date"):
                old_val = old.get(field)
                new_val = item.get(field)
                if old_val != new_val:
                    row[f"{field} (was)"] = old_val
            rows.append(row)
        df_changed = pd.DataFrame(rows)
        styled = df_changed.style.apply(
            lambda _: ["background-color: #fff3cd"] * len(df_changed.columns), axis=1
        )
        st.dataframe(styled, use_container_width=True)

    # DELETED rows
    if delta["deleted"]:
        st.markdown("#### 🔴 Deleted (in state store, not in Excel)")
        df_del = pd.DataFrame(delta["deleted"])
        cols = [c for c in ["checkpoint_key", "status", "severity", "work_item_id"] if c in df_del.columns]
        styled = df_del[cols].style.apply(
            lambda _: ["background-color: #f8d7da"] * len(cols), axis=1
        )
        st.dataframe(styled, use_container_width=True)

    # UNCHANGED rows (collapsed)
    if delta["unchanged"]:
        with st.expander(f"⚪ Unchanged ({n_unchanged} rows)"):
            df_unch = pd.DataFrame(delta["unchanged"])
            cols = [c for c in _DISPLAY_COLS if c in df_unch.columns]
            st.dataframe(df_unch[cols], use_container_width=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        confirm = st.button("✅ Confirm & Push", type="primary", use_container_width=True)
    with col2:
        cancel = st.button("❌ Cancel", use_container_width=True)

    if cancel:
        return False
    if confirm:
        return True
    return None  # Neither clicked yet


def render_push_progress(items: list[dict]) -> None:
    """Show live push progress with a progress bar and per-item status."""
    total = len(items)
    progress_bar = st.progress(0)
    status_container = st.empty()

    for i, item in enumerate(items, start=1):
        progress_bar.progress(i / total)
        key = item.get("checkpoint_key", f"item-{i}")
        if item.get("success"):
            status_container.success(f"✅ [{i}/{total}] {key} → WI#{item.get('work_item_id')}")
        else:
            status_container.error(f"❌ [{i}/{total}] {key} — {item.get('error')}")

    progress_bar.progress(1.0)
    success_count = sum(1 for r in items if r.get("success"))
    fail_count = total - success_count
    st.info(f"Push complete: {success_count} succeeded, {fail_count} failed.")


def render_knowledge_base_browser(vector_store: VectorStore) -> None:
    """Render a table of ingested knowledge base sources with remove buttons."""
    stats = vector_store.get_stats()
    st.markdown(
        f"**Total chunks:** {stats['total_chunks']} &nbsp;|&nbsp; "
        f"**Unique sources:** {stats['unique_sources']} &nbsp;|&nbsp; "
        f"**Doc types:** {', '.join(stats['doc_types']) or 'none'}"
    )

    sources = vector_store.list_sources()
    if not sources:
        st.info("No documents ingested yet.")
        return

    df = pd.DataFrame(sources)
    for _, row in df.iterrows():
        col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 3, 1])
        col1.write(row.get("source_file", ""))
        col2.write(row.get("doc_type", ""))
        col3.write(str(row.get("chunk_count", 0)))
        col4.write(str(row.get("ingested_at", ""))[:19])
        if col5.button("🗑️", key=f"remove_{row['source_file']}"):
            vector_store.delete_by_source(row["source_file"])
            st.success(f"Removed: {row['source_file']}")
            st.rerun()


def render_chat_ui(
    qa_agent_fn: Callable,
    vector_store: VectorStore,
    config: dict,
    api_key: str,
) -> None:
    """Render the Q&A chat interface with history."""
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    col_filter, col_clear = st.columns([3, 1])
    with col_filter:
        doc_type_filter = st.selectbox(
            "Filter context by doc type",
            options=["All", "spec", "sql", "code", "doc"],
            key="chat_doc_type_filter",
        )
    with col_clear:
        st.write("")
        if st.button("🗑️ Clear chat", use_container_width=True):
            st.session_state["chat_history"] = []
            st.rerun()

    # Render history
    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Chat input
    if prompt := st.chat_input("Ask about DQCP rules, checkpoints, or migration logic…"):
        st.session_state["chat_history"].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                try:
                    filter_val = None if doc_type_filter == "All" else doc_type_filter
                    # Build history without the last user message (it's embedded in the prompt)
                    history = st.session_state["chat_history"][:-1]
                    answer = qa_agent_fn(
                        question=prompt,
                        vector_store=vector_store,
                        config=config,
                        api_key=api_key,
                        chat_history=history,
                        doc_type_filter=filter_val,
                    )
                except Exception as exc:
                    answer = f"⚠️ Error calling the Q&A agent: {exc}"
                st.markdown(answer)

        st.session_state["chat_history"].append({"role": "assistant", "content": answer})
