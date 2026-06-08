"""Wikipedia search tool — fetches article summaries via the REST API."""
import json
import urllib.parse
import urllib.request


class WikipediaSearchTool:
    name = "wikipedia_search"
    description = "Search Wikipedia for an article summary. Returns title, page_id, and extract."
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search term, e.g. 'Albert Einstein'."},
            "language": {"type": "string", "description": "Language code, default 'zh'.", "default": "zh"},
        },
        "required": ["query"],
    }

    _UA = "AI-Agent-Framework/1.0"

    def run(self, query: str, language: str = "zh") -> str:
        try:
            return self._fetch(query.strip(), language)
        except Exception as exc:
            return json.dumps({"error": f"Wikipedia request failed: {exc}"}, ensure_ascii=False)

    def _fetch(self, query: str, lang: str) -> str:
        # Search for best title match
        search_url = (
            f"https://{lang}.wikipedia.org/w/api.php"
            f"?action=query&list=search&srsearch={urllib.parse.quote(query)}"
            f"&format=json&srlimit=1"
        )
        sr = self._get(search_url)
        results = sr.get("query", {}).get("search", [])
        if not results:
            return json.dumps({"error": f"No article found for '{query}'."}, ensure_ascii=False)

        title, page_id = results[0]["title"], results[0]["pageid"]

        # Fetch extract
        ext_url = (
            f"https://{lang}.wikipedia.org/w/api.php"
            f"?action=query&prop=extracts&exintro&explaintext"
            f"&pageids={page_id}&format=json"
        )
        er = self._get(ext_url)
        pages = er.get("query", {}).get("pages", {})
        extract = pages.get(str(page_id), {}).get("extract", "")
        if len(extract) > 1200:
            extract = extract[:1200] + "…"

        return json.dumps({"title": title, "page_id": page_id, "extract": extract}, ensure_ascii=False)

    @staticmethod
    def _get(url: str) -> dict:
        req = urllib.request.Request(url)
        req.add_header("User-Agent", WikipediaSearchTool._UA)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
