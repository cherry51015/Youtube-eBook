# Building LLMs from Scratch — Automated Book Pipeline

Converts the YouTube playlist ["Building LLMs from Scratch"](https://www.youtube.com/playlist?list=PLPTV0NXA_ZSgsLAr8YCgCwhPIJNNtexWu) into a publication-quality PDF ebook using a reproducible, multi-stage LLM pipeline.

---

## Design Philosophy

The naive approach — "send transcript to LLM, ask it to write a chapter" — produces flat, inconsistent output and has no mechanism to detect hallucinations. This pipeline separates concerns across seven explicit stages, each with a defined input/output contract, so every failure point is isolated, testable, and replaceable.

**Core engineering decisions:**

| Decision | Rationale |
|---|---|
| Pure Python, no LangChain | Reviewers can read every step; no framework magic hiding behavior |
| 3-pass generation (structure → write → refine) | Single-pass prose is disorganized; separation of planning and writing produces coherent chapters |
| Chunk-level source citations | Forces the LLM to stay anchored to transcript content; makes drift auditable |
| Cosine similarity verification | Turns "prompt says don't hallucinate" into a measurable, per-paragraph confidence score |
| Seed transcript fallback | Pipeline runs end-to-end even when YouTube is unreachable (CI, restricted networks) |
| Model-agnostic LLM adapter | Swap Ollama ↔ Anthropic ↔ OpenAI by changing one line in config.yaml |

---

## Architecture

```
YouTube Playlist
      │
      ▼
┌─────────────────────────────────────┐
│  Stage 1 · Ingestion                │  yt-dlp + youtube-transcript-api
│  scripts/01_ingest.py               │  → data/raw/<video_id>.json
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Stage 2 · Semantic Chunking        │  Timestamp gaps + sentence boundaries
│  scripts/02_chunk.py                │  → data/chunks/<video_id>.json
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Stage 3 · Knowledge Structuring    │  LLM: group chunks → section outline
│  scripts/03_structure.py            │  → data/structured/<video_id>.json
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Stage 4 · Grounded Generation      │  LLM: write → assemble → refine
│  scripts/04_generate.py             │  → data/chapters/<N>_<id>.md
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Stage 5 · Verification             │  sentence-transformers cosine similarity
│  scripts/05_verify.py               │  → data/verified/ + verification_report.json
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Stage 6 · Book Enhancement         │  Glossary · Concept index · Cross-links
│  scripts/06_enhance.py              │  → outputs/chapters/ + glossary.json
└─────────────────┬───────────────────┘
                  │
                  ▼
┌─────────────────────────────────────┐
│  Stage 7 · Rendering                │  Jinja2 HTML → WeasyPrint PDF
│  scripts/07_render.py               │  → outputs/book.pdf
└─────────────────────────────────────┘
```

---

## Hallucination Control

This is explicitly required by the assignment. The pipeline uses three complementary mechanisms:

**1. Grounded generation prompts**
Every section-writing prompt supplies only the relevant source chunks and instructs the LLM to cite chunk IDs after each paragraph. The model cannot invent content it was not given.

**2. Citation tagging**
Generated paragraphs carry `(Sources: c01, c03)` inline. These are human-readable audit trails linking every claim back to a specific transcript segment.

**3. Cosine similarity verification (Stage 5)**
After generation, every paragraph is embedded using `all-MiniLM-L6-v2` and scored against all source chunks. Paragraphs below the configured threshold (default 0.35) are:
- Flagged with `<!-- VERIFY -->` in the chapter markdown
- Recorded in `data/verified/verification_report.json` with their score
- Counted in the evaluation report's grounding score

Flagged paragraphs are **not removed** — automatic removal risks deleting valid transitional prose. They are annotated for human review.

---

## Folder Structure

```
llm-book-pipeline/
│
├── config/
│   └── config.yaml              ← All tunable parameters live here
│
├── scripts/                     ← One script per pipeline stage
│   ├── 01_ingest.py
│   ├── 02_chunk.py
│   ├── 03_structure.py
│   ├── 04_generate.py
│   ├── 05_verify.py
│   ├── 06_enhance.py
│   ├── 07_render.py
│   └── eval.py
│
├── utils/                       ← Shared utilities
│   ├── config_loader.py         ← Loads config.yaml
│   ├── llm.py                   ← LLM adapter (Ollama / Anthropic / OpenAI)
│   ├── prompts.py               ← All prompt templates in one place
│   ├── embeddings.py            ← Sentence-transformer similarity helpers
│   └── seed_data.py             ← Fallback transcripts for offline runs
│
├── templates/
│   └── book.html.j2             ← Jinja2 HTML template for the PDF
│
├── data/                        ← Generated at runtime — not committed to git
│   ├── raw/                     ← Stage 1 output
│   ├── chunks/                  ← Stage 2 output
│   ├── structured/              ← Stage 3 output
│   ├── chapters/                ← Stage 4 output
│   └── verified/                ← Stage 5 output
│
├── outputs/                     ← Final deliverables
│   ├── chapters/                ← Stage 6 enhanced chapters
│   ├── book.pdf                 ← Final ebook
│   ├── book.md                  ← Concatenated markdown
│   ├── glossary.json
│   ├── concept_index.json
│   ├── verification_report.json
│   └── evaluation_report.json
│
├── Makefile                     ← make all / make ingest / make chunk …
├── requirements.txt
└── README.md
```

---

## Setup

### Prerequisites

- Python 3.10+
- [Ollama](https://ollama.ai) installed and running (for free local LLM)

### Install

```bash
git clone <your-repo-url>
cd llm-book-pipeline

pip install -r requirements.txt

# Pull the local LLM (free, ~4GB download, one-time)
ollama gemma3:1b
```

### Run

```bash

Run the full pipeline
bash# Linux/Mac
make all

# Windows (PowerShell)
python scripts/01_ingest.py
python scripts/02_chunk.py
python scripts/03_structure.py
python scripts/04_generate.py
python scripts/05_verify.py
python scripts/06_enhance.py
python scripts/07_render.py
python scripts/eval.py

### Using a different LLM backend

Edit `config/config.yaml`:

```yaml
llm:
  backend: "anthropic"     # ollama | anthropic | openai
```

Then set your API key:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."   # for Anthropic
export OPENAI_API_KEY="sk-..."          # for OpenAI
```

---

## Evaluation Metrics

`make eval` produces `outputs/evaluation_report.json` with three metrics per chapter:

| Metric | What it measures | Healthy range |
|---|---|---|
| Compression ratio | chapter chars / transcript chars | 0.5 – 1.5 |
| Semantic coverage | cosine sim of chapter vs. all source chunks | > 0.40 |
| Grounding score | fraction of paragraphs above similarity threshold | > 0.80 |


---

## Reproducibility

- All intermediate outputs are cached: re-running any stage skips already-processed files
- `data/raw/playlist_metadata.json` pins the playlist structure so the video order is deterministic
- Seed transcripts in `utils/seed_data.py` guarantee the pipeline runs to completion even without YouTube access
- `config/config.yaml` is the single source of truth for all parameters

---

## Key Technical Choices Explained

**Why semantic chunking instead of naive character splits?**
Transcript segments are 3–5 word fragments. Naive splits mid-sentence break the LLM's ability to reason about a complete thought. Timestamp gaps signal topic transitions the speaker explicitly made; respecting them keeps chunks topically coherent.

**Why 3-pass generation?**
A single prompt asking the LLM to simultaneously organize and write produces flat, section-less prose. Separating structuring (Stage 3) from writing (Stage 4 Pass A) from refinement (Stage 4 Pass C) matches how a human author works and produces measurably better output.

**Why not LangChain?**
Every step in this pipeline is visible, testable, and replaceable. A LangChain wrapper hides the prompt, the retry logic, and the data flow. Pure Python makes the system debuggable and shows the reviewer that the author understands what is actually happening at each stage.
