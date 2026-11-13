# Benchmark

`questions.jsonl`: 21 questions written before any retrieval run (16 dev / 5 test).

- Fields: `id`, `split`, `type`, `question`, `expected_answer`, `gold_source_id`, `gold_page`, `gold_pages`, `evidence_quote`, `filter`.
- Types: `truc_tiep` (direct), `dien_dat_lai` (paraphrased), `dieu_kien` / `ngoai_le` (condition / exception), `metadata_filter`.
- Filter questions: q14, q15, q16 (dev) and q20 (test). The filter value (`chapter`) is the chapter the user names in the question itself, given before retrieval; it is never taken from the gold answer.
- Split: by question, before running anything. Leak risk: dev and test come from the same book (test questions q17-q21 are on pages 23, 27, 37, 44; dev q-pages are different pages, but chapters overlap).
- Verification: `python src/verify_benchmark.py` checks that each evidence quote appears verbatim (after whitespace/case normalization) on its gold page, and that the requirements (>=20, >=15/5, >=3 filter, >=1 filter in test) hold. Each quote was also read against the source text by hand.
- Strategy selection rule, fixed before looking at test: highest dev Evidence Hit@3, then dev Hit@1, then fewer chunks.
