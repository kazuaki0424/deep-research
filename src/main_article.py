# src/main_article.py
from __future__ import annotations
import os
import sys
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict

from research import tavily_search  # 既存の research.py にある想定（なければ後述の代替実装を使ってください）
from analyze_claude import DeepAnalyzer

# ---- 設定値の読み取り（環境変数 .env から） ----
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "public"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Tokyo")
LANG = os.getenv("LANGUAGE", "ja-JP")

TOPICS_FILE = Path("topics.yaml")

def now_jst():
    # ざっくりJST固定（タイムゾーン文字列の厳密処理は省略）
    return datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=9)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def load_topics() -> List[str]:
    import yaml
    if not TOPICS_FILE.exists():
        print(f"[warn] topics.yaml が見つかりませんでした: {TOPICS_FILE.resolve()}", file=sys.stderr)
        return ["テクノロジー総覧"]
    with TOPICS_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    topics = data.get("topics") or data  # どちらの書式でもOKに
    if isinstance(topics, list):
        return [str(t) for t in topics if t]
    return ["テクノロジー総覧"]

def pick_today_topic(topics: List[str]) -> str:
    # 日替わりローテーション（曜日で決定）
    if not topics:
        return "テクノロジー総覧"
    idx = now_jst().weekday() % len(topics)
    return topics[idx]

def write_markdown(markdown: str, theme: str) -> Path:
    articles_dir = OUTPUT_DIR / "articles"
    ensure_dir(articles_dir)
    date_str = now_jst().strftime("%Y-%m-%d")
    safe_theme = "".join(ch for ch in theme if ch.isalnum() or ch in ("-", "_")).strip() or "topic"
    out_path = articles_dir / f"{date_str}-{safe_theme}.md"
    out_path.write_text(markdown, encoding="utf-8")
    print(f"[ok] wrote: {out_path}")
    return out_path

def debug_dump(obj, title="debug"):
    try:
        print(f"[{title}] {json.dumps(obj, ensure_ascii=False)[:1000]}")
    except Exception:
        print(f"[{title}] <non-serializable>")

def main():
    print("[info] start main_article")
    ensure_dir(OUTPUT_DIR / "articles")

    topics = load_topics()
    theme = pick_today_topic(topics)
    print(f"[info] theme = {theme}")

    # ---- ニュース収集（Tavily） ----
    try:
        docs: List[Dict] = tavily_search(theme, max_results=8, lang=LANG)
        if not docs:
            print("[warn] tavily_search が空でした。fallback: キーワードを拡張して再試行")
            docs = tavily_search(f"{theme} 最新 動向 企業 規制", max_
