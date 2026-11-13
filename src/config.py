"""Shared settings. Keep model / store / metric identical across strategies A, B, C."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW_PATH = ROOT / "data" / "raw" / "elements_of_style.txt"
PAGES_PATH = ROOT / "data" / "processed" / "pages.jsonl"
BENCHMARK_PATH = ROOT / "benchmark" / "questions.jsonl"
RESULTS_DIR = ROOT / "results"
LOG_DIR = RESULTS_DIR / "logs"
CHROMA_DIR = ROOT / "chroma_db"

DOC_ID = "strunk-elements-of-style-1920"
SOURCE_URL = "https://www.gutenberg.org/ebooks/37134"
MIN_UNIT_CHARS = 1500

EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384 dims, local, free
TOP_K = 3

STRATEGIES = {
    "A": {"chunking": "fixed", "chunk_size": 500, "overlap": 50, "use_filter": False},
    "B": {"chunking": "paragraph", "max_chars": 800, "use_filter": False},
    "C": {"chunking": "paragraph", "max_chars": 800, "use_filter": True},  # same chunks as B
}
