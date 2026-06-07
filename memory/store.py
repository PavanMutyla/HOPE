"""
Phase 2 — Memory layer.

Will use ChromaDB for local vector storage. Extract facts and preferences
after each session, inject relevant memories before each LLM call.

Insert a memory_retriever before context_aggregator.user() in hope.py.
Insert a memory_writer after context_aggregator.assistant() in hope.py.
"""
