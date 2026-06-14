"""Reflection store — BM25-backed persistence for post-task reflections.

Stores structured reflections as a JSON array on disk.  A minimal BM25
index (zero external deps) enables semantic retrieval of relevant past
lessons before new tasks begin.
"""
from __future__ import annotations
import json
import math
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PATH = str(Path(__file__).resolve().parent.parent.parent / "reflections.json")


# ---------------------------------------------------------------------------
# Lightweight tokenizer (shared with search engine, duplicated to stay
# self-contained within the memory layer)
# ---------------------------------------------------------------------------

_CJK_RE = re.compile(r"[一-鿿]")
_WORD_RE = re.compile(r"[a-z]+")

_STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会",
    "着", "没有", "看", "好", "自己", "这", "那", "a", "an", "the",
    "is", "are", "was", "were", "be", "to", "of", "in", "for", "on",
    "with", "at", "by", "from", "and", "or", "not", "no", "so", "if",
}


def _tokenize(text: str) -> list[str]:
    t = text.lower()
    tokens: list[str] = []
    cjk: list[str] = []
    for ch in t:
        if _CJK_RE.match(ch) and ch not in _STOPWORDS:
            cjk.append(ch)
            tokens.append(ch)
    for i in range(len(cjk) - 1):
        bg = cjk[i] + cjk[i + 1]
        if bg not in _STOPWORDS:
            tokens.append(bg)
    for m in _WORD_RE.finditer(t):
        w = m.group()
        if w not in _STOPWORDS and len(w) > 1:
            tokens.append(w)
    return tokens


# ---------------------------------------------------------------------------
# ReflectionStore
# ---------------------------------------------------------------------------


class ReflectionStore:
    """BM25-indexed persistent store for task reflections.

    Each reflection is a dict with keys: id, timestamp, task_summary,
    outcome, reflection, keywords.
    """

    def __init__(self, path: str | None = None) -> None:
        self._path = Path(path or DEFAULT_PATH)
        self._records: list[dict] = []
        # BM25 index
        self._docs: list[list[str]] = []   # tokenised documents
        self._df: dict[str, int] = {}
        self._idf: dict[str, float] = {}
        self._avgdl: float = 0.0
        self._N: int = 0
        self._k1 = 1.5
        self._b = 0.75
        self._load()

    # ------------------------------------------------------------------
    def save(self, reflection: dict) -> None:
        """Append a reflection, persist atomically, and update the index."""
        rec = dict(reflection)
        self._records.append(rec)
        # Index the new record
        doc_text = f"{rec.get('task_summary','')} {rec.get('reflection','')} {' '.join(rec.get('keywords',[]))}"
        tokens = _tokenize(doc_text)
        self._docs.append(tokens)
        for t in set(tokens):
            self._df[t] = self._df.get(t, 0) + 1
        self._N = len(self._records)
        total_len = sum(len(d) for d in self._docs)
        self._avgdl = total_len / max(self._N, 1)
        self._compute_idf()
        self._write_atomic()

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        """BM25 search over stored reflections. Returns top_k results."""
        if self._N == 0:
            return []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []
        scores: list[tuple[int, float]] = []
        for i, doc in enumerate(self._docs):
            dl = len(doc)
            if dl == 0:
                continue
            score = 0.0
            for t in q_tokens:
                idf = self._idf.get(t, 0.0)
                if idf == 0.0:
                    continue
                f = doc.count(t)
                num = f * (self._k1 + 1.0)
                den = f + self._k1 * (1.0 - self._b + self._b * dl / self._avgdl)
                score += idf * (num / den)
            if score > 0:
                scores.append((i, score))
        scores.sort(key=lambda x: x[1], reverse=True)
        return [self._records[i] for i, _ in scores[:top_k]]

    # ------------------------------------------------------------------
    def _compute_idf(self) -> None:
        self._idf = {}
        for term, df in self._df.items():
            self._idf[term] = math.log((self._N - df + 0.5) / (df + 0.5) + 1.0)

    def _write_atomic(self) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(self._records, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, self._path)

    def _load(self) -> None:
        if not self._path.exists():
            self._records = []
            return
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                self._records = json.load(fh)
        except (json.JSONDecodeError, OSError):
            self._records = []
        # Rebuild index
        for rec in self._records:
            doc_text = f"{rec.get('task_summary','')} {rec.get('reflection','')} {' '.join(rec.get('keywords',[]))}"
            tokens = _tokenize(doc_text)
            self._docs.append(tokens)
            for t in set(tokens):
                self._df[t] = self._df.get(t, 0) + 1
        self._N = len(self._records)
        total_len = sum(len(d) for d in self._docs)
        self._avgdl = total_len / max(self._N, 1)
        self._compute_idf()
