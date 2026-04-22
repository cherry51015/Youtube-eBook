#!/usr/bin/env python3
"""
scripts/04_generate.py  —  Stage 4: Grounded Chapter Generation

Three-pass generation per chapter:
  Pass A — Section writing: each section is written independently from its
            source chunks. The LLM must cite chunk IDs after each paragraph.
  Pass B — Chapter assembly: sections are joined with proper headings.
  Pass C — Refinement: the full draft is refined for tone, grammar,
            consistent voice, introduction, and key takeaways.

Output per video: data/chapters/<index>_<video_id>.md
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
from utils.prompts import (
    SYSTEM_BOOK_AUTHOR,
    WRITE_SECTION_PROMPT,
    REFINE_CHAPTER_PROMPT,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def format_chunks_for_writing(chunks: list[dict], max_total_chars: int = 1500) -> str:
    """Cap total chars sent to LLM to prevent Ollama timeouts."""
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


def write_section(
    chapter_num: int,
    chapter_title: str,
    section_title: str,
    chunks: list[dict],
    cfg: dict,
) -> str:
    if not chunks:
        return ""
    try:
        prompt = WRITE_SECTION_PROMPT.format(
            chapter_num=chapter_num,
            chapter_title=chapter_title,
            section_title=section_title,
            chunks_text=format_chunks_for_writing(chunks),
        )
        return call(prompt, system=SYSTEM_BOOK_AUTHOR, cfg=cfg)
    except Exception as e:
        log.warning("    Section write failed: %s — using chunk text directly", e)
        # Fallback: just use the raw chunk text as the section content
        return "\n\n".join(c["text"] for c in chunks[:3])


def assemble_draft(chapter_title: str, chapter_num: int,
                   sections: list[dict], section_texts: list[str]) -> str:
    parts = [f"# Chapter {chapter_num}: {chapter_title}\n"]
    for section, text in zip(sections, section_texts):
        if text.strip():
            parts.append(f"\n## {section.get('title', 'Section')}\n")
            parts.append(text.strip())
    return "\n\n".join(parts)


def refine_chapter(chapter_title: str, draft: str, cfg: dict) -> str:
    try:
        prompt = REFINE_CHAPTER_PROMPT.format(
            chapter_title=chapter_title,
            draft=draft[:3000],  # cap draft sent to LLM
        )
        return call(prompt, system=SYSTEM_BOOK_AUTHOR, cfg=cfg)
    except Exception as e:
        log.warning("    Refinement failed: %s — using draft as-is", e)
        return draft


def process_video(struct_path: Path, out_dir: Path, cfg: dict) -> None:
    with open(struct_path) as f:
        data = json.load(f)

    vid_id = data["video_id"]
    idx = data["video_index"]
    chapter_title = data.get("chapter_title", data["title"])
    out_file = out_dir / f"{idx:02d}_{vid_id}.md"

    if out_file.exists():
        log.info("  SKIP  Chapter %02d: %s", idx, chapter_title)
        return

    log.info("  Chapter %02d: %s", idx, chapter_title)
    sections = data.get("sections", [])

    if not sections:
        log.warning("    No sections — skipping")
        return

    # Pass A: write each section independently
    section_texts = []
    for i, section in enumerate(sections, 1):
        log.info("    Section %d/%d: %s", i, len(sections), section.get("title", f"Part {i}"))
        text = write_section(
            chapter_num=idx,
            chapter_title=chapter_title,
            section_title=section.get("title", f"Part {i}"),
            chunks=section.get("chunks", []),
            cfg=cfg,
        )
        section_texts.append(text)

    # Pass B: assemble
    draft = assemble_draft(chapter_title, idx, sections, section_texts)
    log.info("    Draft: %d chars — refining …", len(draft))

    # Pass C: refine
    final = refine_chapter(chapter_title, draft, cfg)

    # Prepend metadata comment for traceability
    header = (
        f"<!-- chapter:{idx} video_id:{vid_id} title:{chapter_title} "
        f"source:{data.get('url','')} -->\n\n"
    )
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(header + final)

    log.info("    ✓ Written: %s (%d chars)", out_file.name, len(final))


def main() -> None:
    cfg = load_config()
    p = paths(cfg)
    p["chapters"].mkdir(parents=True, exist_ok=True)

    struct_files = sorted(
        p["structured"].glob("*.json"),
        key=lambda f: json.load(open(f)).get("video_index", 99),
    )

    if not struct_files:
        log.error("No structured files found. Run 03_structure.py first.")
        sys.exit(1)

    log.info("Generating %d chapters …", len(struct_files))
    for sf in struct_files:
        process_video(sf, p["chapters"], cfg)

    log.info("\n✓ Generation complete → %s", p["chapters"])


if __name__ == "__main__":
    main()