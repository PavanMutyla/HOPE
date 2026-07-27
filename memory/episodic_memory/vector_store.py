"""Chroma-backed semantic index over episodic summaries.

Only the `summary` field is embedded — raw conversational turns embed badly
("yeah, let's do that instead" has no standalone vector meaning); production
memory systems (Mem0, Letta) embed a compacted summary and store the raw
content as the payload a hit points back to. See
docs/HOPE_Memory_Framework.md §3.8 and docs/HOPE_Episodic_Storage_Design.md §5.

A query returns episode ids only — full hydration (messages + media) happens
via episodic.get_episode(), never through this module.
"""

from pathlib import Path
from typing import Any

import chromadb

_COLLECTION_NAME = "episodic_summaries"


class EpisodicVectorStore:
    def __init__(
        self,
        persist_dir: str | Path,
        collection_name: str = _COLLECTION_NAME,
        embedding_function: Any = None,
    ):
        self._client = chromadb.PersistentClient(path=str(persist_dir))
        kwargs = {}
        if embedding_function is not None:
            kwargs["embedding_function"] = embedding_function
        self._collection = self._client.get_or_create_collection(collection_name, **kwargs)

    def upsert(self, episode_id: str, summary: str, metadata: dict) -> None:
        self._collection.upsert(ids=[episode_id], documents=[summary], metadatas=[metadata])

    def query(self, text: str, k: int = 5, agent: str | None = None) -> list[str]:
        where = {"agent": agent} if agent else None
        result = self._collection.query(query_texts=[text], n_results=k, where=where)
        ids = result.get("ids") or [[]]
        return ids[0]
