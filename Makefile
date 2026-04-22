.PHONY: all ingest chunk structure generate verify enhance render eval clean help

PYTHON := python3

help:
	@echo ""
	@echo "  Building LLMs from Scratch — Book Pipeline"
	@echo "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "  make all        Run full pipeline end-to-end"
	@echo "  make ingest     Stage 1: Fetch playlist + transcripts"
	@echo "  make chunk      Stage 2: Semantic chunking"
	@echo "  make structure  Stage 3: Knowledge structuring (LLM)"
	@echo "  make generate   Stage 4: Chapter generation (LLM)"
	@echo "  make verify     Stage 5: Grounding verification"
	@echo "  make enhance    Stage 6: Glossary, index, cross-links"
	@echo "  make render     Stage 7: PDF rendering"
	@echo "  make eval       Evaluate pipeline metrics"
	@echo "  make clean      Remove all generated data (keep config)"
	@echo ""
	@echo "  LLM backend (set in config/config.yaml):"
	@echo "    ollama     — local, free (default). Requires: ollama pull mistral"
	@echo "    anthropic  — cloud. Requires: export ANTHROPIC_API_KEY=..."
	@echo "    openai     — cloud. Requires: export OPENAI_API_KEY=..."
	@echo ""

all: ingest chunk structure generate verify enhance render eval

ingest:
	@echo "\n── Stage 1: Ingestion ──────────────────────────────"
	$(PYTHON) scripts/01_ingest.py

chunk:
	@echo "\n── Stage 2: Semantic Chunking ──────────────────────"
	$(PYTHON) scripts/02_chunk.py

structure:
	@echo "\n── Stage 3: Knowledge Structuring ──────────────────"
	$(PYTHON) scripts/03_structure.py

generate:
	@echo "\n── Stage 4: Grounded Generation ────────────────────"
	$(PYTHON) scripts/04_generate.py

verify:
	@echo "\n── Stage 5: Verification ───────────────────────────"
	$(PYTHON) scripts/05_verify.py

enhance:
	@echo "\n── Stage 6: Book Enhancement ───────────────────────"
	$(PYTHON) scripts/06_enhance.py

render:
	@echo "\n── Stage 7: Rendering ──────────────────────────────"
	$(PYTHON) scripts/07_render.py

eval:
	@echo "\n── Evaluation ──────────────────────────────────────"
	$(PYTHON) scripts/eval.py

clean:
	@echo "Removing generated data …"
	rm -rf data/raw data/chunks data/structured data/chapters data/verified outputs
	@echo "Done. Config preserved."
