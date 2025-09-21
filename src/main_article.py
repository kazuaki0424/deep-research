# src/main_article.py
from __future__ import annotations
import os, sys, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict

from research import Researcher
from analyze_claude import DeepAnalyzer

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "public"))
LANG = os.getenv("LANGUAGE", "ja-JP")
TOPICS_FILE = Path("topics.yaml")

def now_jst():
    return datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=9)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def load_topics() -> List[str]:
    import yaml
    if not TOPICS_FILE.exists():
        return ["テクノロジー総覧"]
    with TOPICS_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    topics = data.get("topics") or data
    return [str(t) for t in topics] if isinstance(topics, list) else ["テクノロジー総覧"]

def pick_today_topic(topics: List[str]) -> str:
    if not topics: return "テクノロジー総覧"
    return topics[now_jst().weekday() % len(topics)]

def write_markdown(markdown: str, theme: str) -> Path:
    articles = OUTPUT_DIR / "articles"
    ensure_dir(articles)
    date_str = now_jst().strftime("%Y-%m-%d")
    safe = "".join(ch for ch in theme if ch.isalnum() or ch in "-_")
    path = articles / f"{date_str}-{safe or 'topic'}.md"
    path.write_text(markdown, encoding="utf-8")
    print(f"[ok] wrote: {path}")
    return path

def debug_dump(obj, title="debug"):
    try:
        print(f"[{title}] {json.dumps(obj, ensure_ascii=False)[:1200]}")
    except Exception:
        print(f"[{title}] <non-serializable>")

def main():
    print("[info] start main_article")
    ensure_dir(OUTPUT_DIR / "articles")

    # --- pick topic ---
    topics = load_topics()
    theme = pick_today_topic(topics)
    print(f"[info] theme = {theme}")

    # --- collect sources via Tavily ---
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        print("[error] TAVILY_API_KEY missing", file=sys.stderr)
        md = f"# {theme}\n\nTavilyのAPIキーが設定されていません。Settings → Secrets → Actions に `TAVILY_API_KEY` を追加してください。"
        write_markdown(md, theme); return

    researcher = Researcher(tavily_api_key=tavily_key)
    try:
        docs: List[Dict] = researcher.collect(theme, max_results=8)
        if not docs:
            print("[warn] docs empty; retry with expanded query")
            docs = researcher.collect(f"{theme} 最新 動向 企業 規制", max_results=8)
        debug_dump([{"title": d.get("title"), "url": d.get("url")} for d in docs], "sources")
    except Exception as e:
        print(f"[error] tavily/research failed: {e}", file=sys.stderr)
        docs = []

    # --- deep analysis via Claude (haiku既定にしておいてください) ---
    try:
        analyzer = DeepAnalyzer()  # analyze_claude.py で model="claude-3-haiku-20240307"
        md: str = analyzer.analyze(theme, docs)
        if not md or len(md.strip()) < 100:
            md = f"# {theme}\n\n生成が空/短すぎです。キーやモデル権限をご確認ください。"
    except Exception as e:
        md = f"# {theme}\n\n分析中に例外: {e}"

    write_markdown(md, theme)

    # 初回 404 回避用 index
    idx = (OUTPUT_DIR / "articles" / "index.html")
    if not idx.exists():
        idx.write_text(
            "<!doctype html><meta charset='utf-8'><title>Articles</title>"
            "<h1>Articles</h1><p>最新記事はこのディレクトリの .md を開いてください。</p>",
            encoding="utf-8"
        )
        print(f"[ok] wrote: {idx}")

    print("[info] done main_article")

if __name__ == "__main__":
    main()
