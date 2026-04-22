"""
utils/embeddings.py

Loads a local sentence-transformer model once and exposes helpers
for computing cosine similarity between generated text and source chunks.
Used by the verification stage to flag low-confidence paragraphs.
"""

import logging
import numpy as np
from typing import Optional

log = logging.getLogger(__name__)

_model = None


def _get_model(model_name: str = "all-MiniLM-L6-v2"):
    global _model
    if _model is None:
        log.info("Loading embedding model: %s (first call only)", model_name)
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(model_name)
    return _model


def embed(texts: list[str], model_name: str = "all-MiniLM-L6-v2") -> np.ndarray:
    model = _get_model(model_name)
    return model.encode(texts, normalize_embeddings=True, show_progress_bar=False)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    # Both already L2-normalized from embed(), so dot product = cosine similarity
    return float(np.dot(a, b))


def score_paragraph_against_chunks(
    paragraph: str,
    chunk_texts: list[str],
    model_name: str = "all-MiniLM-L6-v2",
) -> dict:
    """
    Returns the max cosine similarity between a paragraph and a list of chunks,
    along with the index of the best-matching chunk.
    """
    if not chunk_texts or not paragraph.strip():
        return {"score": 0.0, "best_chunk_idx": -1}

    all_texts = [paragraph] + chunk_texts
    vecs = embed(all_texts, model_name)
    para_vec = vecs[0]
    chunk_vecs = vecs[1:]

    sims = [cosine_similarity(para_vec, cv) for cv in chunk_vecs]
    best_idx = int(np.argmax(sims))
    return {"score": sims[best_idx], "best_chunk_idx": best_idx}
