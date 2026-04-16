"""
Ollama-powered Q&A agent for DQCP knowledge base.

Replaces the Anthropic SDK with the local Ollama inference engine.
Model and server are configured in config.yaml → ollama section.
"""
import os

import ollama

from src.vector_store import VectorStore

SYSTEM_PROMPT = """You are a DQCP (Data Quality Control Process) assistant for a V8-to-V3locity pension system migration project at Linea.
You have access to retrieved context from the project's knowledge base — specs, SQL scripts, documentation, and code.
Answer questions about DQCP rules, checkpoint definitions, data quality criteria, migration logic, and process status.
Be precise and technical. When referencing a rule or spec, cite the source document.
If the retrieved context does not contain enough information to answer confidently, say so clearly rather than guessing.
Do not make up checkpoint names, rule IDs, or SQL logic that is not in the provided context."""


def _build_ollama_client(config: dict) -> ollama.Client:
    """
    Return an Ollama client pointed at the configured server.

    Priority order for base_url:
      1. OLLAMA_BASE_URL environment variable
      2. config.yaml → ollama.base_url
      3. Default: http://localhost:11434
    """
    base_url = (
        os.environ.get("OLLAMA_BASE_URL")
        or config.get("ollama", {}).get("base_url", "http://localhost:11434")
    )
    return ollama.Client(host=base_url)


def answer_question(
    question: str,
    vector_store: VectorStore,
    config: dict,
    api_key: str,          # kept for interface compatibility — unused with Ollama
    chat_history: list[dict],
    doc_type_filter: str = None,
) -> str:
    """
    Retrieve relevant context from ChromaDB and call the local Ollama model.

    Raises OllamaError (subclass of Exception) on connection/model errors so
    the caller can surface them with st.error() without crashing the app.
    """
    ollama_cfg = config.get("ollama", {})
    model = ollama_cfg.get("model", "llama3.1")
    num_ctx = ollama_cfg.get("num_ctx", 4096)
    temperature = ollama_cfg.get("temperature", 0.1)

    top_k = config["knowledge"].get("top_k_results", 5)
    chunks = vector_store.query(question, top_k=top_k, doc_type_filter=doc_type_filter)

    # Format retrieved context
    if chunks:
        context_blocks = []
        for i, chunk in enumerate(chunks, start=1):
            src = chunk["metadata"].get("source_file", "unknown")
            dtype = chunk["metadata"].get("doc_type", "")
            context_blocks.append(
                f"[Context {i} | source: {src} | type: {dtype}]\n{chunk['text']}"
            )
        context_text = "\n\n---\n\n".join(context_blocks)
    else:
        context_text = "(No relevant context found in the knowledge base.)"

    user_message_content = (
        f"Retrieved context:\n\n{context_text}\n\n"
        f"Question: {question}"
    )

    # Build message list: system → history → new user turn
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(chat_history)
    messages.append({"role": "user", "content": user_message_content})

    client = _build_ollama_client(config)
    response = client.chat(
        model=model,
        messages=messages,
        options={
            "num_ctx": num_ctx,
            "temperature": temperature,
        },
    )
    return response["message"]["content"]


def list_local_models(config: dict) -> list[str]:
    """
    Return model tags available on the configured Ollama server.
    Used by the Config & State tab to populate a model selector.
    """
    try:
        client = _build_ollama_client(config)
        result = client.list()
        return [m["name"] for m in result.get("models", [])]
    except Exception:
        return []
