#!/usr/bin/env python3
"""
scripts/eval.py  —  Pipeline Evaluation

Computes three objective metrics across all chapters:

1. Compression Ratio
   chapter_chars / transcript_chars
   Ideal range: 0.5 – 1.5 (good chapters expand for clarity but not excessively)

2. Semantic Coverage Score
   Average cosine similarity between each source chunk and the chapter text.
   Measures: does the chapter cover the transcript content?
   Higher = more faithful coverage.

3. Grounding Score
   From verification reports: fraction of paragraphs above threshold.
   Higher = more paragraphs are well-grounded in source material.

Outputs: outputs/evaluation_report.json  +  console summary table.
"""

import json
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.config_loader import load_config, paths
from utils.embeddings import embed
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def compression_ratio(chapter_text: str, transcript_text: str) -> float:
    if not transcript_text:
        return 0.0
    return len(chapter_text) / max(len(transcript_text), 1)


def semantic_coverage(chapter_text: str, chunk_texts: list[str],
                      model_name: str) -> float:
    if not chunk_texts or not chapter_text.strip():
        return 0.0
    all_texts = [chapter_text] + chunk_texts
    vecs = embed(all_texts, model_name)
    chapter_vec = vecs[0]
    chunk_vecs = vecs[1:]
    sims = [float(np.dot(chapter_vec, cv)) for cv in chunk_vecs]
    return float(np.mean(sims))


def grounding_score(verification_report: dict) -> float:
    s = verification_report.get("summary", {})
    total = s.get("total", 0)
    verified = s.get("verified", 0)
    if total == 0:
        return 1.0
    return verified / total


def main() -> None:
    cfg = load_config()
    p = paths(cfg)
    emb_model = cfg["embedding"]["model"]

    # Find chapter files
    enhanced_dir = p["outputs"] / "chapters"
    if enhanced_dir.exists() and list(enhanced_dir.glob("*.md")):
        chapter_dir = enhanced_dir
    elif list(p["verified"].glob("*.md")):
        chapter_dir = p["verified"]
    else:
        chapter_dir = p["chapters"]

    chapter_files = sorted(chapter_dir.glob("*.md"))
    if not chapter_files:
        log.error("No chapter files found.")
        sys.exit(1)

    log.info("Loading embedding model …")
    results = []
    header = f"{'Chapter':<40} {'Compress':>9} {'Coverage':>9} {'Grounding':>10}"
    log.info("\n" + header)
    log.info("-" * len(header))

    for cf in chapter_files:
        chapter_text = cf.read_text(encoding="utf-8")

        # Load source chunks from structured dir
        vid_match = re.match(r"\d+_(.+)", cf.stem)
        vid_id = vid_match.group(1) if vid_match else cf.stem
        struct_file = p["structured"] / f"{vid_id}.json"
        chunk_texts, transcript_text = [], ""

        if struct_file.exists():
            struct = json.loads(struct_file.read_text(encoding="latin-1"))
            for section in struct.get("sections", []):
                for chunk in section.get("chunks", []):
                    chunk_texts.append(chunk["text"])
            transcript_text = " ".join(chunk_texts)

        # Load verification report
        ver_file = p["verified"] / f"{cf.stem}.json"
        ver_report = json.loads(ver_file.read_text(encoding="utf-8")) if ver_file.exists() else {}

        cr = compression_ratio(chapter_text, transcript_text)
        cov = semantic_coverage(chapter_text, chunk_texts, emb_model)
        gr = grounding_score(ver_report)

        results.append({
            "chapter": cf.stem,
            "compression_ratio": round(cr, 3),
            "semantic_coverage": round(cov, 3),
            "grounding_score": round(gr, 3),
        })

        label = cf.stem[:38]
        log.info(f"  {label:<38} {cr:>9.3f} {cov:>9.3f} {gr:>10.3f}")

    # Aggregate
    avg_cr = sum(r["compression_ratio"] for r in results) / max(len(results), 1)
    avg_cov = sum(r["semantic_coverage"] for r in results) / max(len(results), 1)
    avg_gr = sum(r["grounding_score"] for r in results) / max(len(results), 1)

    log.info("-" * len(header))
    log.info(f"  {'AVERAGE':<38} {avg_cr:>9.3f} {avg_cov:>9.3f} {avg_gr:>10.3f}")

    report = {
        "chapters": results,
        "aggregate": {
            "avg_compression_ratio": round(avg_cr, 3),
            "avg_semantic_coverage": round(avg_cov, 3),
            "avg_grounding_score": round(avg_gr, 3),
        },
        "interpretation": {
            "compression_ratio": "0.5–1.5 = healthy; <0.5 = too compressed; >2.0 = padded",
            "semantic_coverage": "0.0–1.0 cosine sim; >0.4 = good coverage of transcript",
            "grounding_score": "fraction of paragraphs above stability threshold; >0.8 = reliable",
        },
    }

    out_file = p["outputs"] / "evaluation_report.json"
    out_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    log.info("\n✓ Evaluation report: %s", out_file)


if __name__ == "__main__":
    main()