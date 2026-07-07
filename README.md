# Hide専用ニュース

決済・Agentic Commerce・デジタルID/VC・コンサル/政策のRSSを集め、日本語で要約して1枚に。
GitHub Pagesで公開: https://hasuim.github.io/hide-news/

## 仕組み（自己完結）
1. `python3 fetch_news.py`   … RSS巡回 → news_data.json（🔭ウォッチ候補も表示）
2. curated_news.json を編集   … 今日の注目・テーマ別の日本語要約（Claudeが担当）
3. `python3 generate_news.py` … index.html を生成

毎朝この一連を自動実行し、index.html を更新してPagesへ反映する。

## 依存
`pip install -r requirements.txt`（feedparser）
