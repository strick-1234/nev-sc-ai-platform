# -*- coding: utf-8 -*-
"""融合平台工具⑥：知识库检索（SOP 文档，字符二元组匹配）。"""
from __future__ import annotations

import re
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent / "知识库"
_PUNCT = re.compile(r"[\s，。；：、！？,.!?;:()（）【】\"'“”‘’《》<>\-—…]+")


def _bigrams(text: str) -> set[str]:
    t = _PUNCT.sub("", text).lower()
    return {t[i : i + 2] for i in range(len(t) - 1)}


def _chunk(path: Path):
    chunks, cur_title, cur_lines = [], "", []
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if s.startswith("#"):
            if cur_lines:
                chunks.append({"doc": path.stem, "title": cur_title, "text": "\n".join(cur_lines)})
            cur_title, cur_lines = s.lstrip("#").strip(), [s]
        elif s:
            cur_lines.append(s)
    if cur_lines:
        chunks.append({"doc": path.stem, "title": cur_title, "text": "\n".join(cur_lines)})
    return chunks


def search_knowledge(question: str, top_k: int = 3) -> dict:
    qb = _bigrams(question)
    if not qb:
        return {"ok": False, "text": "问题过短，无法检索。"}
    scored = []
    for f in sorted(DOCS_DIR.glob("*.md")):
        for ch in _chunk(f):
            tb = _bigrams(ch["text"])
            if not tb:
                continue
            score = len(qb & tb) + 2 * len(qb & _bigrams(ch["title"]))
            if score > 0:
                scored.append((score, ch))
    scored.sort(key=lambda x: -x[0])
    if not scored:
        return {"ok": True, "found": 0, "text": "知识库中未检索到相关内容，请换一种问法。"}
    segs = []
    for score, ch in scored[:top_k]:
        text = ch["text"]
        if len(text) > 400:
            text = text[:400] + "…"
        segs.append({"doc": ch["doc"], "title": ch["title"], "score": score, "text": text})
    return {"ok": True, "found": len(segs), "segments": segs,
            "text": "\n\n".join(f"《{s['doc']}》/{s['title']}：{s['text']}" for s in segs)}
