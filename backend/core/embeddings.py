"""Gemini embedding client.

Wraps the google-genai SDK to turn text into 768-dim vectors for semantic search.
Uses asymmetric task types — documents and queries are embedded slightly
differently, which improves retrieval quality — and batches requests to stay within
limits. Free-tier friendly.

Kept separate from the (future) chat LLM client because embeddings return plain
numeric vectors, not structured text that needs schema validation.
"""

from __future__ import annotations

import math
from functools import lru_cache

from google import genai
from google.genai import types

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

# gemini-embedding-001 defaults to 3072 dims; we truncate (Matryoshka) to 768 to
# match the listing_embedding column. Keep EMBED_DIM and the DB vector size in sync.
EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768
_BATCH = 50  # embed_content accepts a list; chunk to stay comfortably within limits


@lru_cache(maxsize=1)
def _client() -> genai.Client:
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Add it to .env.")
    return genai.Client(api_key=settings.gemini_api_key)


def _normalize(vec: list[float]) -> list[float]:
    """Scale to unit length. Recommended for MRL-truncated (<3072) embeddings."""
    norm = math.sqrt(sum(x * x for x in vec))
    return [x / norm for x in vec] if norm else vec


def embed_texts(texts: list[str], *, task_type: str = "RETRIEVAL_DOCUMENT") -> list[list[float]]:
    """Embed many texts, returning one `EMBED_DIM`-dim unit vector each (order preserved)."""
    if not texts:
        return []
    config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=EMBED_DIM)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _BATCH):
        chunk = texts[start : start + _BATCH]
        resp = _client().models.embed_content(model=EMBED_MODEL, contents=chunk, config=config)
        vectors.extend(_normalize(e.values) for e in resp.embeddings)
    return vectors


def embed_query(text: str) -> list[float]:
    """Embed a search query (uses the query task type, not the document one)."""
    return embed_texts([text], task_type="RETRIEVAL_QUERY")[0]
