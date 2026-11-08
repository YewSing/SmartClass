"""Knowledge base for the AI Learning Assistant (Module 8).

Ingestion:  moodle_client -> sync -> ingest (parsers -> chunker -> embedder) -> kb_chunks
Question:   search (hybrid vector + keyword) -> assistant (prompt -> LLM -> citations)
"""
