"""Web search + fetch tools — DuckDuckGo (no API key) + direct URL fetching."""
from __future__ import annotations
import json
import re
import urllib.parse
import urllib.request


class WebSearchTool:
    """Search the web via DuckDuckGo Lite (free, no API key required).

    Returns titles, snippets, and URLs for up to 10 results.
    """

    name = "web_search"
    description = (
        "Search the web using DuckDuckGo. "
        "Use for current events, facts not in Wikipedia, recent news, "
        "prices, documentation, or any information beyond the model's knowledge cutoff. "
        "Returns up to 10 results with title, snippet, and URL."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search keywords, e.g. 'Python 3.13 release notes'.",
            },
            "max_results": {
                "type": "integer",
                "description": "Max results (default 5, max 10).",
            },
        },
        "required": ["query"],
    }

    _UA = "AI-Agent-Framework/1.0"

    def run(self, query: str, max_results: int = 5) -> str:
        max_results = min(int(max_results), 10)
        try:
            results = self._search(query.strip(), max_results)
            if not results:
                return json.dumps({"query": query, "results": [],
                                   "hint": "No results. Try broader keywords."},
                                  ensure_ascii=False)
            return json.dumps({"query": query, "results": results},
                              ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Search failed: {exc}"}, ensure_ascii=False)

    def _search(self, query: str, n: int) -> list[dict]:
        url = (
            "https://lite.duckduckgo.com/lite/?"
            + urllib.parse.urlencode({"q": query})
        )
        req = urllib.request.Request(url)
        req.add_header("User-Agent", self._UA)
        req.add_header("Accept", "text/html")

        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        return self._parse(html, n)

    @staticmethod
    def _parse(html: str, n: int) -> list[dict]:
        results: list[dict] = []
        # DuckDuckGo Lite results are in <a> tags with class "result-link"
        # Title is the link text, snippet is in <td class="result-snippet">
        links = re.findall(
            r'<a[^>]*class="result-link"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>',
            html)
        snippets = re.findall(
            r'<td class="result-snippet"[^>]*>([^<]*(?:<[^/][^>]*>[^<]*</[^>]*>)*[^<]*)</td>',
            html)

        for i, (url, title) in enumerate(links):
            if i >= n:
                break
            snippet = ""
            if i < len(snippets):
                snippet = re.sub(r"<[^>]+>", "", snippets[i]).strip()
            results.append({
                "title": title.strip(),
                "url": url.strip(),
                "snippet": snippet[:300],
            })
        return results


class WebFetchTool:
    """Fetch a web page and return its text content."""

    name = "web_fetch"
    description = (
        "Fetch the text content of a web page by URL. "
        "Use after web_search to read full article/detail pages. "
        "Strips HTML tags and returns plain text. Max ~8000 chars."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL to fetch, e.g. 'https://example.com/article'.",
            },
        },
        "required": ["url"],
    }

    _UA = "AI-Agent-Framework/1.0"

    def run(self, url: str) -> str:
        try:
            text = self._fetch(url.strip())
            return json.dumps({"url": url, "content": text[:8000]},
                              ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"error": f"Fetch failed: {exc}"}, ensure_ascii=False)

    def _fetch(self, url: str) -> str:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", self._UA)
        req.add_header("Accept", "text/html")
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        return self._extract_text(html)

    @staticmethod
    def _extract_text(html: str) -> str:
        # Remove scripts, styles, head
        html = re.sub(r"<(script|style|head|nav|footer)[^>]*>.*?</\1>",
                      "", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<[^>]+>", " ", html)
        html = re.sub(r"\s+", " ", html)
        return html.strip()
