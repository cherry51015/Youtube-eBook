#!/usr/bin/env python3
"""
scripts/06_enhance.py  —  Stage 6: Book Intelligence Layer

Three enhancements that transform pipeline output into a real book:

1. Glossary — LLM extracts key technical terms + one-sentence definitions
   from each chapter, grounded strictly in chapter text. Duplicates are
   merged (first definition wins). Output: data/outputs/glossary.json

2. Concept Index — term frequency across chapters, for the book's index.
   Output: data/outputs/concept_index.json

3. Cross-chapter linking — detects concepts from other chapters mentioned
   in the current chapter text and inserts (→ Chapter N: Title) references.
   This is done with simple keyword matching (no extra LLM call) to avoid
   introducing latency and potential drift.

The enhanced chapter files are written to: data/outputs/chapters/<file>.md
These are the source for the final PDF renderer.
"""

import json
import logging
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.config_loader import load_config, paths
from utils.llm import call
from utils.prompts import GLOSSARY_PROMPT, SYSTEM_BOOK_AUTHOR

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


# Glossary 

def extract_glossary_for_chapter(chapter_title: str, text: str, cfg: dict) -> list[dict]:
    prompt = GLOSSARY_PROMPT.format(chapter_title=chapter_title, text=text[:6000])
    raw = call(prompt, system=SYSTEM_BOOK_AUTHOR, cfg=cfg)

    cleaned = re.sub(r"```(?:json)?", "", raw).strip().rstrip("`").strip()
    try:
        parsed = json.loads(cleaned)
        return parsed.get("terms", [])
    except Exception as e:
        log.warning("Glossary parse failed: %s", e)
        return []


def build_glossary(chapter_files: list[Path], cfg: dict) -> dict[str, str]:
    glossary: dict[str, str] = {}
    for cf in chapter_files:
        with open(cf, encoding="utf-8") as f:
            text = f.read()

        # Extract chapter title from H1
        title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
        chapter_title = title_match.group(1) if title_match else cf.stem

        log.info("  Glossary: %s", chapter_title[:50])
        terms = extract_glossary_for_chapter(chapter_title, text, cfg)
        for item in terms:
            term = item.get("term", "").strip()
            defn = item.get("definition", "").strip()
            if term and defn and term not in glossary:
                glossary[term] = defn

    return glossary


#  Concept Index

def build_concept_index(chapter_files: list[Path],
                        glossary: dict[str, str]) -> dict[str, list[int]]:
    """
    For each glossary term, record which chapter numbers mention it.
    Returns: { "Attention": [3, 4, 5, 6], "BPE": [2, 3], ... }
    """
    index: dict[str, list[int]] = defaultdict(list)
    for cf in chapter_files:
        with open(cf, encoding="utf-8") as f:
            text = f.read().lower()
        # Parse chapter number from filename prefix (e.g. 04_...)
        num_match = re.match(r"(\d+)_", cf.stem)
        chap_num = int(num_match.group(1)) if num_match else 0

        for term in glossary:
            pattern = re.compile(r"\b" + re.escape(term.lower()) + r"\b")
            if pattern.search(text):
                index[term].append(chap_num)

    return dict(sorted(index.items()))


# Cross-chapter linking 
def insert_crosslinks(text: str, current_num: int,
                      chapter_map: dict[int, str],
                      concept_index: dict[str, list[int]]) -> str:
    """
    For each concept that appears in chapters other than current_num,
    find its first occurrence in the text and append a cross-reference.
    Limit to 5 references to avoid clutter.
    """
    added = 0
    for term, chapters in concept_index.items():
        if added >= 5:
            break
        other_chapters = [c for c in chapters if c != current_num]
        if not other_chapters:
            continue

        # Reference to the lowest-numbered other chapter that covers this term
        ref_chap = min(other_chapters)
        if ref_chap not in chapter_map:
            continue

        ref_title = chapter_map[ref_chap]
        ref_str = f" (→ Chapter {ref_chap}: {ref_title})"

        # Find first occurrence of the term in a paragraph (not in headings/code)
        pattern = re.compile(
            r"(?<![`#])\b" + re.escape(term) + r"\b(?![`])",
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            insert_pos = match.end()
            # Only insert if not already cross-referenced nearby
            vicinity = text[max(0, insert_pos - 5): insert_pos + len(ref_str) + 10]
            if "→ Chapter" not in vicinity:
                text = text[:insert_pos] + ref_str + text[insert_pos:]
                added += 1

    return text


#  Main 

def main() -> None:
    cfg = load_config()
    p = paths(cfg)

    out_chapters_dir = p["outputs"] / "chapters"
    out_chapters_dir.mkdir(parents=True, exist_ok=True)

    # Use verified markdown if available, else fall back to raw chapters
    chapter_files = sorted((p["verified"]).glob("*.md"))
    if not chapter_files:
        log.info("No verified chapters found — using raw chapters")
        chapter_files = sorted(p["chapters"].glob("*.md"))
    if not chapter_files:
        log.error("No chapter files found. Run 04_generate.py first.")
        sys.exit(1)

    log.info("Enhancing %d chapters …", len(chapter_files))

    # Build chapter number → title map for cross-linking
    chapter_map: dict[int, str] = {}
    for cf in chapter_files:
        num_match = re.match(r"(\d+)_", cf.stem)
        if not num_match:
            continue
        chap_num = int(num_match.group(1))
        with open(cf, encoding="utf-8") as f:
            text = f.read()
        title_match = re.search(r"^# Chapter \d+: (.+)$", text, re.MULTILINE)
        title = title_match.group(1) if title_match else cf.stem
        chapter_map[chap_num] = title

    # Step 1: Glossary (LLM-based) 
    log.info("\n[1/3] Building glossary …")
    glossary = build_glossary(chapter_files, cfg)
    log.info("  → %d unique terms", len(glossary))
    with open(p["outputs"] / "glossary.json", "w", encoding="utf-8") as f:
        json.dump(glossary, f, indent=2, ensure_ascii=False)

    # Step 2: Concept index
    log.info("\n[2/3] Building concept index …")
    concept_index = build_concept_index(chapter_files, glossary)
    with open(p["outputs"] / "concept_index.json", "w", encoding="utf-8") as f:
        json.dump(concept_index, f, indent=2, ensure_ascii=False)

    #  Step 3: Cross-link and write final chapters
    log.info("\n[3/3] Inserting cross-references …")
    for cf in chapter_files:
        with open(cf, encoding="utf-8") as f:
            text = f.read()
        num_match = re.match(r"(\d+)_", cf.stem)
        chap_num = int(num_match.group(1)) if num_match else 0
        enhanced = insert_crosslinks(text, chap_num, chapter_map, concept_index)
        out_file = out_chapters_dir / cf.name
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(enhanced)
        log.info("  ✓ %s", cf.name)
    log.info("\n✓ Enhancement complete → %s", p["outputs"])


if __name__ == "__main__":
    main()