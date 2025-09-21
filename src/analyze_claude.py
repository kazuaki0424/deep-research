from __future__ import annotations
import os
from typing import List, Dict
from anthropic import Anthropic

ANALYSIS_SYSTEM = (
  "あなたは一流のアナリスト兼編集者です。"
  "与えられた資料をもとに、日本語で『深掘り分析メモ（ビジネスレポート風）』を作成します。"
  "単なる要約ではなく、因果関係、多視点の比較、反証可能性、リスク、将来シナリオ、ビジネス/社会的含意を必須とします。"
  "本文中に [1] のように出典番号を差し込み、最後に出典一覧を付与してください。"
)

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
    out = []
    for i, d in enumerate(docs, start=1):
        out.append(f"[{i}] {d.get('title','')} — {d.get('url','')}
抜粋:
{d.get('content','')[:700]}")
    return "\n\n".join(out)

class DeepAnalyzer:
    def __init__(self, api_key: str | None = None, model: str = "claude-3-5-sonnet-latest"):
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.model = model

    def analyze(self, theme: str, docs: List[Dict]) -> str:
        sources_block = format_sources(docs)
        msg = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            temperature=0.5,
            system=ANALYSIS_SYSTEM,
            messages=[{"role":"user","content": USER_TMPL.format(theme=theme, sources=sources_block)}]
        )
        return "".join([p.text for p in msg.content if getattr(p,'type',None)=="text"]) or ""
