#!/usr/bin/env python3
"""Render news.html from curated_news.json (Claude-curated, Japanese, summarized).

Flow:
    1. python3 fetch_news.py       # collect feeds -> news_data.json (raw pool)
    2. (Claude) rewrite curated_news.json from that pool
       - picks   : 今日の注目（出典をバラす / ★1-3）
       - sections: テーマ別（各記事に日本語見出し + 1行要約 / 英語は日本語化）
    3. python3 generate_news.py    # -> news.html

news.html has a client-side "ストック" feature: a ＋ button on each article saves
it to the browser (localStorage). The ストック panel can copy/export the saved list
so Claude can file it into the knowledge base (knowledge-stock skill).
"""

import html
import json
import os
from datetime import datetime

OUT_DIR = os.path.dirname(os.path.abspath(__file__))
CURATED_JSON = os.path.join(OUT_DIR, "curated_news.json")
OUT_HTML = os.path.join(OUT_DIR, "index.html")

# Display order + accent color per theme.
THEME_ORDER = [
    ("決済・フィンテック", "#2a78d6"),
    ("Agentic Commerce", "#e34948"),
    ("デジタルアイデンティティ/VC", "#4a3aa7"),
    ("コンサル/政策", "#eda100"),
]

CSS = """
:root {
  --surface-1: #fcfcfb; --page: #f9f9f7;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #898781;
  --grid: #e1e0d9; --border: rgba(11,11,11,0.10); --accent-line: #2a78d6;
}
@media (prefers-color-scheme: dark) {
  :root {
    --surface-1: #1a1a19; --page: #0d0d0d;
    --text-primary: #ffffff; --text-secondary: #c3c2b7; --text-muted: #7d7c77;
    --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 20px; background: var(--page); color: var(--text-primary);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif; line-height: 1.6;
}
.wrap { max-width: 900px; margin: 0 auto; }
header.top { margin-bottom: 20px; }
header.top h1 { font-size: 22px; margin: 0 0 4px; letter-spacing: .01em; }
header.top .meta { font-size: 12px; color: var(--text-muted); }
h2.section { font-size: 13px; text-transform: uppercase; letter-spacing: .05em;
  color: var(--text-secondary); font-weight: 600; margin: 34px 0 12px;
  display: flex; align-items: center; gap: 8px; }
.dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; }
.count { color: var(--text-muted); font-weight: 400; letter-spacing: 0; text-transform: none; }

/* stock (＋) button */
.stock-btn { flex-shrink: 0; width: 24px; height: 24px; border-radius: 50%;
  border: 1px solid var(--border); background: var(--surface-1); color: var(--text-muted);
  font-size: 15px; line-height: 1; cursor: pointer; padding: 0; }
.stock-btn:hover { background: var(--grid); color: var(--text-primary); }
.stock-btn.on { background: #eda100; border-color: #eda100; color: #fff; }

.pick { background: var(--surface-1); border: 1px solid var(--border); border-left: 3px solid var(--accent);
  border-radius: 10px; padding: 14px 16px; margin-bottom: 10px; }
.pick .head { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.stars { color: #eda100; font-size: 13px; letter-spacing: 1px; flex-shrink: 0; }
.pick a.title { font-size: 15px; font-weight: 600; color: var(--text-primary); text-decoration: none; flex: 1; }
.pick a.title:hover { text-decoration: underline; }
.pick .src { font-size: 11px; color: var(--text-muted); margin-top: 4px; }
.pick .summary { font-size: 13px; color: var(--text-secondary); margin-top: 6px; }

ul.feed { list-style: none; padding: 0; margin: 0; }
ul.feed li { padding: 12px 2px; border-bottom: 1px solid var(--grid); display: flex; gap: 10px; align-items: flex-start; }
ul.feed .body { flex: 1; }
ul.feed a.title { color: var(--text-primary); text-decoration: none; font-size: 14px; font-weight: 600; }
ul.feed a.title:hover { text-decoration: underline; }
ul.feed .src { font-size: 11px; color: var(--text-muted); margin-left: 6px; }
ul.feed .summary { font-size: 12.5px; color: var(--text-secondary); margin-top: 3px; }

/* 横断ウォッチ枠 */
.watch { border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; margin-bottom: 8px;
  background: linear-gradient(180deg, rgba(26,175,122,0.08), transparent 60%); }
.watch h2 { font-size: 15px; margin: 0 0 4px; display: flex; align-items: center; gap: 8px; }
.watch .thesis { font-size: 12.5px; color: var(--text-secondary); margin: 0 0 12px; }
.watch ul { list-style: none; margin: 0; padding: 0; }
.watch li { padding: 9px 0; border-top: 1px solid var(--grid); display: flex; gap: 10px; align-items: flex-start; }
.watch .body { flex: 1; }
.watch a.title { color: var(--text-primary); text-decoration: none; font-size: 13.5px; font-weight: 600; }
.watch a.title:hover { text-decoration: underline; }
.watch .src { font-size: 11px; color: var(--text-muted); margin-left: 6px; }
.watch .summary { font-size: 12px; color: var(--text-secondary); margin-top: 2px; }
.watch .tag { font-size: 10px; color: #1baf7a; border: 1px solid #1baf7a; border-radius: 4px; padding: 0 5px; margin-left: 6px; white-space: nowrap; }

/* stock panel */
#stock-panel { border: 1px solid var(--border); border-radius: 10px; background: var(--surface-1);
  margin-bottom: 8px; overflow: hidden; }
#stock-panel[hidden] { display: none; }
#stock-panel summary { cursor: pointer; padding: 12px 16px; font-size: 13px; font-weight: 600;
  color: var(--text-primary); display: flex; align-items: center; gap: 8px; }
#stock-panel .actions { padding: 0 16px 6px; display: flex; gap: 8px; flex-wrap: wrap; }
#stock-panel .actions button { font-size: 12px; border: 1px solid var(--border); background: var(--surface-1);
  color: var(--text-secondary); border-radius: 6px; padding: 4px 10px; cursor: pointer; }
#stock-panel .actions button:hover { background: var(--grid); color: var(--text-primary); }
#stock-list { list-style: none; margin: 0; padding: 4px 16px 14px; }
#stock-list li { padding: 8px 0; border-top: 1px solid var(--grid); display: flex; gap: 8px; align-items: flex-start; }
#stock-list a { color: var(--text-primary); text-decoration: none; font-size: 13px; flex: 1; }
#stock-list a:hover { text-decoration: underline; }
#stock-list .rm { cursor: pointer; color: var(--text-muted); border: none; background: none; font-size: 14px; }
#stock-list .st { font-size: 11px; color: var(--text-muted); }

footer { margin-top: 40px; padding-top: 14px; border-top: 1px dashed var(--border);
  font-size: 11px; color: var(--text-muted); }
.toast { position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
  background: var(--text-primary); color: var(--surface-1); padding: 8px 16px; border-radius: 8px;
  font-size: 12px; opacity: 0; transition: opacity .2s; pointer-events: none; }
.toast.show { opacity: 1; }
"""

JS = """
<script>
const KEY = 'hide_news_stock_v1';
const load = () => { try { return JSON.parse(localStorage.getItem(KEY)) || []; } catch(e){ return []; } };
const save = (a) => localStorage.setItem(KEY, JSON.stringify(a));
const has = (link, a) => a.some(x => x.link === link);

function toast(msg){
  let t = document.querySelector('.toast');
  if(!t){ t = document.createElement('div'); t.className='toast'; document.body.appendChild(t); }
  t.textContent = msg; t.classList.add('show');
  clearTimeout(t._t); t._t = setTimeout(()=>t.classList.remove('show'), 1400);
}

function toggle(item){
  let a = load();
  if(has(item.link, a)){ a = a.filter(x => x.link !== item.link); }
  else { a.unshift({...item, stocked_at: new Date().toISOString()}); toast('ストックに追加'); }
  save(a); render();
}

function render(){
  const a = load();
  const links = new Set(a.map(x => x.link));
  document.querySelectorAll('.stock-btn').forEach(b => {
    const on = links.has(b.dataset.link);
    b.classList.toggle('on', on);
    b.textContent = on ? '✓' : '＋';
    b.title = on ? 'ストックから外す' : 'ストックに追加';
  });
  const panel = document.getElementById('stock-panel');
  const list = document.getElementById('stock-list');
  const cnt = document.getElementById('stock-count');
  cnt.textContent = a.length;
  panel.hidden = a.length === 0;
  list.innerHTML = a.map(x =>
    `<li><button class="rm" data-link="${encodeURIComponent(x.link)}" title="外す">✕</button>`
    + `<a href="${x.link}" target="_blank" rel="noopener">${x.title}`
    + `<div class="st">${[x.source, (x.date||''), x.theme].filter(Boolean).join(' · ')}</div></a></li>`
  ).join('');
  list.querySelectorAll('.rm').forEach(btn => btn.onclick = () => {
    const link = decodeURIComponent(btn.dataset.link);
    save(load().filter(x => x.link !== link)); render();
  });
}

function toMarkdown(a){
  return a.map(x => `- [${x.title}](${x.link}) — ${x.source||''}${x.date? ' · '+x.date : ''}`
    + (x.theme? ` 〔${x.theme}〕`:'') + (x.summary? `\\n  ${x.summary}` : '')).join('\\n');
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.stock-btn').forEach(b => {
    b.onclick = () => { try { toggle(JSON.parse(b.dataset.item)); } catch(e){ console.error(e); } };
  });
  document.getElementById('stock-copy').onclick = async () => {
    const a = load(); if(!a.length){ toast('ストックは空です'); return; }
    try { await navigator.clipboard.writeText(toMarkdown(a)); toast('コピーしました（Claudeに貼り付け可）'); }
    catch(e){ toast('コピー失敗'); }
  };
  document.getElementById('stock-export').onclick = () => {
    const a = load(); if(!a.length){ toast('ストックは空です'); return; }
    const blob = new Blob([JSON.stringify(a, null, 2)], {type:'application/json'});
    const url = URL.createObjectURL(blob); const el = document.createElement('a');
    el.href = url; el.download = 'news_stock.json'; el.click(); URL.revokeObjectURL(url);
    toast('news_stock.json を書き出し');
  };
  document.getElementById('stock-clear').onclick = () => {
    if(load().length && confirm('ストックを全部消しますか？')){ save([]); render(); }
  };
  render();
});
</script>
"""


def esc(text):
    return html.escape(text or "")


def stock_btn(item):
    """＋ button carrying the article payload for client-side stocking."""
    payload = {
        "title": item.get("title"),
        "link": item.get("link"),
        "source": item.get("source"),
        "date": item.get("date"),
        "theme": item.get("theme"),
        "summary": item.get("summary"),
    }
    data = html.escape(json.dumps(payload, ensure_ascii=False))
    return (f'<button class="stock-btn" data-link="{esc(item.get("link"))}" '
            f'data-item="{data}" title="ストックに追加">＋</button>')


def src_meta(item):
    return " · ".join(x for x in [esc(item.get("source")), esc(item.get("date"))] if x)


def render():
    with open(CURATED_JSON, encoding="utf-8") as fh:
        data = json.load(fh)
    watch = data.get("watch")
    picks = data.get("picks", [])
    sections = data.get("sections", {})

    gen = datetime.now().strftime("%Y-%m-%d %H:%M")
    watch_n = len(watch["items"]) if watch else 0
    total = watch_n + len(picks) + sum(len(v) for v in sections.values())
    parts = []

    # --- 🔭 横断ウォッチ ---
    if watch and watch.get("items"):
        rows = []
        for it in watch["items"]:
            tag = f'<span class="tag">{esc(it.get("theme"))}</span>' if it.get("theme") else ""
            rows.append(
                f'<li>{stock_btn(it)}<div class="body">'
                f'<a class="title" href="{esc(it["link"])}" target="_blank" rel="noopener">{esc(it["title"])}</a>'
                f'{tag}<span class="src">{src_meta(it)}</span>'
                f'<div class="summary">{esc(it.get("summary"))}</div></div></li>'
            )
        parts.append(
            '<div class="watch">'
            f'<h2>🔭 {esc(watch.get("title"))}</h2>'
            f'<p class="thesis">{esc(watch.get("thesis"))}</p>'
            f'<ul>{"".join(rows)}</ul>'
            "</div>"
        )

    # --- 今日の注目 ---
    if picks:
        parts.append('<h2 class="section">今日の注目 '
                     f'<span class="count">{len(picks)}件</span></h2>')
        for p in picks:
            accent = dict(THEME_ORDER).get(p.get("theme"), "#888")
            stars = "★" * int(p.get("rating", 1))
            parts.append(
                f'<div class="pick" style="--accent:{accent}">'
                f'<div class="head"><span class="stars">{stars}</span>'
                f'<a class="title" href="{esc(p["link"])}" target="_blank" rel="noopener">{esc(p["title"])}</a>'
                f'{stock_btn(p)}</div>'
                f'<div class="src">{src_meta(p)} ｜ {esc(p.get("theme"))}</div>'
                f'<div class="summary">{esc(p.get("summary"))}</div>'
                f"</div>"
            )

    # --- テーマ別（各記事に1行要約 + ＋ボタン） ---
    for name, color in THEME_ORDER:
        items = sections.get(name, [])
        if not items:
            continue
        parts.append(
            f'<h2 class="section"><span class="dot" style="background:{color}"></span>'
            f'{esc(name)} <span class="count">{len(items)}件</span></h2>'
        )
        parts.append('<ul class="feed">')
        for it in items:
            it_with_theme = {**it, "theme": name}
            parts.append(
                f'<li>{stock_btn(it_with_theme)}<div class="body">'
                f'<a class="title" href="{esc(it["link"])}" target="_blank" rel="noopener">{esc(it["title"])}</a>'
                f'<span class="src">{src_meta(it)}</span>'
                f'<div class="summary">{esc(it.get("summary"))}</div></div></li>'
            )
        parts.append("</ul>")

    body = "\n".join(parts)
    stock_panel = (
        '<details id="stock-panel" hidden open>'
        '<summary>📌 ストック（<span id="stock-count">0</span>件）</summary>'
        '<div class="actions">'
        '<button id="stock-copy">⧉ コピー（Claude用）</button>'
        '<button id="stock-export">⤓ 書き出し(JSON)</button>'
        '<button id="stock-clear">全消去</button>'
        "</div>"
        '<ul id="stock-list"></ul>'
        "</details>"
    )

    doc = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Hideのニュース</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header class="top">
  <h1>Hide専用ニュース</h1>
  <div class="meta">生成: {gen} ／ 注目{len(picks)}件・全{total}件 ／ 記事の ＋ でストック</div>
</header>
{stock_panel}
{body}
<footer>fetch_news.py で収集 → curated_news.json を編集 → generate_news.py で生成。
ストックは「コピー」してClaudeに貼るか「書き出し」した news_stock.json を渡すと知識庫に取り込めます。</footer>
</div>
{JS}
</body>
</html>
"""
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(doc)
    print(f"生成しました: {OUT_HTML}（注目{len(picks)}件 / 全{total}件 / {len(THEME_ORDER)}テーマ）")


if __name__ == "__main__":
    render()
