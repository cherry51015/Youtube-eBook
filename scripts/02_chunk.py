#!/usr/bin/env python3
"""
scripts/02_chunk.py  —  Stage 2: Semantic Chunking

Splits raw transcripts into semantic chunks using two signals:
  1. Timestamp gaps — a pause >= pause_threshold_sec seconds suggests
     a topic break (the speaker paused, likely moving to a new idea).
  2. Sentence boundaries + soft character target — we accumulate
     sentences until reaching target_chars, then cut at the next
     sentence boundary.

This is meaningfully better than naive character splits:
  - Respects the speaker's natural pacing
  - Keeps sentences whole (no mid-sentence cuts into the LLM context)
  - Produces chunks the LLM can reason about without losing context

Output per video: data/chunks/<video_id>.json
  Each chunk:
    { "id": "c01", "text": "...", "start": 12.3, "end": 45.6,
      "char_count": 487, "is_topic_break": true|false }
"""

import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.config_loader import load_config, paths

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def clean_segment_text(text: str) -> str:
    text = re.sub(r"\[.*?\]", "", text)          # remove [Music], [Applause] etc
    text = re.sub(r"\(.*?\)", "", text)          # remove (inaudible) etc
    text = re.sub(r"\s+", " ", text).strip()
    return text


def merge_segments_into_sentences(segments: list[dict]) -> list[dict]:
    """
    Merge raw transcript segments (typically 3-5 word fragments) into
    full sentences, carrying the start timestamp of the first fragment
    and end timestamp of the last.
    """
    merged = []
    buf_text, buf_start, buf_end = "", None, None

    for seg in segments:
        text = clean_segment_text(seg["text"])
        if not text:
            continue
        start = seg.get("start", 0.0)
        end = start + seg.get("duration", 0.0)

        if buf_start is None:
            buf_start = start
        buf_end = end
        buf_text = (buf_text + " " + text).strip()

        # Cut when we see sentence-ending punctuation
        if re.search(r"[.!?]$", buf_text):
            merged.append({"text": buf_text, "start": buf_start, "end": buf_end})
            buf_text, buf_start, buf_end = "", None, None

    if buf_text:
        merged.append({"text": buf_text, "start": buf_start or 0.0, "end": buf_end or 0.0})

    return merged


def chunk_sentences(
    sentences: list[dict],
    target_chars: int,
    max_chars: int,
    min_chars: int,
    pause_threshold: float,
) -> list[dict]:
    """
    Group sentences into chunks using:
      - pause_threshold: a gap >= this many seconds forces a new chunk
      - target_chars: soft character target; cut at next sentence boundary once exceeded
      - max_chars: hard ceiling — force a cut regardless
    """
    chunks = []
    buf_sents, buf_start, buf_end = [], None, None
    is_break = False  # whether this chunk started after a topic break

    def flush(force_break: bool = False) -> None:
        nonlocal buf_sents, buf_start, buf_end, is_break
        text = " ".join(s["text"] for s in buf_sents).strip()
        if len(text) >= min_chars:
            chunks.append({
                "id": f"c{len(chunks)+1:02d}",
                "text": text,
                "start": buf_start,
                "end": buf_end,
                "char_count": len(text),
                "is_topic_break": is_break,
            })
        buf_sents, buf_start, buf_end = [], None, None
        is_break = force_break

    for i, sent in enumerate(sentences):
        prev_end = sentences[i - 1]["end"] if i > 0 else sent["start"]
        gap = sent["start"] - prev_end if i > 0 else 0.0

        current_chars = sum(len(s["text"]) for s in buf_sents) + len(sent["text"])
        force_by_pause = gap >= pause_threshold and buf_sents
        force_by_max = current_chars > max_chars and buf_sents

        if force_by_pause or force_by_max:
            flush(force_break=force_by_pause)

        if buf_start is None:
            buf_start = sent["start"]
        buf_end = sent["end"]
        buf_sents.append(sent)

        current_chars = sum(len(s["text"]) for s in buf_sents)
        if current_chars >= target_chars:
            flush()

    if buf_sents:
        flush()

    return chunks


def process_video(raw_path: Path, out_dir: Path, cfg: dict) -> None:
    cc = cfg["chunking"]
    with open(raw_path) as f:
        data = json.load(f)

    vid_id = data["video_id"]
    out_file = out_dir / f"{vid_id}.json"

    if out_file.exists():
        log.info("  SKIP  %s", data["title"])
        return

    sentences = merge_segments_into_sentences(data["segments"])
    chunks = chunk_sentences(
        sentences,
        target_chars=cc["target_chars"],
        max_chars=cc["max_chars"],
        min_chars=cc["min_chars"],
        pause_threshold=cc["pause_threshold_sec"],
    )

    output = {
        "video_id": vid_id,
        "video_index": data["video_index"],
        "title": data["title"],
        "url": data.get("url", ""),
        "chunk_count": len(chunks),
        "chunks": chunks,
    }
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    log.info("  [%02d] %-45s → %d chunks  (avg %d chars)",
             data["video_index"], data["title"][:45],
             len(chunks),
             sum(c["char_count"] for c in chunks) // max(len(chunks), 1))


def main() -> None:
    cfg = load_config()
    p = paths(cfg)
    p["chunks"].mkdir(parents=True, exist_ok=True)

    raw_files = sorted(p["raw"].glob("*.json"),
                       key=lambda f: f.name)
    raw_files = [f for f in raw_files if f.name != "playlist_metadata.json"]

    if not raw_files:
        log.error("No raw transcripts found. Run 01_ingest.py first.")
        sys.exit(1)

    log.info("Chunking %d transcript files …", len(raw_files))
    for rf in raw_files:
        process_video(rf, p["chunks"], cfg)

    log.info("\n✓ Chunking complete → %s", p["chunks"])


if __name__ == "__main__":
    main()
