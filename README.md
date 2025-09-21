# Nightly Deep Research Articles (Claude + Tavily)

毎晩、指定テーマを自動リサーチし、**ビジネスレポート風のMarkdown記事**を `public/articles/` に出力します。  
公開は **GitHub Pages**（推奨）または **Render（Static Site）** で可能。

---

## 0. 事前準備
- Python 3.11 インストール（macOS: `brew install python@3.11` など）
- Anthropic / Tavily の API キーを取得しておく（`.env`で設定）
- GitHub アカウント（既にお持ちです）

## 1. ローカル実行（初回テスト）
```bash
# 1) unzip 後、このフォルダに移動
cd deep-research-starter

# 2) 仮想環境を作成して有効化（macOS/Linux）
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell:  .venv\Scripts\Activate.ps1

# 3) 依存をインストール
pip install --upgrade pip
pip install -r requirements.txt

# 4) .env を作成（.env.example をコピーして値を入れる）
cp .env.example .env
# ANTHROPIC_API_KEY と TAVILY_API_KEY を必須で設定

# 5) 試しに実行
python -m src.main_article
# => public/articles/ に Markdown が生成されます
```

## 2. GitHub に公開
1) 新規リポジトリを作成して、このフォルダ一式を push  
2) リポジトリ Settings → Pages → **Source: GitHub Actions** or **Deploy from branch**（`/public` を公開）  
3) Settings → Secrets and variables → Actions で以下を登録  
- **Secrets**: `ANTHROPIC_API_KEY`, `TAVILY_API_KEY`  
- **Variables**: `SITE_TITLE`, `SITE_DESCRIPTION`, `AUTHOR`, `FEED_BASE_URL` (例: `https://<username>.github.io/deep-research`)

4) Actions タブで `workflow_dispatch` を1回実行（初回テスト）  
5) 以降、**毎晩 23:00 JST** に自動で記事が追加されます

## 3. テーマのローテーション
- `topics.yaml` の `day: Mon/Tue/...` でローテーションを管理
- 週末はテクノロジー全般のホットトピックを拾う設定になっています

## 4. NotebookLM で音声化（手動）
- 翌朝、生成された Markdown を NotebookLM に読み込ませ、Audio Overviews で会話型ポッドキャストに変換
- そのまま共有・試聴可能

## 5. Render で公開（任意）
- Render の Static Site として GitHub リポジトリを接続
- **Build Command**: `pip install -r requirements.txt && python -m src.main_article`  
- **Publish Directory**: `public`
- **Builds** を毎晩走らせたい場合は Render の cron（または GitHub Actions のみでOK）

## 6. トラブルシュート
- Tavily 429/403: 検索数を減らす（`collect(..., max_results=8)`）
- Claude token 超過: 1記事あたりの出典を減らす、抜粋長を700→400に
- 日本語が固い: 分析モデルは `claude-3-5-sonnet-latest`、temperature を 0.6 に

---

© 2025 Nightly Deep Research
