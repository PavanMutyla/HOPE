"""Mem0 client config — points Mem0's vector store at a Chroma collection
separate from episodic memory's (same backend, different persist dir), and
pins the LLM/embedder to HOPE's own OpenAI credentials.

Two things here are not optional tuning, confirmed by spike (see
docs/HOPE_Semantic_Memory_Spike_Notes.md):
- Mem0's default LLM (gpt-5-mini) rejects Mem0's own hardcoded
  temperature=0.1, so the model must be overridden explicitly.
- Mem0's history_db_path defaults to ~/.mem0/history.db, outside
  data_store/ entirely, unless set explicitly.
"""

from pathlib import Path
from typing import Any

from settings import settings

COLLECTION_NAME = "semantic_facts"


def build_mem0_config(
    persist_dir: str | Path | None = None,
    history_db_path: str | Path | None = None,
) -> dict[str, Any]:
    persist_dir = str(persist_dir or settings.semantic_persist_dir)
    history_db_path = str(history_db_path or settings.semantic_history_db_path)
    Path(history_db_path).parent.mkdir(parents=True, exist_ok=True)

    return {
        "vector_store": {
            "provider": "chroma",
            "config": {
                "collection_name": COLLECTION_NAME,
                "path": persist_dir,
            },
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": settings.summarizer_model,
                "temperature": 0.1,
                "api_key": settings.openai_api_key,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "api_key": settings.openai_api_key,
            },
        },
        "history_db_path": history_db_path,
        "version": "v1.1",
    }
