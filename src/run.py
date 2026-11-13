"""Day 06 pipeline: ingest -> verify benchmark -> chunk A/B/C -> embed + Chroma -> top-3
traces -> Hit@1 / Evidence Hit@3 -> manual-audit sheets.

Run from the repo root:  python src/run.py
"""
from __future__ import annotations

import csv
import json
import platform
import statistics
import time
from datetime import datetime, timezone

import ingest
import verify_benchmark
from chunking import build_chunks
from config import (BENCHMARK_PATH, CHROMA_DIR, EMBED_MODEL, RESULTS_DIR, STRATEGIES,
                    TOP_K)
from evaluate import evaluate_query, summarize
from store import Embedder, get_client, get_collection, query, upsert_chunks

AUDIT_DIR = RESULTS_DIR / "audit"
TRACE_DIR = RESULTS_DIR / "traces"
COHERENCE_PAGES = list(range(1, 11))  # fixed before looking at any score: pages p01..p10
COHERENCE_OFFSET = 600                # position = character 600 of each of those pages


def write_csv(path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def chunk_covering(chunks: list[dict], pages: dict, page_no: int, offset: int) -> dict:
    page_text = pages[page_no]["text"]
    for c in chunks:
        if c["metadata"]["page"] != page_no:
            continue
        start = c["metadata"]["char_start"]
        if start < 0:
            start = page_text.find(c["text"])
        if start <= offset < start + len(c["text"]):
            return c
    raise RuntimeError(f"no chunk covers page {page_no} offset {offset}")


def main() -> None:
    t0 = time.time()
    print("== 1. Ingest")
    units = ingest.main()
    pages = {u["page"]: u for u in units}
    print("== 2. Verify benchmark")
    verify_benchmark.main()
    questions = [json.loads(l) for l in BENCHMARK_PATH.open(encoding="utf-8")]

    print(f"== 3. Load embedding model {EMBED_MODEL}")
    t = time.time()
    emb = Embedder()
    model_load_s = round(time.time() - t, 2)
    client = get_client()

    import chromadb, sentence_transformers, torch
    run_info = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(), "platform": platform.platform(),
        "chromadb": chromadb.__version__, "sentence_transformers": sentence_transformers.__version__,
        "torch": torch.__version__, "embedding_model": EMBED_MODEL, "embedding_dim": emb.dim,
        "query_doc_processing": "same model, no prefix, L2-normalized, cosine distance",
        "vector_store": f"Chroma PersistentClient at {CHROMA_DIR.name}/, HNSW (approximate), cosine",
        "cost_usd": 0, "model_load_s": model_load_s, "strategies": {},
    }

    all_traces, all_chunks = [], {}
    q_vecs = emb.encode([q["question"] for q in questions])
    for name, cfg in STRATEGIES.items():
        print(f"== 4. Strategy {name}: {cfg}")
        chunks = build_chunks(pages.values(), name, cfg)
        all_chunks[name] = chunks
        lens = [len(c["text"]) for c in chunks]
        t = time.time()
        vecs = emb.encode([c["text"] for c in chunks])
        embed_s = round(time.time() - t, 2)
        col = get_collection(client, f"eos_{name}")
        t = time.time()
        load1 = upsert_chunks(col, chunks, vecs)
        load2 = upsert_chunks(col, chunks, vecs)  # reload same version: must not duplicate
        store_s = round(time.time() - t, 2)
        assert load2["count_after"] == len(chunks), "duplicate chunks after reload!"

        t = time.time()
        traces = []
        for q, qv in zip(questions, q_vecs):
            where = {"chapter": q["filter"]["chapter"]} if (cfg["use_filter"] and q.get("filter")) else None
            hits = query(col, qv, TOP_K, where)
            ev = evaluate_query(q, hits)
            traces.append({"strategy": name, "id": q["id"], "split": q["split"], "type": q["type"],
                           "question": q["question"], "filter_applied": where,
                           "gold_pages": q["gold_pages"], "evidence_quote": q["evidence_quote"],
                           **ev, "top3": hits})
        query_s = round(time.time() - t, 2)
        all_traces += traces
        TRACE_DIR.mkdir(parents=True, exist_ok=True)
        with (TRACE_DIR / f"trace_{name}.jsonl").open("w", encoding="utf-8") as f:
            for tr in traces:
                f.write(json.dumps(tr, ensure_ascii=False) + "\n")
        run_info["strategies"][name] = {
            **cfg, "chunks": len(chunks), "len_min": min(lens), "len_mean": round(statistics.mean(lens)),
            "len_median": statistics.median(lens), "len_max": max(lens), "total_chars": sum(lens),
            "embed_s": embed_s, "store_s": store_s, "query_s_all_questions": query_s,
            "first_load": load1, "reload_same_version": load2}
        print(f"   chunks={len(chunks)} embed={embed_s}s store={store_s}s reload_count={load2['count_after']}")

    print("== 5. Metrics")
    summary = summarize(all_traces)
    write_csv(RESULTS_DIR / "metrics.csv", summary)
    for r in summary:
        print(f"   {r['strategy']} {r['split']:4s} Hit@1 {r['hit1']}/{r['N']}  Hit@3 {r['hit3']}/{r['N']}"
              f"  evidence_split {r['evidence_split']}  filter_ok {r['filter_ok']}/{r['filter_questions']}")

    print("== 6. Manual audit sheets (fill score/reason columns by hand)")
    coh = []
    for name in STRATEGIES:
        for i, p in enumerate(COHERENCE_PAGES, 1):
            c = chunk_covering(all_chunks[name], pages, p, COHERENCE_OFFSET)
            coh.append({"strategy": name, "position": f"pos{i:02d}", "page": p, "chunk_id": c["id"],
                        "chunk_text": c["text"], "score_0_2": "", "reason": ""})
    write_csv(AUDIT_DIR / "coherence_labels.csv", coh)

    grd, meta = [], []
    for tr in all_traces:
        if tr["split"] != "test":
            continue
        grd.append({"strategy": tr["strategy"], "id": tr["id"], "question": tr["question"],
                    "evidence_quote": tr["evidence_quote"], "auto_hit3": tr["hit3"],
                    **{f"top{k+1}": f"[{h['metadata']['page_id']} ch{h['metadata']['chapter']}] {h['text']}"
                       for k, h in enumerate(tr["top3"])},
                    "score_0_2": "", "reason": ""})
        for k, h in enumerate(tr["top3"]):
            m = h["metadata"]
            src_page = pages[m["page"]]
            auto_ok = (h["text"] in src_page["text"] and m["chapter"] == src_page["chapter"]
                       and m["source"] == src_page["source"] and m["document_id"] == src_page["document_id"])
            meta.append({"strategy": tr["strategy"], "id": tr["id"], "rank": k + 1, "chunk_id": h["id"],
                         "document_id": m["document_id"], "source": m["source"], "page": m["page"],
                         "chapter": m["chapter"], "filter": json.dumps(tr["filter_applied"]),
                         "auto_text_in_page_and_fields_match": auto_ok, "manual_ok": "", "note": ""})
    write_csv(AUDIT_DIR / "grounding_labels.csv", grd)
    write_csv(AUDIT_DIR / "metadata_check.csv", meta)

    run_info["total_runtime_s"] = round(time.time() - t0, 2)
    (RESULTS_DIR / "run_info.json").write_text(json.dumps(run_info, indent=2), encoding="utf-8")
    print(f"Done in {run_info['total_runtime_s']}s. See results/")


if __name__ == "__main__":
    main()
