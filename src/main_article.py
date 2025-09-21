# src/main_article.py
from __future__ import annotations
import os, sys, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict

# src パッケージ内のモジュールを相対インポート
from .research import Researcher
from .analyze_claude import DeepAnalyzer

# ===== 基本設定（.env から上書き可） =====
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "public"))
LANG = os.getenv("LANGUAGE", "ja-JP")
TOPICS_FILE = Path("topics.yaml")
TIMEZONE_HOURS = 9  # JST

# ===== ユーティリティ =====
def now_local():
    return datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=TIMEZONE_HOURS)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def load_topics() -> List[str]:
    """topics.yaml は下記どちらでもOK:
    - リスト形式: [AI, フィンテック, ...]
    - マップ形式: { topics: [AI, ...] }
    """
    import yaml
    if not TOPICS_FILE.exists():
        print(f"[warn] topics.yaml not found. fallback to default topic", file=sys.stderr)
        return ["テクノロジー総覧"]
    with TOPICS_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    topics = data.get("topics") if isinstance(data, dict) else data
    if not isinstance(topics, list) or not topics:
        return ["テクノロジー総覧"]
    return [str(t) for t in topics if t]

def pick_today_topic(topics: List[str]) -> str:
    if not topics:
        return "テクノロジー総覧"
    return topics[now_local().weekday() % len(topics)]

def safe_slug(s: str) -> str:
    return "".join(ch for ch in s if ch.isalnum() or ch in "-_").strip() or "topic"

def write_markdown(markdown: str, theme: str) -> Path:
    articles_dir = OUTPUT_DIR / "articles"
    ensure_dir(articles_dir)
    date_str = now_local().strftime("%Y-%m-%d")
    path = articles_dir / f"{date_str}-{safe_slug(theme)}.md"
    path.write_text(markdown, encoding="utf-8")
    print(f"[ok] wrote markdown: {path}")
    return path

def ensure_articles_index():
    idx = OUTPUT_DIR / "articles" / "index.html"
    if not idx.exists():
        idx.write_text(
            "<!doctype html><meta charset='utf-8'>"
            "<title>Articles</title><h1>Articles</h1>"
            "<p>このディレクトリの .md ファイルが記事です。</p>",
            encoding="utf-8",
        )
        print(f"[ok] wrote index: {idx}")

def debug_dump(obj, title="debug"):
    try:
        print(f"[{title}] {json.dumps(obj, ensure_ascii=False)[:1200]}")
    except Exception:
        print(f"[{title}] <non-serializable>")

# ===== メイン処理 =====
def main():
    print("[info] start main_article")
    ensure_dir(OUTPUT_DIR / "articles")
    ensure_articles_index()

    # 1) トピック決定
    topics = load_topics()
    theme = pick_today_topic(topics)
    print(f"[info] theme = {theme}")

    # 2) 資料収集（Tavily）
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        print("[error] TAVILY_API_KEY is missing. Set it in Settings → Secrets → Actions.", file=sys.stderr)
        md = f"# {theme}\n\nTavily の API キーが未設定です。`TAVILY_API_KEY` を Actions Secrets に登録してください。"
        write_markdown(md, theme)
        print("[info] done main_article (no tavily key)")
        return

    researcher = Researcher(tavily_api_key=tavily_key)
    try:
        print("[info] collecting sources via Tavily ...")
        docs: List[Dict] = researcher.collect(theme, max_results=8)
        if not docs:
            print("[warn] docs empty. retry with expanded query")
            docs = researcher.collect(f"{theme} 最新 動向 企業 規制 投資 発表", max_results=8)
        debug_dump([{"title": d.get("title"), "url": d.get("url")} for d in docs], "sources")
    except Exception as e:
        print(f"[error] tavily collect failed: {e}", file=sys.stderr)
        docs = []

    # 3) Claude で深堀り分析（analyze_claude.py の既定は haiku 推奨）
    try:
        print("[info] calling Claude analyzer ...")
        analyzer = DeepAnalyzer()  # model は analyze_claude.py 側のデフォルトを使用
        md: str = analyzer.analyze(theme, docs)
        print(f"[debug] Claude output length = {len(md) if md else 0}")
        if not md or len(md.strip()) < 100:
            print("[warn] Claude output was empty/too short. Write fallback frame.")
            md = (
                f"# {theme}\n\n"
                "生成テキストが空/短すぎでした。モデル権限やAPIキー、リクエスト量をご確認ください。\n"
                "最低限のフレームを保存しています。"
            )
    except Exception as e:
        print(f"[error] Claude analyze raised: {e}", file=sys.stderr)
        md = f"# {theme}\n\n分析中に例外が発生しました: {e}"

    # 4) ファイルに書き出し
    write_markdown(md, theme)
    print("[info] done main_article")

if __name__ == "__main__":
    main()
