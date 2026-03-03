"""
JARVIS-OS Plugin: Web Search
Search the web and extract content from pages.
Uses DuckDuckGo for search and httpx for page fetching with HTML-to-text extraction.
"""

import logging
import re

logger = logging.getLogger("jarvis.plugin.web_search")

PLUGIN_INFO = {
    "name": "Web Search",
    "version": "2.0.0",
    "description": "Search the web and extract page content for research tasks",
    "author": "JARVIS-OS",
    "capabilities": ["web_search", "url_fetch", "content_extraction"],
}


def get_tools():
    return [
        {
            "name": "web_search",
            "description": "Search the web using DuckDuckGo for real-time information. Returns titles, URLs, and snippets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The search query"},
                    "max_results": {"type": "integer", "description": "Max results to return (default 5)"},
                },
                "required": ["query"],
            },
        },
        {
            "name": "fetch_url",
            "description": "Fetch a web page and extract its text content. Good for reading articles, docs, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The URL to fetch"},
                },
                "required": ["url"],
            },
        },
    ]


async def execute(tool_name: str, arguments: dict, context: dict) -> dict:
    if tool_name == "web_search":
        return await _web_search(arguments.get("query", ""), arguments.get("max_results", 5))
    elif tool_name == "fetch_url":
        return await _fetch_url(arguments.get("url", ""))
    return {"error": f"Unknown tool: {tool_name}"}


async def _web_search(query: str, max_results: int = 5) -> dict:
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.get(
                "https://html.duckduckgo.com/html/",
                params={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )
            text = response.text
            results = []

            links = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)">(.+?)</a>', text)
            snippets = re.findall(r'<a class="result__snippet"[^>]*>(.+?)</a>', text)

            for i, (url, title) in enumerate(links[:max_results]):
                result = {
                    "title": re.sub(r'<[^>]+>', '', title).strip(),
                    "url": url,
                    "snippet": re.sub(r'<[^>]+>', '', snippets[i]).strip() if i < len(snippets) else "",
                }
                results.append(result)

            if not results:
                return {"status": "success", "results": [], "query": query, "message": "No results found"}

            return {"status": "success", "results": results, "query": query}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _html_to_text(html: str) -> str:
    """Extract readable text from HTML, stripping tags and scripts."""
    # Remove script and style elements
    html = re.sub(r'<script[^>]*>[\s\S]*?</script>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<style[^>]*>[\s\S]*?</style>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<nav[^>]*>[\s\S]*?</nav>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<footer[^>]*>[\s\S]*?</footer>', '', html, flags=re.IGNORECASE)
    html = re.sub(r'<header[^>]*>[\s\S]*?</header>', '', html, flags=re.IGNORECASE)

    # Convert common elements to text equivalents
    html = re.sub(r'<br\s*/?>', '\n', html)
    html = re.sub(r'</?p[^>]*>', '\n', html)
    html = re.sub(r'</?div[^>]*>', '\n', html)
    html = re.sub(r'</?h[1-6][^>]*>', '\n', html)
    html = re.sub(r'<li[^>]*>', '\n- ', html)
    html = re.sub(r'</?(?:ul|ol)[^>]*>', '\n', html)

    # Remove remaining tags
    text = re.sub(r'<[^>]+>', '', html)

    # Decode HTML entities
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&quot;', '"').replace('&#39;', "'").replace('&nbsp;', ' ')

    # Clean up whitespace
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]

    result = []
    prev_empty = False
    for line in lines:
        if not line:
            if not prev_empty:
                result.append('')
                prev_empty = True
        else:
            result.append(line)
            prev_empty = False

    return '\n'.join(result)


async def _fetch_url(url: str) -> dict:
    try:
        import httpx
        async with httpx.AsyncClient(
            timeout=20,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=5),
        ) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            )

            content_type = response.headers.get("content-type", "")

            if "text/html" in content_type:
                text = _html_to_text(response.text)
            else:
                text = response.text

            # Truncate to reasonable size
            if len(text) > 15000:
                text = text[:15000] + "\n\n... [content truncated — page too long]"

            return {
                "status": "success",
                "url": str(response.url),
                "status_code": response.status_code,
                "content": text,
                "content_type": content_type,
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


async def on_load(kernel):
    logger.info("Web Search plugin loaded (v2.0 with content extraction)")


async def on_unload():
    logger.info("Web Search plugin unloaded")
