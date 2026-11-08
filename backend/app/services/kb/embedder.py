"""Local text embeddings (fastembed + ONNX, CPU, no PyTorch).

An embedding turns text into a vector (384 numbers for bge-small) so that texts
with similar meaning end up close together. Passages and questions MUST be
embedded with the same model, or the distances mean nothing.

BGE models were trained with a short instruction in front of search queries
(not in front of passages); adding it improves retrieval for short questions.
"""
import asyncio
import threading
from pathlib import Path

from app.core.config import settings

QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from fastembed import TextEmbedding

                cache_dir = settings.KB_EMBED_CACHE_DIR or str(Path.home() / ".cache" / "smartclass" / "fastembed")
                _model = TextEmbedding(model_name=settings.KB_EMBED_MODEL, cache_dir=cache_dir)
    return _model


def embed_passages_sync(texts: list[str]) -> list[list[float]]:
    return [v.tolist() for v in _get_model().embed(texts, batch_size=32)]


def embed_query_sync(text: str) -> list[float]:
    return next(iter(_get_model().embed([QUERY_PREFIX + text]))).tolist()


async def embed_passages(texts: list[str]) -> list[list[float]]:
    # CPU-bound: run off the event loop so the API stays responsive while indexing
    return await asyncio.to_thread(embed_passages_sync, texts)


async def embed_query(text: str) -> list[float]:
    return await asyncio.to_thread(embed_query_sync, text)


def warm_up() -> None:
    """Load the model (called at startup so the first question isn't slow)."""
    _get_model()
