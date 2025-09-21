# src/research.py
from __future__ import annotations
import os, time, math, requests
from typing import List, Dict, Iterable, Tuple
from tavily import TavilyClient
import trafilatura
from urllib.parse import urlparse
from datetime import datetime, timezone

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

# 品質ブースト（代表的な信頼メディア/一次情報源）
PREFERRED_DOMAINS = {
    # ビジネス/テック主要
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com", "economist.com",
    "nytimes.com", "washingtonpost.com", "cnbc.com", "forbes.com", "seekingalpha.com",
    "techcrunch.com", "theverge.com", "wired.com", "arstechnica.com",
    # 研究・規制・一次資料
    "arxiv.org", "nature.com", "science.org", "acm.org", "ieee.org",
    "ec.europa.eu", "whitehouse.gov", "congress.gov", "house.gov", "senate.gov",
    "federalregister.gov", "fti.org", "bis.doc.gov",
    # 企業一次情報
    "prnewswire.com", "businesswire.com", "investor.*", "ir.*",
}

# 除外（まとめ系/重複製/信頼性が低いものを例示。必要に応じて調整）
BLOCKED_DOMAINS = {
    "githubusercontent.com", "medium.com/@", "youtube.com", "x.com", "twitter.com",
    "reddit.com", "substack.com", "quora.com", "facebook.com", "tiktok.com",
}

FORCED_TERMS = [
    "最新", "動向", "規制", "投資", "資金調達", "提携", "買収", "採用", "ロードマップ",
    "価格", "性能", "ベンチマーク", "導入事例", "PoC", "セキュリティ", "大手企業",
]

class Researcher:
    def __init__(self, tavily_api_key: str):
        self.client = TavilyClient(api_key=tavily_api_key)

    # ---------- 検索クエリ構築 ----------
    def _build_queries(self, theme: str, weekend: bool = False) -> List[str]:
        """
        週末は技術フォーカスを想定し、より技術寄り語を強める。
        複数クエリを走らせ、結果をマージして重複排除・リランキングする。
        """
        base = theme.strip()
        join = " ".join(FORCED_TERMS)
        queries = [
            f"{base} {join}",
            f"{base} 企業 発表 プレスリリース 投資家向け情報 IR 提携",
            f"{base} 規制 政策 ガイドライン 標準化 標準規格",
            f"{base} 価格 性能 ベンチマーク 評価 比較",
        ]
        if weekend:
            queries.append(f"{base} アーキテクチャ 実装 研究 論文 arXiv ベストプラクティス")
        return queries

    # ---------- Tavily検索 ----------
    def search(self, query: str, max_results: int = 12) -> List[Dict]:
        """
        Tavilyの基本検索。回答生成や生本文は不要なのでFalse。
        """
        res = self.client.search(
            query=query,
            max_results=max_results,
            include_answer=False,
            include_raw_content=False
        )
        return res.get("results", [])

    # ---------- 本文抽出 ----------
    def fetch_clean(self, url: str, timeout: int = 25) -> str:
        """
        trafilaturaで本文抽出。事前にHEAD/GETで到達性を確認し、空なら空文字を返す。
        """
        try:
            # 軽い到達性確認
            requests.get(url, timeout=timeout, headers={"User-Agent": UA})
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                text = trafilatura.extract(
                    downloaded,
                    include_tables=False,
                    favor_recall=True
                )
                if text:
                    return text
        except Exception:
            pass
        return ""

    # ---------- ドメイン判定 ----------
    @staticmethod
    def _domain_of(u: str) -> str:
        try:
            n = urlparse(u).netloc.lower()
            return n
        except Exception:
            return ""

    @staticmethod
    def _is_blocked(domain: str) -> bool:
        if not domain:
            return True
        if domain in BLOCKED_DOMAINS:
            return True
        for pat in BLOCKED_DOMAINS:
            if pat in domain:
                return True
        return False

    @staticmethod
    def _is_preferred(domain: str) -> bool:
        for pat in PREFERRED_DOMAINS:
            if pat == domain or pat in domain:
                return True
        return False

    # ---------- リランキング ----------
    def _score_result(self, item: Dict) -> float:
        """
        簡易スコアリング:
        - ドメイン品質（preferred:+1.0）
        - 直近性（published_dateがあれば減衰）
        - タイトル長・要語含有の軽い加点
        """
        url = item.get("url", "") or ""
        title = (item.get("title", "") or "").lower()
        domain = self._domain_of(url)
        score = 0.0
        if self._is_preferred(domain):
            score += 1.0
        # 直近性（published_dateがISOで来る場合に限り）
        dt_str = item.get("published_date")
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str.replace("Z","+00:00"))
                age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds()/86400.0)
                score += max(0.0, 0.8 * math.exp(-age_days/60.0))  # ~2ヶ月でほぼ減衰
            except Exception:
                pass
        # 用語ヒット
        for kw in ["regulation","規制","investment","投資","acquisition","買収","partnership","提携","benchmark","ベンチマーク","roadmap","ロードマップ","hiring","採用"]:
            if kw in title:
                score += 0.1
        # タイトルの情報量
        if len(title) >= 25:
            score += 0.1
        return score

    # ---------- 検索統合 ----------
    def _merge_dedup(self, result_lists: List[List[Dict]], per_domain_cap: int = 3) -> List[Dict]:
        seen_urls, merged = set(), []
        domain_counts: Dict[str, int] = {}
        # まとめて平坦化
        flat: List[Dict] = [r for lst in result_lists for r in lst if isinstance(lst, list)]
        # スコア算出
        scored = []
        for it in flat:
            url = it.get("url")
            if not url or url in seen_urls:
                continue
            domain = self._domain_of(url)
            if self._is_blocked(domain):
                continue
            s = self._score_result(it)
            scored.append((s, it, domain))
            seen_urls.add(url)
        # スコア順に並べ、ドメイン上限で間引く
        for s, it, domain in sorted(scored, key=lambda x: x[0], reverse=True):
            cnt = domain_counts.get(domain, 0)
            if cnt >= per_domain_cap:
                continue
            merged.append(it)
            domain_counts[domain] = cnt + 1
        return merged

    # ---------- 収集メイン ----------
    def collect(self, query: str, max_results: int = 12, weekend: bool = False) -> List[Dict]:
        """
        - クエリを複数生成してTavily検索
        - 統合・重複排除・品質ブースト
        - 各URLの本文を抽出（空は除外）
        """
        queries = self._build_queries(query, weekend=weekend)
        all_results: List[List[Dict]] = []
        for q in queries:
            try:
                res = self.search(q, max_results=max_results)
                all_results.append(res)
                time.sleep(0.3)
            except Exception:
                continue

        merged = self._merge_dedup(all_results, per_domain_cap=3)

        bundle: List[Dict] = []
        for h in merged:
            url = h.get("url"); title = h.get("title", "")
            if not url:
                continue
            text = self.fetch_clean(url)
            if not text:
                continue
            bundle.append({
                "title": title,
                "url": url,
                "content": text[:14000],
                "published_date": h.get("published_date")
            })
            # 過負荷回避
            time.sleep(0.5)

        # 上位だけ返す
        return bundle[:max_results]
