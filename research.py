from __future__ import annotations
import os, time, requests
from typing import List, Dict
from tavily import TavilyClient
import trafilatura

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

class Researcher:
    def __init__(self, tavily_api_key: str):
        self.client = TavilyClient(api_key=tavily_api_key)

    def search(self, query: str, max_results: int = 12) -> List[Dict]:
        res = self.client.search(query=query, max_results=max_results, include_answer=False, include_raw_content=False)
        return res.get("results", [])

    def fetch_clean(self, url: str, timeout: int = 25) -> str:
        try:
            requests.get(url, timeout=timeout, headers={"User-Agent": UA})
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(downloaded, include_tables=False)
                if text:
                    return text
        except Exception:
            pass
        return ""

    def collect(self, query: str, max_results: int = 12) -> List[Dict]:
        hits = self.search(query, max_results=max_results)
        bundle = []
        for h in hits:
            url = h.get("url"); title = h.get("title", "")
            if not url: 
                continue
            text = self.fetch_clean(url)
            if not text: 
                continue
            bundle.append({"title": title, "url": url, "content": text[:14000]})
            time.sleep(0.5)
        return bundle
