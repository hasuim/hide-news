#!/bin/bash
# index.html を生成して GitHub Pages へ公開する（generate → commit → push を1コマンドに集約）。
# 自動更新タスク/手動の両方から `bash /Users/hasumihideyuki/hide-news/publish.sh` で呼ぶ。
# cd と git を1行に並べる書き方(cd && git)はハーネスが「常に許可」を出さないため、
# ここに閉じ込めて外からは1コマンドに見せる。
set -e
cd /Users/hasumihideyuki/hide-news

python3 generate_news.py

git add -A
if git diff --cached --quiet; then
  echo "変更なし（更新をスキップ）"
  exit 0
fi
git commit -m "Update news $(date '+%Y-%m-%d %H:%M')"
git push origin main
echo "公開しました。"
