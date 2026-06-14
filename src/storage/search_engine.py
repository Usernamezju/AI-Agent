"""BM25 search engine with optional AI re-ranking — zero external dependencies."""
from __future__ import annotations
import json
import math
import re

# ═══════════════════════════════════════════════════════════════════════
# Stopwords
# ═══════════════════════════════════════════════════════════════════════

STOPWORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人",
    "都", "一", "一个", "上", "也", "很", "到", "说", "要", "去",
    "你", "会", "着", "没有", "看", "好", "自己", "这", "那", "他",
    "她", "它", "们", "对", "用", "做", "来", "能", "可以", "还",
    "但", "与", "或", "被", "让", "从", "把", "给", "向", "以",
    "及", "没", "出", "如", "如果", "所以", "因为", "然后", "只是",
    "怎么", "什么", "哪里", "哪个", "怎样", "多少", "吗", "呢", "吧",
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "can", "shall",
    "i", "you", "he", "she", "it", "we", "they", "me", "him",
    "her", "us", "them", "my", "your", "his", "its", "our",
    "their", "this", "that", "these", "those", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "as", "into",
    "through", "during", "before", "after", "above", "below",
    "between", "and", "but", "or", "not", "no", "so", "if",
    "then", "than", "too", "very", "just", "about", "also",
}

# ═══════════════════════════════════════════════════════════════════════
# Tokenizer
# ═══════════════════════════════════════════════════════════════════════


def tokenize(text: str) -> list[str]:
    """Chinese + English mixed tokenizer (zero-dependency).

    Chinese: unigram (single chars) + bigram (adjacent pairs).
    English: whole words matching ``[a-z]+``.
    Both are filtered against `STOPWORDS`.
    """
    text = text.lower()
    tokens: list[str] = []

    # Chinese characters
    cjk_chars: list[str] = []
    cjk_pattern = re.compile(r"[一-鿿]")
    for ch in text:
        if cjk_pattern.match(ch) and ch not in STOPWORDS:
            cjk_chars.append(ch)
            tokens.append(ch)  # unigram

    # bigram
    for i in range(len(cjk_chars) - 1):
        bigram = cjk_chars[i] + cjk_chars[i + 1]
        if bigram not in STOPWORDS:
            tokens.append(bigram)

    # English words
    for m in re.finditer(r"[a-z]+", text):
        word = m.group()
        if word not in STOPWORDS and len(word) > 1:
            tokens.append(word)

    return tokens


# ═══════════════════════════════════════════════════════════════════════
# BM25
# ═══════════════════════════════════════════════════════════════════════


class BM25:
    """Pure-Python BM25 implementation.

    Parameters
    ----------
    k1 : float
        Term saturation parameter (default 1.5).
    b : float
        Length normalisation parameter (default 0.75).
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self._docs: list[dict] = []    # {"id":..., "title":..., "text":...}
        self._tf: list[dict] = []      # per-doc term-frequency Counter
        self._df: dict[str, int] = {}  # document frequency
        self._idf: dict[str, float] = {}
        self._avgdl: float = 0.0
        self._N: int = 0

    # ------------------------------------------------------------------
    def index(self, documents: list[dict]) -> None:
        """Build / rebuild the BM25 index from *documents*."""
        self._docs = []
        self._tf = []
        self._df = {}
        total_len = 0

        for doc in documents:
            text = self._make_text(doc)
            tokens = tokenize(text)
            tf = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self._docs.append({"id": doc["id"], "title": doc.get("title", ""), "text": text})
            self._tf.append(tf)
            for t in set(tf):
                self._df[t] = self._df.get(t, 0) + 1
            total_len += len(tokens)

        self._N = len(documents)
        self._avgdl = total_len / max(self._N, 1)
        self._compute_idf()

    def _compute_idf(self) -> None:
        self._idf = {}
        for term, df in self._df.items():
            # IDF = log((N - df + 0.5) / (df + 0.5) + 1)
            self._idf[term] = math.log((self._N - df + 0.5) / (df + 0.5) + 1.0)

    # ------------------------------------------------------------------
    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Return top-k results as ``[{id, title, score, snippet}, ...]``."""
        if self._N == 0:
            return []

        query_tokens = tokenize(query)
        if not query_tokens:
            return []

        scores: list[tuple[int, float]] = []  # (doc_index, score)

        for i, tf in enumerate(self._tf):
            dl = sum(tf.values())
            if dl == 0:
                continue
            score = 0.0
            for t in query_tokens:
                idf = self._idf.get(t, 0.0)
                if idf == 0.0:
                    continue
                f = tf.get(t, 0)
                numerator = f * (self.k1 + 1.0)
                denominator = f + self.k1 * (1.0 - self.b + self.b * dl / self._avgdl)
                score += idf * (numerator / denominator)
            if score > 0:
                scores.append((i, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        results: list[dict] = []
        for idx, score in scores[:top_k]:
            doc = self._docs[idx]
            results.append({
                "id": doc["id"],
                "title": doc["title"],
                "score": round(score, 4),
                "snippet": self._make_snippet(doc["text"], query_tokens),
            })
        return results

    # ------------------------------------------------------------------
    def add_document(self, doc: dict) -> None:
        """Incrementally index a single document (no full rebuild)."""
        text = self._make_text(doc)
        tokens = tokenize(text)
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1

        self._docs.append({"id": doc["id"], "title": doc.get("title", ""), "text": text})
        self._tf.append(tf)

        new_terms = set(tf)
        for t in new_terms:
            self._df[t] = self._df.get(t, 0) + 1

        self._N = len(self._docs)
        total_len = sum(len(t) for t in self._tf)  # sum of all token counts
        # Actually we need total_len across all docs — recompute quickly
        total_len = sum(sum(t.values()) for t in self._tf)
        self._avgdl = total_len / max(self._N, 1)
        self._compute_idf()

    # ------------------------------------------------------------------
    def _make_snippet(self, text: str, query_tokens: list[str]) -> str:
        """Extract a context window around the first query-token match."""
        lower = text.lower()
        best_pos = len(text)
        for t in query_tokens:
            pos = lower.find(t)
            if pos != -1 and pos < best_pos:
                best_pos = pos
        if best_pos >= len(text):
            return text[:120]
        start = max(0, best_pos - 60)
        end = min(len(text), best_pos + 60)
        snippet = text[start:end]
        if start > 0:
            snippet = "…" + snippet
        if end < len(text):
            snippet += "…"
        return snippet

    @staticmethod
    def _make_text(doc: dict) -> str:
        return doc.get("text", "")


# ═══════════════════════════════════════════════════════════════════════
# AI Re-ranker
# ═══════════════════════════════════════════════════════════════════════


class AIReranker:
    """LLM-based re-ranker that picks the most relevant results from BM25 candidates."""

    def __init__(self, llm_client) -> None:
        self._llm = llm_client

    def rerank(self, query: str, candidates: list[dict], top_k: int = 3) -> list[dict]:
        """Re-rank up to 10 candidates, returning the top *top_k*."""
        if len(candidates) <= top_k:
            return candidates

        pool = candidates[:10]
        lines: list[str] = []
        for i, c in enumerate(pool):
            lines.append(f"[{i + 1}] id={c['id']}  标题：{c.get('title','')}  片段：{c.get('snippet','')}")

        prompt = (
            f"用户搜索：{query}\n\n"
            "以下是候选对话（id 和摘要）：\n"
            + "\n".join(lines) + "\n\n"
            f"请从中选出与搜索词最相关的最多 {top_k} 条，\n"
            "按相关性从高到低输出 id 列表，格式为 JSON 数组：[\"id1\",\"id2\"]\n"
            "若都不相关，返回 []。\n"
            "只返回 JSON，不要其他文字。"
        )

        messages = [{"role": "user", "content": prompt}]
        try:
            raw = self._llm.chat(messages, temperature=0, max_tokens=300)
            ids = json.loads(raw.strip())
            if isinstance(ids, list):
                id_to_candidate = {c["id"]: c for c in pool}
                reranked = [id_to_candidate[cid] for cid in ids if cid in id_to_candidate]
                return reranked[:top_k] if reranked else candidates[:top_k]
        except Exception:
            pass
        return candidates[:top_k]


# ═══════════════════════════════════════════════════════════════════════
# SearchEngine facade
# ═══════════════════════════════════════════════════════════════════════


class SearchEngine:
    """Top-level search API that combines BM25 + optional AI re-ranking."""

    def __init__(self, store, llm_client=None) -> None:
        self._store = store
        self._bm25 = BM25()
        self._reranker = AIReranker(llm_client) if llm_client else None
        self._indexed = False

    # ------------------------------------------------------------------
    def rebuild_index(self) -> int:
        """Full index rebuild from all stored conversations. Returns doc count."""
        docs = self._make_docs(self._store.get_all_for_search())
        self._bm25.index(docs)
        self._indexed = True
        return len(docs)

    def add_to_index(self, conv_id: str) -> None:
        """Incrementally index a single conversation by id."""
        conv = self._store.get_conversation(conv_id)
        if not conv:
            return
        doc = self._make_docs([conv])[0] if self._make_docs([conv]) else None
        if doc:
            self._bm25.add_document(doc)
            self._indexed = True

    def search(self, query: str, use_ai: bool = False, top_k: int = 5) -> list[dict]:
        """Search conversations. Auto-builds index on first call."""
        if not self._indexed:
            self.rebuild_index()

        candidates = self._bm25.search(query, top_k=top_k * 2)

        if use_ai and self._reranker and len(candidates) > top_k:
            return self._reranker.rerank(query, candidates, top_k=top_k)

        return candidates[:top_k]

    # ------------------------------------------------------------------
    @staticmethod
    def _make_docs(convs: list[dict]) -> list[dict]:
        """Convert conversation dicts to searchable documents."""
        docs: list[dict] = []
        for conv in convs:
            messages = conv.get("messages", [])
            lines: list[str] = []
            for m in messages:
                role = m.get("role", "")
                content = m.get("content", "")
                if role == "user":
                    lines.append(f"用户：{content}")
                elif role == "assistant":
                    lines.append(f"助手：{content}")
            docs.append({
                "id": conv.get("id", ""),
                "title": conv.get("title", ""),
                "text": "\n".join(lines),
            })
        return docs
