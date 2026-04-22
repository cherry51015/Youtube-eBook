#!/usr/bin/env python3
"""
scripts/03_structure.py  —  Stage 3: Knowledge Structuring

For each video, asks the LLM to:
  - Identify key topics from the chunks
  - Group chunk IDs into logical sections
  - Assign a section title to each group
  - Extract key technical terms

Output per video: data/structured/<video_id>.json
"""

import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.config_loader import load_config, paths
from utils.llm import call
from utils.prompts import STRUCTURE_PROMPT, SYSTEM_BOOK_AUTHOR

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def format_chunks_for_prompt(chunks: list[dict], max_total_chars: int = 1500) -> str:
    """
    Cap total chars sent to LLM so Ollama doesn't time out on large transcripts.
    """
    lines = []
    total = 0
    for c in chunks:
        entry = f"[{c['id']}] {c['text']}"
        if total + len(entry) > max_total_chars and lines:
            lines.append(f"[...{len(chunks) - len(lines)} more chunks truncated...]")
            break
        lines.append(entry)
        total += len(entry)
    return "\n\n".join(lines)


def parse_structure_response(raw: str, chunks: list[dict]) -> dict:
    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    
    # Try to find JSON anywhere in the response
    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(0)

    try:
        parsed = json.loads(cleaned)
        assert "sections" in parsed and isinstance(parsed["sections"], list)
        assert "key_terms" in parsed and isinstance(parsed["key_terms"], list)
        return parsed
    except Exception as e:
        log.warning("JSON parse failed (%s). Using fallback structure.", e)
        n = len(chunks)
        size = max(1, n // 3)
        sections = []
        for i in range(0, n, size):
            group = chunks[i: i + size]
            sections.append({
                "title": f"Part {len(sections)+1}",
                "chunk_ids": [c["id"] for c in group],
            })
        return {
            "chapter_title": "Chapter",
            "sections": sections,
            "key_terms": [],
        }

def process_video(chunk_path: Path, out_dir: Path, cfg: dict) -> None:
    with open(chunk_path) as f:
        data = json.load(f)

    vid_id = data["video_id"]
    out_file = out_dir / f"{vid_id}.json"

    if out_file.exists():
        log.info("  SKIP  %s", data["title"])
        return

    chunks = data["chunks"]
    if not chunks:
        log.warning("  No chunks for %s — skipping", vid_id)
        return

    log.info("  [%02d] Structuring: %s", data["video_index"], data["title"])

    prompt = STRUCTURE_PROMPT.format(
        title=data["title"],
        chapter_num=data["video_index"],
        chunks_text=format_chunks_for_prompt(chunks),
    )

    try:
        raw = call(prompt, system=SYSTEM_BOOK_AUTHOR, cfg=cfg)
        structure = parse_structure_response(raw, chunks)
    except Exception as e:
        log.warning("  FAILED %s: %s — using fallback", data["title"], e)
        # Fallback: group chunks into 3 sections without LLM
        n = len(chunks)
        size = max(1, n // 3)
        sections = []
        for i in range(0, n, size):
            group = chunks[i: i + size]
            sections.append({
                "title": f"Part {len(sections)+1}",
                "chunk_ids": [c["id"] for c in group],
            })
        structure = {
            "chapter_title": data["title"],
            "sections": sections,
            "key_terms": [],
        }

    # Attach full chunk texts so generate.py doesn't need to re-load chunk file
    chunk_map = {c["id"]: c for c in chunks}
    for section in structure["sections"]:
        section["chunks"] = [
            chunk_map[cid] for cid in section.get("chunk_ids", [])
            if cid in chunk_map
        ]

    output = {
        "video_id": vid_id,
        "video_index": data["video_index"],
        "title": data["title"],
        "url": data.get("url", ""),
        "chapter_title": structure.get("chapter_title", data["title"]),
        "sections": structure["sections"],
        "key_terms": structure.get("key_terms", []),
    }

    with open(out_file, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    log.info("       ✓ %d sections, %d key terms",
             len(structure["sections"]), len(structure.get("key_terms", [])))


def main() -> None:
    cfg = load_config()
    p = paths(cfg)
    p["structured"].mkdir(parents=True, exist_ok=True)

    chunk_files = sorted(p["chunks"].glob("*.json"),
                         key=lambda f: json.load(open(f)).get("video_index", 99))

    if not chunk_files:
        log.error("No chunk files found. Run 02_chunk.py first.")
        sys.exit(1)

    log.info("Structuring %d videos …", len(chunk_files))
    for cf in chunk_files:
        process_video(cf, p["structured"], cfg)

    log.info("\n✓ Structuring complete → %s", p["structured"])


if __name__ == "__main__":
    main()