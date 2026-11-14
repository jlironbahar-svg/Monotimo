"""Web search: open the user's browser and fetch a short spoken summary.

The summary uses Groq's Compound models (built-in web search). If that is not available,
it falls back to scraping DuckDuckGo's lightweight HTML results page.
"""

from __future__ import annotations

import html
import logging
import re

import httpx

from .groq_client import GroqClient, GroqError

log = logging.getLogger(__name__)

_RESULT_RE = re.compile(
    r'class="result__a"[^>]*>(?P<title>.*?)</a>.*?class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
    re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(_TAG_RE.sub("", s))).strip()


def parse_ddg_html(page: str, limit: int = 4) -> list[tuple[str, str]]:
    out = []
    for m in _RESULT_RE.finditer(page):
        title, snippet = _strip(m.group("title")), _strip(m.group("snippet"))
        if title:
            out.append((title, snippet))
        if len(out) >= limit:
            break
    return out


class WebSearcher:
    def __init__(self, groq: GroqClient, model_getter):
        self.groq = groq
        self._model = model_getter

    async def summarize(self, query: str) -> str:
        if self.groq.configured:
            try:
                msg = await self.groq.chat(
                    self._model(),
                    [
                        {
                            "role": "system",
                            "content": "Search the web and answer in at most 3 short plain sentences. No markdown, no URLs.",
                        },
                        {"role": "user", "content": query},
                    ],
                    temperature=0.3,
                    max_tokens=400,
                )
                text = (msg.get("content") or "").strip()
                if text:
                    return text
            except GroqError as exc:
                log.info("Groq compound search failed (%s); falling back to DuckDuckGo", exc)
        return await self._duckduckgo(query)

    async def _duckduckgo(self, query: str) -> str:
        try:
            async with httpx.AsyncClient(timeout=12, headers={"User-Agent": "Mozilla/5.0 (DesktopFriend)"}) as http:
                resp = await http.post("https://html.duckduckgo.com/html/", data={"q": query})
            results = parse_ddg_html(resp.text)
        except httpx.HTTPError as exc:
            log.info("DuckDuckGo fallback failed: %s", exc)
            results = []
        if not results:
            return "I opened the search in your browser, but couldn't read the results myself."
        return " | ".join(f"{t}: {s}" if s else t for t, s in results)
