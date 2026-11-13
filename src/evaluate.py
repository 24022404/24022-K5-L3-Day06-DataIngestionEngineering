"""Step 4: automatic retrieval metrics (Hit@1, Evidence Hit@3) from top-3 traces.

A retrieved chunk is a hit when it comes from a gold page AND contains the whole
evidence quote (whitespace/case-insensitive). Coherence and grounding are NOT
inferred here: they are labelled by hand in results/audit/*.csv.
"""
from __future__ import annotations

import re


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def evaluate_query(question: dict, hits: list[dict]) -> dict:
    ev = norm(question["evidence_quote"])
    flags = [h["metadata"]["page"] in question["gold_pages"] and ev in norm(h["text"]) for h in hits]
    page_flags = [h["metadata"]["page"] in question["gold_pages"] for h in hits]
    flt = question.get("filter")
    return {
        "hit_flags": flags,
        "hit1": bool(flags[:1] and flags[0]),
        "hit3": any(flags[:3]),
        # gold page reached but evidence not fully inside one chunk -> evidence split
        "page_hit3_no_evidence": any(page_flags[:3]) and not any(flags[:3]),
        "filter_ok": (all(h["metadata"]["chapter"] == flt["chapter"] for h in hits[:3])
                      if flt else None),
    }


def summarize(traces: list[dict]) -> list[dict]:
    rows = []
    for strat in sorted({t["strategy"] for t in traces}):
        for split in ("dev", "test"):
            ts = [t for t in traces if t["strategy"] == strat and t["split"] == split]
            if not ts:
                continue
            fl = [t for t in ts if t["filter_ok"] is not None]
            rows.append({
                "strategy": strat, "split": split, "N": len(ts),
                "hit1": sum(t["hit1"] for t in ts), "hit3": sum(t["hit3"] for t in ts),
                "evidence_split": sum(t["page_hit3_no_evidence"] for t in ts),
                "filter_questions": len(fl),
                "filter_ok": sum(bool(t["filter_ok"]) for t in fl),
            })
    return rows
