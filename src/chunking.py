"""Step 2: chunking strategies. Chunks never cross a page unit, so `page` stays exact."""
from __future__ import annotations

import re

ENTRY_RE = re.compile(r"^[A-Z][^\n]{0,60}?\.\s")  # e.g. "Data. A plural..." (chapter IV/V entries)
RULE_RE = re.compile(r"^\d{1,2}\. [A-Z]")


def _meta(page: dict, idx: int, strategy: str) -> dict:
    return {
        "document_id": page["document_id"],
        "source": page["source"],
        "page": page["page"],
        "page_id": page["page_id"],
        "chapter": page["chapter"],
        "chapter_title": page["chapter_title"],
        "strategy": strategy,
        "chunk_index": idx,
    }


def fixed_chunks(pages: list[dict], size: int, overlap: int, strategy: str = "A") -> list[dict]:
    """Strategy A: fixed windows of `size` characters, `overlap` characters shared."""
    out = []
    for page in pages:
        text, step, i, start = page["text"], size - overlap, 0, 0
        while start < len(text):
            piece = text[start:start + size]
            if piece.strip():
                out.append({"id": f"{strategy}-{page['page_id']}-{i:03d}", "text": piece,
                            "metadata": {**_meta(page, i, strategy), "char_start": start}})
                i += 1
            if start + size >= len(text):
                break
            start += step
    return out


def paragraph_chunks(pages: list[dict], max_chars: int, strategy: str = "B") -> list[dict]:
    """Strategy B: merge whole paragraphs up to `max_chars`; always start a new chunk at a
    rule heading or a usage entry ("Data. ...") so one chunk = one idea where possible.
    A single paragraph longer than max_chars is kept whole (never cut mid-paragraph)."""
    out = []
    for page in pages:
        paras = [p for p in re.split(r"\n\s*\n", page["text"]) if p.strip()]
        groups, cur = [], []
        for p in paras:
            is_heading = bool(RULE_RE.match(p) or (page["chapter"] in (4, 5) and ENTRY_RE.match(p)))
            too_long = cur and len("\n\n".join(cur + [p])) > max_chars
            if cur and (is_heading or too_long):
                groups.append(cur)
                cur = []
            cur.append(p)
        if cur:
            groups.append(cur)
        for i, g in enumerate(groups):
            out.append({"id": f"{strategy}-{page['page_id']}-{i:03d}", "text": "\n\n".join(g),
                        "metadata": {**_meta(page, i, strategy), "char_start": -1}})
    return out


def build_chunks(pages: list[dict], name: str, cfg: dict) -> list[dict]:
    if cfg["chunking"] == "fixed":
        return fixed_chunks(pages, cfg["chunk_size"], cfg["overlap"], name)
    return paragraph_chunks(pages, cfg["max_chars"], name)
