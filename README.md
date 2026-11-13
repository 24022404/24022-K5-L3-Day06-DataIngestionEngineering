# Day 06 · Data Ingestion Engineering — The Elements of Style

Retrieval benchmark of 3 data-preparation strategies on William Strunk Jr., *The Elements of Style* (1920), Project Gutenberg #37134 (public domain in the USA).

- Embedding: `sentence-transformers/all-MiniLM-L6-v2` (384 dims, local CPU, free)
- Vector store: Chroma `PersistentClient` (folder `chroma_db/`), cosine, HNSW
- No Docker, no API key, cost 0 USD

## Setup (Windows cmd)

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
curl -L -o data\raw\elements_of_style.txt https://www.gutenberg.org/ebooks/37134.txt.utf-8
```
(macOS/Linux: `source .venv/bin/activate`.) The first run downloads the embedding model (~90 MB) from Hugging Face.

## Run

```
python src/run.py
```

This runs everything: ingest → verify benchmark → chunk A/B/C → embed + store in Chroma (loads twice to check no duplicates) → top-3 retrieval for every question → metrics → manual-audit sheets.

## Layout

| Path | Content |
|---|---|
| `data/raw/elements_of_style.txt` | raw source (Gutenberg licence header kept) |
| `data/manifest.json` | source, licence, page-counting rule, 47 units with chars |
| `data/processed/pages.jsonl` | normalized page units (generated) |
| `benchmark/questions.jsonl` | 21 questions (16 dev / 5 test), gold page + evidence |
| `src/` | `ingest.py`, `chunking.py`, `store.py`, `evaluate.py`, `verify_benchmark.py`, `run.py`, `config.py` |
| `artifacts/experiment_log.csv` | configs, hypotheses, results |
| `results/metrics.csv` | Hit@1 / Evidence Hit@3 per strategy and split |
| `results/traces/trace_{A,B,C}.jsonl` | full top-3 trace per question (text, score, metadata, hit flags) |
| `results/run_info.json` | library versions, model, timings, chunk stats, reload check |
| `results/logs/ingest_log.txt` | ingest log (removed parts, short/empty units) |
| `results/audit/*.csv` | manual labels: coherence (10 positions × 3), grounding (5 test × 3), metadata check |
| `report/individual/` | individual report |

## Strategies

| | Chunking | Retrieval |
|---|---|---|
| A | fixed 500 chars, overlap 50, inside each page unit | no filter |
| B | whole paragraphs merged up to 800 chars; new chunk at each rule heading / usage entry | no filter |
| C | same chunks as B | `where chapter = <chapter named in the question>` only for filter questions |
