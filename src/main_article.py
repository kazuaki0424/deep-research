# src/main_article.py
from __future__ import annotations
import os, sys, re, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict

# 相対インポート（python -m src.main_article で動く）
from .research import Researcher
from .analyze_claude import DeepAnalyzer
import markdown2

# ===== 基本設定（.envで上書き可） =====
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
    """topics.yaml は以下のどちらでもOK:
    - [AI, フィンテック, 量子, ロボティクス]
    - { topics: [AI, フィンテック, ...] }
    """
    import yaml
    if not TOPICS_FILE.exists():
        print(f"[warn] topics.yaml not found, fallback to default topic", file=sys.stderr)
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

def extract_title(md_text: str) -> str | None:
    m = re.search(r'^\s*#\s+(.+)$', md_text, re.MULTILINE)
    return m.group(1).strip() if m else None

def write_markdown(md_text: str, theme: str) -> Path:
    articles_dir = OUTPUT_DIR / "articles"
    ensure_dir(articles_dir)
    date_str = now_local().strftime("%Y-%m-%d")
    path = articles_dir / f"{date_str}-{safe_slug(theme)}.md"
    path.write_text(md_text, encoding="utf-8")
    print(f"[ok] wrote markdown: {path}")
    return path

def write_html_from_markdown(md_text: str, theme: str) -> Path:
    """Markdown を HTML に変換して保存（CSS付き・単一ページ）"""
    articles_dir = OUTPUT_DIR / "articles"
    ensure_dir(articles_dir)
    date_str = now_local().strftime("%Y-%m-%d")

    html_body = markdown2.markdown(md_text, extras=["fenced-code-blocks", "tables"])
    title = extract_title(md_text) or theme
    page = (
        "<!doctype html><meta charset='utf-8'>"
        f"<title>{title}</title>"
        "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/water.css@2/out/water.css'>"
        f"<h1>{title}</h1>\n" + html_body +
        "<p><a href='./'>← 記事一覧へ</a></p>"
    )
    out = articles_dir / f"{date_str}-{safe_slug(theme)}.html"
    out.write_text(page, encoding="utf-8")
    print(f"[ok] wrote html: {out}")
    return out

def rebuild_articles_index():
    """articles ディレクトリ内の .html を拾って一覧を作り直す（降順）"""
    articles_dir = OUTPUT_DIR / "articles"
    ensure_dir(articles_dir)
    pages = sorted(articles_dir.glob("*.html"), reverse=True)
    if not pages:
        # 初回用のプレースホルダ
        (articles_dir / "index.html").write_text(
            "<!doctype html><meta charset='utf-8'><title>Articles</title>"
            "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/water.css@2/out/water.css'>"
            "<h1>Articles</h1><p>まだ記事がありません。</p>",
            encoding="utf-8"
        )
        print(f"[ok] wrote placeholder index: {articles_dir/'index.html'}")
        return

    def label(p: Path) -> str:
        # ファイル名（stem）をラベルに。必要なら本文タイトルを抽出してもOK
        return p.stem

    lis = "\n".join(f"<li><a href='./{p.name}'>{label(p)}</a></li>" for p in pages)
    html = (
        "<!doctype html><meta charset='utf-8'><title>Articles</title>"
        "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/water.css@2/out/water.css'>"
        "<h1>Articles</h1><ul>" + lis + "</ul><p><a href='../'>トップ</a></p>"
    )
    (articles_dir / "index.html").write_text(html, encoding="utf-8")
    print(f"[ok] rebuilt index: {articles_dir/'index.html'}")

# ===== メイン処理 =====
def main():
    print("[info] start main_article")
    ensure_dir(OUTPUT_DIR / "articles")

    # 1) テーマ決定（ローテーション）
    topics = load_topics()
    theme = pick_today_topic(topics)
    print(f"[info] theme = {theme}")

    # 2) 情報収集（Tavily）
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        print("[error] TAVILY_API_KEY is missing.", file=sys.stderr)
        md = f"# {theme}\n\nTavily の API キーが未設定です。Settings → Secrets → Actions に `TAVILY_API_KEY` を追加してください。"
        write_markdown(md, theme)
        write_html_from_markdown(md, theme)
        rebuild_articles_index()
        print("[info] done main_article (no tavily key)")
        return

    researcher = Researcher(tavily_api_key=tavily_key)
    try:
        print("[info] collecting sources via Tavily ...")
        docs: List[Dict] = researcher.collect(theme, max_results=8)
        if not docs:
            print("[warn] docs empty; retry with expanded query")
            docs = researcher.collect(f"{theme} 最新 動向 企業 規制 投資 発表", max_results=8)
        # ログにURLだけ出す
        summary = [{"title": d.get("title"), "url": d.get("url")} for d in docs]
        print(f"[debug] sources: {json.dumps(summary, ensure_ascii=False)[:1000]}")
    except Exception as e:
        print(f"[error] tavily collect failed: {e}", file=sys.stderr)
        docs = []

    # 3) Claude で深掘り
    try:
        print("[info] calling Claude analyzer ...")
        analyzer = DeepAnalyzer()  # analyze_claude.py 既定は haiku 推奨
        md: str = analyzer.analyze(theme, docs)
        print(f"[debug] Claude output length = {len(md) if md else 0}")
        if not md or len(md.strip()) < 100:
            print("[warn] Claude output empty/short; writing fallback frame")
            md = (
                f"# {theme}\n\n"
                "生成テキストが空/短すぎでした。モデル権限やAPIキーをご確認ください。"
            )
    except Exception as e:
        print(f"[error] Claude analyze raised: {e}", file=sys.stderr)
        md = f"# {theme}\n\n分析中に例外が発生しました: {e}"

    # 4) 保存（.md と .html） + 一覧更新
    write_markdown(md, theme)
    write_html_from_markdown(md, theme)
    rebuild_articles_index()

    print("[info] done main_article")

if __name__ == "__main__":
    main()
