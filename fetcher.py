import requests
import trafilatura


def fetch_html(url: str) -> str:
    r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0 (lrt-digest)"})
    r.raise_for_status()
    r.encoding = r.apparent_encoding or "utf-8"
    return r.text


def extract_text(article_html: str) -> str:
    text = trafilatura.extract(article_html, include_comments=False, include_tables=False)
    return (text or "").strip()

