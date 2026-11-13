"""Check every benchmark evidence quote really exists on its gold page (after normalization).
Run BEFORE any retrieval experiment. Exits with an error if anything is wrong."""
from __future__ import annotations

import json
import sys
from collections import Counter

from config import BENCHMARK_PATH, PAGES_PATH
from evaluate import norm


def main() -> None:
    pages = {json.loads(l)["page"]: json.loads(l) for l in PAGES_PATH.open(encoding="utf-8")}
    qs = [json.loads(l) for l in BENCHMARK_PATH.open(encoding="utf-8")]
    errors = []
    for q in qs:
        ev = norm(q["evidence_quote"])
        found = [p for p, u in pages.items() if ev in norm(u["text"])]
        if not set(q["gold_pages"]) <= set(found) or not found:
            errors.append(f"{q['id']}: evidence found on {found}, gold says {q['gold_pages']}")
        if q.get("filter") and any(pages[p]["chapter"] != q["filter"]["chapter"] for p in q["gold_pages"]):
            errors.append(f"{q['id']}: filter chapter does not contain the gold page")
    split = Counter(q["split"] for q in qs)
    n_filter = Counter(q["split"] for q in qs if q.get("filter"))
    print(f"questions={len(qs)} split={dict(split)} filter_questions={dict(n_filter)}")
    if len(qs) < 20 or split["dev"] < 15 or split["test"] < 5 or sum(n_filter.values()) < 3 or n_filter["test"] < 1:
        errors.append("benchmark size / split / filter requirements not met")
    if errors:
        print("\n".join(errors))
        sys.exit(1)
    print("OK: all evidence quotes verified on their gold pages")


if __name__ == "__main__":
    main()
