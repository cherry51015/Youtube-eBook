#!/usr/bin/env python3
"""
scripts/05_verify.py  —  Stage 5: Verification Layer

For each generated chapter, scores every paragraph against the source
transcript chunks using cosine similarity on sentence embeddings.

Paragraphs with similarity below the configured threshold are flagged.
This catches content that diverged from the source — not necessarily
hallucinations, but claims not directly grounded in transcript text.

Output per chapter: data/verified/<chapter_file>.json
  {
    "chapter": "...",
    "paragraphs": [
      { "text": "...", "score": 0.71, "status": "verified",
        "best_chunk_id": "c03" },
      { "text": "...", "score": 0.28, "status": "FLAGGED",
        "best_chunk_id": "c07" }
    ],
    "summary": { "total": N, "verified": N, "flagged": N,
                 "avg_score": 0.62 }
  }

Flagged paragraphs are NOT removed from the final book. They are
annotated with <!-- VERIFY --> in the chapter markdown so a human
reviewer can inspect them. This is the correct tradeoff: automatic
removal risks deleting valid content; annotation preserves it for review.
"""

import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.config_loader import load_config, paths
from utils.embeddings import score_paragraph_against_chunks

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def extract_paragraphs(md_text: str) -> list[str]:
    # Remove HTML comments and headings, split on blank lines
    text = re.sub(r"<!--.*?-->", "", md_text, flags=re.DOTALL)
    blocks = re.split(r"\n{2,}", text)
    paras = []
    for b in blocks:
        b = b.strip()
        # Keep only non-empty, non-heading, non-code-fence blocks of >= 40 chars
        if b and not b.startswith("#") and not b.startswith("```") and len(b) >= 40:
            paras.append(b)
    return paras


def load_source_chunks(structured_dir: Path, vid_id: str) -> list[dict]:
    struct_file = structured_dir / f"{vid_id}.json"
    if not struct_file.exists():
        return []
    with open(struct_file) as f:
        data = json.load(f)
    chunks = []
    for section in data.get("sections", []):
        chunks.extend(section.get("chunks", []))
    return chunks


def annotate_chapter_markdown(md_text: str, flagged_paras: set[str]) -> str:
    if not flagged_paras:
        return md_text
    lines = md_text.split("\n")
    result = []
    buf = []

    def flush_buf():
        block = "\n".join(buf).strip()
        if block in flagged_paras:
            result.append("<!-- VERIFY: low grounding score -->\n" + block)
        else:
            result.append(block)
        buf.clear()

    for line in lines:
        if line.strip() == "":
            if buf:
                flush_buf()
            result.append("")
        else:
            buf.append(line)

    if buf:
        flush_buf()

    return "\n".join(result)


def process_chapter(chapter_path: Path, verified_dir: Path,
                    structured_dir: Path, cfg: dict) -> dict:
    with open(chapter_path, encoding="utf-8") as f:
        md_text = f.read()

    # Extract video_id from the metadata comment at top of file
    match = re.search(r"video_id:(\S+)", md_text)
    vid_id = match.group(1) if match else chapter_path.stem.split("_", 1)[-1]

    out_json = verified_dir / f"{chapter_path.stem}.json"
    out_md = verified_dir / f"{chapter_path.stem}.md"

    if out_json.exists():
        log.info("  SKIP  %s", chapter_path.name)
        return {}

    source_chunks = load_source_chunks(structured_dir, vid_id)
    chunk_texts = [c["text"] for c in source_chunks]
    chunk_ids = [c["id"] for c in source_chunks]

    paragraphs = extract_paragraphs(md_text)
    threshold = cfg["embedding"]["verification_threshold"]
    emb_model = cfg["embedding"]["model"]

    results = []
    flagged_paras = set()

    for para in paragraphs:
        if not chunk_texts:
            # No source chunks available — pass through
            results.append({"text": para, "score": 1.0,
                            "status": "no_source", "best_chunk_id": None})
            continue

        scored = score_paragraph_against_chunks(para, chunk_texts, emb_model)
        score = scored["score"]
        best_idx = scored["best_chunk_idx"]
        best_chunk_id = chunk_ids[best_idx] if best_idx >= 0 else None
        status = "verified" if score >= threshold else "FLAGGED"

        if status == "FLAGGED":
            flagged_paras.add(para)

        results.append({
            "text": para[:120] + "…" if len(para) > 120 else para,
            "score": round(score, 4),
            "status": status,
            "best_chunk_id": best_chunk_id,
        })

    n_flagged = sum(1 for r in results if r["status"] == "FLAGGED")
    n_verified = sum(1 for r in results if r["status"] == "verified")
    avg_score = sum(r["score"] for r in results) / max(len(results), 1)

    report = {
        "chapter_file": chapter_path.name,
        "video_id": vid_id,
        "paragraphs": results,
        "summary": {
            "total": len(results),
            "verified": n_verified,
            "flagged": n_flagged,
            "avg_score": round(avg_score, 4),
            "threshold": threshold,
        },
    }

    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Write annotated markdown
    annotated = annotate_chapter_markdown(md_text, flagged_paras)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(annotated)

    log.info("  %-35s  verified=%d  flagged=%d  avg_score=%.3f",
             chapter_path.stem[:35], n_verified, n_flagged, avg_score)

    return report


def main() -> None:
    cfg = load_config()
    p = paths(cfg)
    p["verified"].mkdir(parents=True, exist_ok=True)

    chapter_files = sorted(p["chapters"].glob("*.md"))
    if not chapter_files:
        log.error("No chapter files found. Run 04_generate.py first.")
        sys.exit(1)

    log.info("Loading embedding model: %s", cfg["embedding"]["model"])
    log.info("Verifying %d chapters (threshold=%.2f) …",
             len(chapter_files), cfg["embedding"]["verification_threshold"])

    all_reports = []
    for cf in chapter_files:
        report = process_chapter(cf, p["verified"], p["structured"], cfg)
        if report:
            all_reports.append(report)

    # Aggregate summary
    total_paras = sum(r["summary"]["total"] for r in all_reports)
    total_flagged = sum(r["summary"]["flagged"] for r in all_reports)
    avg_score = (sum(r["summary"]["avg_score"] for r in all_reports)
                 / max(len(all_reports), 1))

    log.info("\n=== Verification Summary ===")
    log.info("  Paragraphs:  %d total | %d verified | %d flagged (%.1f%%)",
             total_paras, total_paras - total_flagged, total_flagged,
             100 * total_flagged / max(total_paras, 1))
    log.info("  Avg grounding score: %.3f  (threshold: %.2f)",
             avg_score, cfg["embedding"]["verification_threshold"])

    with open(p["verified"] / "verification_report.json", "w") as f:
        json.dump({
            "chapters": all_reports,
            "aggregate": {
                "total_paragraphs": total_paras,
                "total_flagged": total_flagged,
                "avg_score": round(avg_score, 4),
            },
        }, f, indent=2)

    log.info("\n✓ Verification complete → %s", p["verified"])


if __name__ == "__main__":
    main()
