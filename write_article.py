from __future__ import annotations
import datetime

def to_markdown(theme: str, analysis_md: str) -> str:
    today = datetime.date.today().isoformat()
    frontmatter = (
        f"---\n"
        f"title: {theme}\n"
        f"date: {today}\n"
        f"layout: article\n"
        f"---\n\n"
    )
    return frontmatter + analysis_md
