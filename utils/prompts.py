"""
utils/prompts.py

All LLM prompt templates live here.
Changing a prompt = change here only. Nothing else to touch.
"""


SYSTEM_BOOK_AUTHOR = """You are a senior technical author converting educational video transcripts \
into a professional book. Your writing is precise, pedagogical, and grounded strictly in the \
provided source material. You never invent facts, examples, or code not present in the source. \
If something is unclear in the transcript, you write around it — you do not fill gaps with \
assumptions."""


# ── Stage 3A: Structuring ─────────────────────────────────────────────────────

STRUCTURE_PROMPT = """Video title: {title}
Chapter number: {chapter_num}

Transcript chunks:
{chunks_text}

Return ONLY this JSON, nothing else, no markdown:
{{
  "chapter_title": "title here",
  "sections": [
    {{"title": "section name", "chunk_ids": ["c01", "c02"]}}
  ],
  "key_terms": ["term1", "term2", "term3"]
}}"""

# ── Stage 3B: Writing ─────────────────────────────────────────────────────────

WRITE_SECTION_PROMPT = """You are writing one section of a technical book chapter.

Book: "Building LLMs from Scratch: A Complete Technical Guide"
Chapter {chapter_num}: {chapter_title}
Section: {section_title}

Source chunks you MUST use (cite by ID in parentheses at end of each paragraph):
{chunks_text}

Instructions:
- Write 2–4 paragraphs of clear, technical prose.
- Derive every claim directly from the chunks above.
- If the chunk contains code, reproduce it in a fenced code block.
- After each paragraph, add a citation like: (Sources: c01, c03)
- Do NOT invent examples, formulas, or code absent from the chunks.
- Do NOT start with "In this section" or any meta-commentary.
- Output only the prose. No section heading — that will be added separately."""


# ── Stage 3C: Refinement ──────────────────────────────────────────────────────

REFINE_CHAPTER_PROMPT = """You are editing a draft book chapter for final publication.

Chapter title: {chapter_title}

Draft:
{draft}

Tasks (make minimal edits — preserve all technical content):
1. Fix grammatical errors and awkward phrasing.
2. Ensure consistent voice: clear, authoritative, third-person technical prose.
3. Remove any meta-commentary like "In this video the instructor says...".
4. Ensure code blocks are properly fenced with the language tag (```python).
5. Add a 3–5 sentence chapter introduction at the very top if one is missing.
6. Add a "Key Takeaways" bullet list (4–6 points) at the very bottom.
7. Keep all (Sources: ...) citations intact.

Return the complete refined chapter text in Markdown. Nothing else."""


# ── Glossary generation ───────────────────────────────────────────────────────

GLOSSARY_PROMPT = """You are given the full text of a technical book chapter.

Chapter: {chapter_title}
Text:
{text}

Extract every distinct technical term that a reader might need defined.
For each term, write a one-sentence definition using ONLY information from the text above.

Return ONLY valid JSON (no markdown, no extra text):
{{
  "terms": [
    {{"term": "Tokenization", "definition": "The process of converting raw text into integer token IDs that a neural network can process."}},
    {{"term": "BPE", "definition": "Byte Pair Encoding, a subword tokenization algorithm that merges the most frequent adjacent token pairs iteratively."}}
  ]
}}"""


# ── Cross-chapter linking ─────────────────────────────────────────────────────

CROSSLINK_PROMPT = """You are given a list of all chapter titles and their key terms.

Chapter map:
{chapter_map}

Current chapter being edited: Chapter {current_num} — {current_title}
Current chapter text:
{text}

Task:
Find up to 5 places in the text where a concept from a DIFFERENT chapter is mentioned.
For each, insert a cross-reference immediately after the first mention, like:
  (→ Chapter 4: Multi-Head Attention)

Rules:
- Only insert references that are genuinely helpful.
- Do not reference the current chapter.
- Return the complete edited text with cross-references inserted. Nothing else."""
