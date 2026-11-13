"""Step 1: read the raw Gutenberg text, normalize it and split it into page units.

The source is plain text with no physical pages, so (per GUIDE.md) we split the
book body in reading order into units of at least 1,500 normalized characters.
Units never cross a chapter boundary; a short tail is merged into the previous
unit of the same chapter. Each unit keeps chapter / rule metadata read from the
headings in the text itself (nothing is guessed).
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from config import (DOC_ID, LOG_DIR, MIN_UNIT_CHARS, PAGES_PATH, RAW_PATH,
                    SOURCE_URL)

CHAPTER_RE = re.compile(r"^(I|II|III|IV|V|VI|VII)\. ([A-Z][A-Z ,]+)$")
RULE_RE = re.compile(r"^(\d{1,2})\. [A-Z]")  # rule headings start at column 0
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7}


def normalize(text: str) -> str:
    """Unicode NFC, unify newlines, drop Gutenberg italic/bold markers (_x_, =x=)."""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"_([^_\n]*(?:\n[^_\n]*)?)_", r"\1", text)  # _italic_ (may span 1 newline)
    text = re.sub(r"=([^=\n]+)=", r"\1", text)  # =bold=
    text = re.sub(r"[ \t]+\n", "\n", text)
    return text


def extract_body(raw: str, log: list[str]) -> str:
    """Keep only the book body: from 'I. INTRODUCTORY' to the end-of-book transcriber note."""
    start = raw.find("\nI. INTRODUCTORY\n")
    end = raw.find("[ Transcriber's Note:", start)
    if start < 0 or end < 0:
        raise RuntimeError("Cannot locate book body markers in raw file")
    log.append(f"body: chars {start}..{end} of raw ({len(raw)} chars); "
               "dropped Gutenberg header/licence, title page, table of contents, "
               "end-of-book correction list")
    return raw[start + 1:end].strip() + "\n"


def split_paragraphs(body: str) -> list[dict]:
    """Return paragraphs with chapter / rule labels taken from the headings."""
    paras, chapter, chapter_title, rule = [], None, None, None
    for block in re.split(r"\n\s*\n", body):
        block = block.strip("\n")
        if not block.strip():
            continue
        first = block.splitlines()[0]
        m = CHAPTER_RE.match(first.strip())
        if m and first == first.lstrip():
            chapter, chapter_title, rule = ROMAN[m.group(1)], m.group(2).title(), None
        elif chapter in (2, 3) and RULE_RE.match(first):  # numbered rules only live in ch. II-III
            rule = int(RULE_RE.match(first).group(1))
        paras.append({"text": block, "chapter": chapter,
                      "chapter_title": chapter_title, "rule": rule})
    return paras


def build_units(paras: list[dict]) -> list[dict]:
    units: list[dict] = []
    cur: list[dict] = []

    def flush(force_merge: bool = False) -> None:
        if not cur:
            return
        text = "\n\n".join(p["text"] for p in cur)
        same_ch = units and units[-1]["chapter"] == cur[0]["chapter"]
        if force_merge and same_ch and len(text) < MIN_UNIT_CHARS:
            units[-1]["text"] += "\n\n" + text
            units[-1]["rules"] = sorted(set(units[-1]["rules"]) | {p["rule"] for p in cur if p["rule"]})
        else:
            units.append({"chapter": cur[0]["chapter"], "chapter_title": cur[0]["chapter_title"],
                          "rules": sorted({p["rule"] for p in cur if p["rule"]}), "text": text})
        cur.clear()

    for p in paras:
        if cur and p["chapter"] != cur[0]["chapter"]:
            flush(force_merge=True)
        cur.append(p)
        if len("\n\n".join(x["text"] for x in cur)) >= MIN_UNIT_CHARS:
            flush()
    flush(force_merge=True)

    for i, u in enumerate(units, 1):
        u.update({"document_id": DOC_ID, "source": SOURCE_URL, "page": i,
                  "page_id": f"{DOC_ID}-p{i:02d}", "n_chars": len(u["text"])})
    return units


def main() -> list[dict]:
    log: list[str] = []
    raw = RAW_PATH.read_text(encoding="utf-8")
    body = normalize(extract_body(normalize(raw), log))
    if "_" in body:
        log.append(f"warning: {body.count('_')} stray '_' left after normalization")
    paras = split_paragraphs(body)
    units = build_units(paras)
    short = [u["page_id"] for u in units if u["n_chars"] < MIN_UNIT_CHARS]
    log.append(f"paragraphs={len(paras)} units={len(units)} short_units(<{MIN_UNIT_CHARS})={short or 'none'}")
    log.append("empty/unreadable units: none (plain UTF-8 text, no OCR needed)")
    if len(units) - len(short) < 30:
        raise RuntimeError(f"Only {len(units) - len(short)} valid units (<30)")

    PAGES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PAGES_PATH.open("w", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps(u, ensure_ascii=False) + "\n")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / "ingest_log.txt").write_text("\n".join(log) + "\n", encoding="utf-8")
    print("\n".join(log))
    return units


if __name__ == "__main__":
    main()
