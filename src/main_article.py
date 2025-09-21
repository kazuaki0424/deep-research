# src/main_article.py
from __future__ import annotations
import os, sys, re, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Tuple, Optional

# 相対インポート（python -m src.main_article で動く）
from .research import Researcher
from .analyze_claude import DeepAnalyzer
import markdown2
import yaml

# ===== 基本設定（.envで上書き可） =====
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "public"))
LANG = os.getenv("LANGUAGE", "ja-JP")
TOPICS_FILE = Path("topics.yaml")
TIMEZONE_HOURS = int(os.getenv("TIMEZONE_HOURS", "9"))  # JSTがデフォルト
# 週末テーマの環境変数（カンマ区切り）。topics.yaml側があればそちら優先
ENV_WEEKEND_TOPICS = [s.strip() for s in os.getenv("WEEKEND_TOPICS", "").split(",") if s.strip()]

# ===== ユーティリティ =====
def now_local():
    return datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=TIMEZONE_HOURS)

def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)

def _read_topics_yaml() -> Tuple[List[str], List[str]]:
    """
    topics.yaml 仕様（後方互換）:
    - 旧: [AI, フィンテック, 量子, ロボティクス]
    - 新: { topics: [...], weekend_topics: [...] }
    weekend_topics が無い場合は環境変数 WEEKEND_TOPICS、さらに無ければ ["AI戦略"] を利用
    """
    topics: List[str] = []
    weekend_topics: List[str] = []

    if TOPICS_FILE.exists():
        with TOPICS_FILE.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if isinstance(data, dict):
            topics = [str(t) for t in (data.get("topics") or []) if t]
            weekend_topics = [str(t) for t in (data.get("weekend_topics") or []) if t]
        elif isinstance(data, list):
            topics = [str(t) for t in data if t]
    # フォールバック
    if not topics:
        topics = ["テクノロジー総覧"]
    if not weekend_topics:
        weekend_topics = ENV_WEEKEND_TOPICS or ["AI戦略"]
    return topics, weekend_topics

def load_topics() -> List[str]:
    # 既存インターフェイス維持（他から呼ばれる可能性に配慮）
    topics, _ = _read_topics_yaml()
    return topics

def pick_today_topic(topics: List[str], weekend_topics: Optional[List[str]] = None) -> str:
    """
    平日: topics を曜日ローテーション
    週末(土日): weekend_topics からローテーション（固定技術テーマを想定）
    """
    weekday = now_local().weekday()  # 0=Mon ... 6=Sun
    weekend_topics = weekend_topics or ["AI戦略"]
    if weekday >= 5:  # 土日
        return weekend_topics[(weekday - 5) % len(weekend_topics)]
    if not topics:
        return "テクノロジー総覧"
    return topics[weekday % len(topics)]

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
        # HTMLタイトルを抽出（<title>...</title>）できれば優先。失敗時はファイル名
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"<title>(.*?)</title>", txt, re.IGNORECASE | re.DOTALL)
            if m:
                return re.sub(r"\s+", " ", m.group(1).strip())
        except Exception:
            pass
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

    # 1) テーマ決定（平日=ローテーション / 週末=固定技術テーマ）
    topics, weekend_topics = _read_topics_yaml()
    theme = pick_today_topic(topics, weekend_topics=weekend_topics)
    print(f"[info] theme = {theme}")

    # 2) 情報収集（Tavily）
    tavily_key = os.getenv("TAVILY_API_KEY")
    if not tavily_key:
        print("[error] TAVILY_API_KEY is missing.", file=sys.stderr)
        md = (
            f"# {theme}\n\n"
            "Tavily の API キーが未設定です。GitHub → Settings → Secrets and variables → Actions に "
            "`TAVILY_API_KEY` を追加してください。"
        )
        write_markdown(md, theme)
        write_html_from_markdown(md, theme)
        rebuild_articles_index()
        print("[info] done main_article (no tavily key)")
        return

    researcher = Researcher(tavily_api_key=tavily_key)
    try:
        print("[info] collecting sources via Tavily ...")
        # 検索精度強化：複数クエリの自動拡張・品質ブースト・重複排除を内部で実施
        docs: List[Dict] = researcher.collect(theme, max_results=14, weekend=(now_local().weekday() >= 5))
        if not docs:
            print("[warn] docs empty; retry with expanded query")
            docs = researcher.collect(f"{theme} 最新 動向 企業 規制 投資 提携 ロードマップ ベンチマーク", max_results=14)
        # ログにURLだけ出す
        summary = [{"title": d.get("title"), "url": d.get("url")} for d in docs]
        print(f"[debug] sources: {json.dumps(summary, ensure_ascii=False)[:2000]}")
    except Exception as e:
        print(f"[error] tavily collect failed: {e}", file=sys.stderr)
        docs = []

    # 3) Claude で深掘り
    try:
        print("[info] calling Claude analyzer ...")
        analyzer = DeepAnalyzer()  # 既存と互換
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
