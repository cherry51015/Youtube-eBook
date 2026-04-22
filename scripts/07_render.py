#!/usr/bin/env python3
"""
scripts/07_render.py  —  Stage 7: Rendering

Reads chapter markdown files + glossary + concept index,
converts Markdown to HTML, injects into the Jinja2 book template,
and renders to PDF with WeasyPrint.

Output:
  outputs/book.pdf   — the final ebook
  outputs/book.md    — concatenated markdown source
  outputs/book.html  — intermediate HTML
"""

import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from utils.config_loader import load_config, paths

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger(__name__)


def md_to_html(text: str) -> str:
    lines = text.split("\n")
    html_lines = []
    in_code = False
    code_lang = ""
    code_buf = []
    in_list = False
    list_tag = "ul"

    def close_list():
        nonlocal in_list
        if in_list:
            html_lines.append(f"</{list_tag}>")
            in_list = False

    def inline(s: str) -> str:
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"__(.+?)__", r"<strong>\1</strong>", s)
        s = re.sub(r"\*(.+?)\*", r"<em>\1</em>", s)
        s = re.sub(r"_(.+?)_", r"<em>\1</em>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        s = re.sub(r"\(→ (Chapter \d+: [^)]+)\)",
                   r'<span class="citation">(→ \1)</span>', s)
        s = re.sub(r"\(Sources?: ([^)]+)\)",
                   r'<span class="citation">(Sources: \1)</span>', s)
        return s

    i = 0
    para_buf = []

    def flush_para():
        if para_buf:
            text_block = " ".join(para_buf).strip()
            if text_block:
                html_lines.append(f"<p>{inline(text_block)}</p>")
            para_buf.clear()

    while i < len(lines):
        line = lines[i]

        if line.startswith("```"):
            flush_para()
            close_list()
            if not in_code:
                in_code = True
                code_lang = line[3:].strip() or "text"
                code_buf = []
            else:
                in_code = False
                escaped = "\n".join(code_buf).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html_lines.append(f'<pre><code class="language-{code_lang}">{escaped}</code></pre>')
                code_buf = []
            i += 1
            continue

        if in_code:
            code_buf.append(line)
            i += 1
            continue

        if line.strip().startswith("<!--"):
            flush_para()
            if "VERIFY" in line:
                html_lines.append('<div class="verify-flag">')
                i += 1
                para = []
                while i < len(lines) and lines[i].strip():
                    para.append(lines[i])
                    i += 1
                html_lines.append(f"<p>{inline(' '.join(para))}</p>")
                html_lines.append("</div>")
            i += 1
            continue

        if line.startswith("# "):
            flush_para()
            close_list()
            m = re.match(r"# Chapter (\d+): (.+)", line)
            if m:
                num, title = m.group(1), m.group(2)
                html_lines.append(f'<h1><span class="chapter-num">Chapter {num}</span>{inline(title)}</h1>')
            else:
                html_lines.append(f"<h1>{inline(line[2:])}</h1>")
            i += 1
            continue

        if line.startswith("## "):
            flush_para()
            close_list()
            html_lines.append(f"<h2>{inline(line[3:])}</h2>")
            i += 1
            continue

        if line.startswith("### "):
            flush_para()
            close_list()
            html_lines.append(f"<h3>{inline(line[4:])}</h3>")
            i += 1
            continue

        if re.match(r"\*\*Key Takeaways\*\*|## Key Takeaways", line, re.I):
            flush_para()
            close_list()
            html_lines.append('<div class="takeaways"><div class="takeaways-title">Key Takeaways</div>')
            i += 1
            html_lines.append("<ul>")
            while i < len(lines) and (lines[i].startswith("- ") or lines[i].startswith("* ")):
                html_lines.append(f"<li>{inline(lines[i][2:])}</li>")
                i += 1
            html_lines.append("</ul></div>")
            continue

        if re.match(r"^[-*] ", line):
            flush_para()
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
                list_tag = "ul"
            html_lines.append(f"<li>{inline(line[2:])}</li>")
            i += 1
            continue

        if re.match(r"^\d+\. ", line):
            flush_para()
            if not in_list:
                html_lines.append("<ol>")
                in_list = True
                list_tag = "ol"
            html_lines.append(f"<li>{inline(re.sub(r'^\\d+\\. ', '', line))}</li>")
            i += 1
            continue

        if not line.strip():
            flush_para()
            close_list()
            i += 1
            continue

        close_list()
        para_buf.append(line)
        i += 1

    flush_para()
    close_list()
    return "\n".join(html_lines)


def load_chapters(chapter_dir: Path) -> list[dict]:
    chapter_files = sorted(
        chapter_dir.glob("*.md"),
        key=lambda f: int(re.match(r"(\d+)", f.stem).group(1))
        if re.match(r"(\d+)", f.stem) else 999
    )
    chapters = []
    for cf in chapter_files:
        with open(cf, encoding="utf-8") as f:
            text = f.read()

        num_match = re.match(r"(\d+)_", cf.stem)
        chap_num = int(num_match.group(1)) if num_match else len(chapters) + 1

        title_match = re.search(r"^# Chapter \d+: (.+)$", text, re.MULTILINE)
        if not title_match:
            title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
        title = title_match.group(1) if title_match else cf.stem

        html = md_to_html(text)
        chapters.append({"num": chap_num, "title": title, "html": html})
        log.info("  Loaded Chapter %02d: %s", chap_num, title[:60])

    return chapters


def main() -> None:
    cfg = load_config()
    p = paths(cfg)
    p["outputs"].mkdir(parents=True, exist_ok=True)

    # Find best available chapter source — works whether stage 6 ran or not
    enhanced_dir = p["outputs"] / "chapters"
    if enhanced_dir.exists() and list(enhanced_dir.glob("*.md")):
        chapter_dir = enhanced_dir
        log.info("Using enhanced chapters from %s", chapter_dir)
    elif p["verified"].exists() and list(p["verified"].glob("*.md")):
        chapter_dir = p["verified"]
        log.info("Using verified chapters from %s", chapter_dir)
    elif p["chapters"].exists() and list(p["chapters"].glob("*.md")):
        chapter_dir = p["chapters"]
        log.info("Using raw chapters from %s", chapter_dir)
    else:
        log.error("No chapter files found. Run 04_generate.py first.")
        sys.exit(1)

    chapters = load_chapters(chapter_dir)
    if not chapters:
        log.error("No chapters loaded from %s", chapter_dir)
        sys.exit(1)
    log.info("Loaded %d chapters total", len(chapters))

    # Load glossary and concept index (optional — empty if stage 6 skipped)
    glossary_file = p["outputs"] / "glossary.json"
    index_file = p["outputs"] / "concept_index.json"
    glossary = json.loads(glossary_file.read_text(encoding="utf-8")) if glossary_file.exists() else {}
    concept_index = json.loads(index_file.read_text(encoding="utf-8")) if index_file.exists() else {}
    log.info("Glossary: %d terms | Concept index: %d entries", len(glossary), len(concept_index))

    # Render HTML via Jinja2 template
    try:
        from jinja2 import Environment, FileSystemLoader
        env = Environment(loader=FileSystemLoader(str(ROOT / "templates")))
        template = env.get_template("book.html.j2")
        html = template.render(
            book=cfg["book"],
            build_date=datetime.now().strftime("%B %Y"),
            chapters=chapters,
            glossary=glossary,
            concept_index=concept_index,
        )
    except Exception as e:
        log.error("Jinja2 template error: %s", e)
        log.error("Make sure templates/book.html.j2 exists")
        sys.exit(1)

    html_path = p["outputs"] / "book.html"
    html_path.write_text(html, encoding="utf-8")
    log.info("Intermediate HTML written: %s", html_path)

    # Write concatenated markdown (fixed — actually writes chapter content)
    md_path = p["outputs"] / "book.md"
    with open(md_path, "w", encoding="utf-8") as f:
        for chap in chapters:
            f.write(f"\n\n---\n\n")
            # Read original markdown file and append it
        # Re-read from source files for clean markdown output
        for cf in sorted(chapter_dir.glob("*.md"),
                         key=lambda f: int(re.match(r"(\d+)", f.stem).group(1))
                         if re.match(r"(\d+)", f.stem) else 999):
            f.write(cf.read_text(encoding="utf-8"))
            f.write("\n\n---\n\n")
    log.info("Concatenated markdown: %s", md_path)

    # Render PDF
    pdf_path = p["outputs"] / "book.pdf"
    log.info("Rendering PDF — this may take 30–90 seconds …")
    try:
        import weasyprint
        weasyprint.HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        size_mb = pdf_path.stat().st_size / 1e6
        log.info("✓ PDF written: %s  (%.1f MB)", pdf_path, size_mb)
    except ImportError:
        log.error("WeasyPrint not installed. Run: pip install weasyprint")
        log.error("HTML available at: %s  — open in browser and print to PDF", html_path)
    except Exception as e:
        log.error("WeasyPrint failed: %s", e)
        log.error("HTML available at: %s  — open in browser and print to PDF", html_path)

    log.info("\n=== Render complete ===")
    log.info("  PDF:      %s", pdf_path)
    log.info("  Markdown: %s", md_path)
    log.info("  HTML:     %s", html_path)


if __name__ == "__main__":
    main()