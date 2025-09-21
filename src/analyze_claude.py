# src/analyze_claude.py
from __future__ import annotations
import os
from typing import List, Dict
from anthropic import Anthropic
from anthropic._exceptions import NotFoundError

# =========================
# 実務コンサル向け・高密度プロンプト
# =========================
ANALYSIS_SYSTEM = (
    "あなたはフォーチュン500の経営陣に助言するマネージング・ディレクター級のストラテジーコンサルタントです。"
    "目的は、与えられた資料から『実務で意思決定に使えるリサーチ・ブリーフ』を日本語で作成すること。"
    "一般論や抽象論は排し、具体的な企業名・製品名・数値・規制名・日付・資金調達/提携/人事などのファクトを明記する。"
    "本文中の主張・数字・日付には必ず [n] で出典番号を付け、末尾に出典一覧を付与する。"
    "推測は避け、根拠が弱い箇所は『不確実性』に回す。誇張や断定はしない。"
    "出力は最終結論のみで、思考過程は出力しない。"
)

USER_TMPL = """
# テーマ
{theme}

# 提供資料（最大12件）
{sources}

# 出力仕様（厳守）
- 形式: Markdown
- 文体: 経営層が3分で全体把握 → 担当者が即アクション可能な粒度まで掘る
- 構成:
1. エグゼクティブブリーフ（120字以内：結論とWhy now）
2. 重要ソース5選（各: タイトル / URL / なぜ重要か / 主要ファクト1–2個）※必ずURLを明記
3. マーケット/技術のいま（具体名・比較表/箇条書き可。勝者/敗者/理由）
4. 競合・エコシステム動向（企業名・提携・調達・人材・ロードマップ）
5. 企業/政策への含意（事業・製品・Go-To-Market・運用・規制の観点で具体）
6. 推奨アクション（30日/90日/180日、各3件以内。想定担当部門と実行難易度も）
7. 指標と先行シグナル（定量KPI、監視トリガー、閾値を If–Then 形式で）
8. 反論・不確実性（反証可能な仮説、データギャップ、起こり得る分岐）
9. 出典一覧
- ルール:
  * 数字・日付・社名・規制名・金額には必ず [n] を付ける
  * 可能ならセクター別（金融/製造/小売/公共など）に具体化
  * 表・箇条書きを積極活用。余計な前置きは不要
  * 出典リンクは必ずURLを明記し、本文の [n] と整合させる
"""

def format_sources(docs: List[Dict]) -> str:
    """
    Claudeに渡すソース一覧（タイトル/URL/抜粋）。
    参照番号 [1].. と本文の [n] を対応させるためのひな型。
    """
    out = []
    for i, d in enumerate(docs, start=1):
        title = d.get("title", "")
        url = d.get("url", "")
        excerpt = (d.get("content", "") or "")[:700]
        out.append(f"[{i}] {title} — {url}\n抜粋:\n{excerpt}")
    return "\n\n".join(out)

class DeepAnalyzer:
    """
    main_article.py から呼び出される分析器。
    - analyze(theme, docs) -> Markdown文字列
    - 既存コードと完全互換のインターフェイス
    """
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        # モデル候補（APIキーの権限差吸収）
        self.candidate_models = [
            model or "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307",
            "claude-3-opus-20240229",
        ]

    def _try_call(self, model: str, theme: str, sources_block: str) -> str:
        msg = self.client.messages.create(
            model=model,
            max_tokens=5000,    # 情報密度を確保
            temperature=0.3,    # ばらつきを抑え、一貫性・ファクト志向に
            system=ANALYSIS_SYSTEM,
            messages=[{"role": "user", "content": USER_TMPL.format(theme=theme, sources=sources_block)}],
        )
        # テキストパートを連結（Anthropic SDKの標準構造）
        return "".join([p.text for p in msg.content if getattr(p, "type", None) == "text"]) or ""

    def analyze(self, theme: str, docs: List[Dict]) -> str:
        sources_block = format_sources(docs)
        last_err = None
        for m in self.candidate_models:
            try:
                return self._try_call(m, theme, sources_block)
            except NotFoundError as e:
                # 次の候補にフォールバック
                last_err = e
        # すべて失敗した場合は明示的に例外
        raise RuntimeError(f"No available Anthropic model for this API key. Last error: {last_err}")
