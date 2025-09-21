from __future__ import annotations
import os
from typing import List, Dict
from anthropic import Anthropic

# Claude への指示（ビジネスレポート風・深掘り重視）
ANALYSIS_SYSTEM = (
    "あなたは一流のアナリスト兼編集者です。"
    "与えられた資料をもとに、日本語で『深掘り分析メモ（ビジネスレポート風）』を作成します。"
    "単なる要約ではなく、因果関係、多視点の比較、反証可能性、リスク、将来シナリオ、"
    "ビジネス/社会的含意を必須とします。"
    "本文中に [1] のように出典番号を差し込み、最後に出典一覧を付与してください。"
)

# プロンプト（ユーザー側の入力として与えるテンプレート）
USER_TMPL = """
# テーマ
{theme}

# 資料（最大12件）
{sources}

# 出力仕様
- 形式: Markdown（ビジネスレポート風）
- 構成: エグゼクティブサマリー → 背景/課題 → 主要インサイト(3-5) → 反論・不確実性 → 将来シナリオ(短/中/長期) → ビジネス・政策への示唆 → Takeaways（5点） → 出典一覧
- ルール: 数字・日付・引用は必ず [n] を付与。出典が矛盾する場合は両論併記し、前提の差異を明確化。
"""

def format_sources(docs: List[Dict]) -> str:
    """Tavilyで収集した資料を、Claudeが参照しやすい文字列に整形。"""
    out = []
    for i, d in enumerate(docs, start=1):
        title = d.get("title", "")
        url = d.get("url", "")
        content = d.get("content", "")[:700]  # 抜粋は700字まで
        out.append(f"[{i}] {title} — {url}\n抜粋:\n{content}")
    return "\n\n".join(out)

class DeepAnalyzer:
    """Claudeに深掘り分析を依頼してMarkdownを返すクラス。"""

    def __init__(self, api_key: str | None = None, model: str = "claude-3-5-sonnet-20240620"):
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model

    def analyze(self, theme: str, docs: List[Dict]) -> str:
        sources_block = format_sources(docs)
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            temperature=0.5,
            system=ANALYSIS_SYSTEM,
            messages=[{"role": "user", "content": USER_TMPL.format(theme=theme, sources=sources_block)}],
        )
        # 返却は text パーツを連結
        return "".join(
            [part.text for part in msg.content if getattr(part, "type", None) == "text"]
        ) or ""
