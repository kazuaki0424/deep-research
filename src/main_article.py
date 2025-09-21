from __future__ import annotations
import os, yaml, pathlib, datetime
from dotenv import load_dotenv
from .research import Researcher
from .analyze_claude import DeepAnalyzer
from .write_article import to_markdown
from .utils import slugify

def pick_topic(cfg: dict) -> dict:
    weekday = datetime.date.today().strftime("%a")  # Mon, Tue, ...
    for t in cfg.get("topics", []):
        if t.get("day") == weekday:
            return t
    return cfg.get("topics", [])[0]

def main():
    load_dotenv()

    with open("topics.yaml", "r", encoding="utf-8") as f:
        topics = yaml.safe_load(f)
    topic = pick_topic(topics)
    theme = topic["title"]
    query = topic["query"]

    # 1) 最新情報収集
    r = Researcher(os.environ["TAVILY_API_KEY"])
    docs = r.collect(query, max_results=12)

    # 2) ClaudeでDeep Research分析
    analyzer = DeepAnalyzer(os.environ.get("ANTHROPIC_API_KEY"))
    analysis_md = analyzer.analyze(theme, docs)

    # 3) Markdown記事として保存
    out_dir = os.environ.get("OUTPUT_DIR", "public")
    art_dir = os.path.join(out_dir, "articles")
    pathlib.Path(art_dir).mkdir(parents=True, exist_ok=True)
    slug = slugify(f"{datetime.date.today().isoformat()}-{theme}")
    md_path = os.path.join(art_dir, f"{slug}.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(theme, analysis_md))

    print("Generated article:", md_path)

if __name__ == "__main__":
    main()
