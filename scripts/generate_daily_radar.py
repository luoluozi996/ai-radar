#!/usr/bin/env python3
"""Generate the Daily AI Content Radar report.

This MVP gathers public signals from GitHub, Hacker News, Hugging Face, and RSS
feeds, then writes an HTML report plus a WeChat summary payload.
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES_PATH = ROOT / "data" / "sources.json"
SUMMARY_PATH = ROOT / "data" / "latest-summary.json"
BASE_URL = "https://luoluozi996.github.io/ai-radar"
USER_AGENT = "ai-radar-generator/1.0"


def request_json(url: str, headers: dict[str, str] | None = None) -> dict | list:
    req_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        req_headers.update(headers)
    req = urllib.request.Request(url, headers=req_headers)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def request_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read().decode("utf-8", errors="replace")


def safe_fetch(label: str, func, fallback):
    try:
        return func()
    except Exception as exc:  # noqa: BLE001 - generation should degrade gracefully.
        print(f"[warn] {label} failed: {exc}", file=sys.stderr)
        return fallback


def iso_today(value: str | None) -> dt.date:
    if value:
        return dt.date.fromisoformat(value)
    return dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()


def date_minus(day: dt.date, days: int) -> str:
    return (day - dt.timedelta(days=days)).isoformat()


def clean_text(value: str, limit: int = 180) -> str:
    value = re.sub(r"<[^>]+>", " ", value or "")
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "…"


def source_weight(source: str) -> int:
    return {
        "GitHub": 26,
        "Hacker News": 22,
        "Hugging Face": 22,
        "RSS": 18,
    }.get(source, 12)


def score_item(item: dict) -> int:
    base = source_weight(item["source"])
    heat = min(34, int(item.get("heat", 0)))
    freshness = min(18, int(item.get("freshness", 10)))
    usability = min(14, int(item.get("usability", 8)))
    novelty = min(14, int(item.get("novelty", 8)))
    return max(45, min(96, base + heat + freshness + usability + novelty))


def metrics_for(item: dict, score: int) -> dict[str, int]:
    heat = min(95, 50 + int(item.get("heat", 0)))
    freshness = min(95, 62 + int(item.get("freshness", 10)))
    usability = min(94, 56 + int(item.get("usability", 8)))
    novelty = min(94, 58 + int(item.get("novelty", 8)))
    activity = min(94, 56 + max(8, score - 58))
    return {"heat": heat, "growth": freshness, "use": usability, "novelty": novelty, "activity": activity}


def classify(item: dict) -> str:
    title = (item["title"] + " " + item.get("summary", "")).lower()
    if item["source"] == "GitHub":
        if "agent" in title:
            return "开源项目 / Agent"
        if "llm" in title or "model" in title:
            return "开源项目 / LLM"
        return "开源项目"
    if item["source"] == "Hugging Face":
        return "模型 / Demo"
    if item["source"] == "Hacker News":
        return "热门讨论"
    return "深度文章 / 发布"


def action_for(item: dict) -> str:
    source = item["source"]
    if source == "GitHub":
        return "点开 README，看 Quick Start 和近期提交。"
    if source == "Hugging Face":
        return "点开模型或 Space，优先看 demo、license 和示例。"
    if source == "Hacker News":
        return "扫讨论区，重点看争议点和真实使用反馈。"
    return "阅读全文，判断是否影响你的产品/研究判断。"


def risk_for(item: dict) -> str:
    source = item["source"]
    if source == "GitHub":
        return "项目热度可能短期波动，真实可用性需要本地试跑。"
    if source == "Hugging Face":
        return "模型/Space 可能缺少稳定评测，需核对 license 和输入输出边界。"
    if source == "Hacker News":
        return "讨论热度不等于事实结论，需要回到原文核验。"
    return "文章观点可能有立场，建议结合原始公告或论文交叉验证。"


def fetch_github(config: dict, day: dt.date) -> list[dict]:
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    items: list[dict] = []
    for raw_query in config.get("github_queries", []):
        query = raw_query.replace("{date_minus_1}", date_minus(day, 1))
        params = urllib.parse.urlencode({"q": query, "sort": "updated", "order": "desc", "per_page": 8})
        data = request_json(f"https://api.github.com/search/repositories?{params}", headers=headers)
        for repo in data.get("items", []):
            title = repo.get("full_name", repo.get("name", "Untitled"))
            summary = repo.get("description") or "No repository description provided."
            stars = int(repo.get("stargazers_count") or 0)
            items.append({
                "source": "GitHub",
                "title": title,
                "summary": summary,
                "url": repo.get("html_url", ""),
                "heat": min(34, max(6, len(str(stars)) * 7)),
                "freshness": 16,
                "usability": 12 if repo.get("has_wiki") or repo.get("homepage") else 9,
                "novelty": 10,
            })
        time.sleep(0.7)
    return items


def fetch_hn(config: dict, day: dt.date) -> list[dict]:
    items: list[dict] = []
    timestamp = int(dt.datetime.combine(day - dt.timedelta(days=2), dt.time()).timestamp())
    terms = " OR ".join(config.get("hacker_news_terms", ["AI", "LLM", "agent"]))
    params = urllib.parse.urlencode({"query": terms, "tags": "story", "numericFilters": f"created_at_i>{timestamp}", "hitsPerPage": 12})
    data = request_json(f"https://hn.algolia.com/api/v1/search_by_date?{params}")
    for hit in data.get("hits", []):
        title = hit.get("title") or hit.get("story_title") or "Untitled HN discussion"
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        points = int(hit.get("points") or 0)
        comments = int(hit.get("num_comments") or 0)
        items.append({
            "source": "Hacker News",
            "title": title,
            "summary": f"HN discussion with {points} points and {comments} comments.",
            "url": url,
            "heat": min(34, points // 8 + comments // 10),
            "freshness": 16,
            "usability": 8,
            "novelty": 11,
        })
    return items


def fetch_hugging_face(day: dt.date) -> list[dict]:
    data = request_json("https://huggingface.co/api/models?sort=trending&limit=12")
    items: list[dict] = []
    for model in data if isinstance(data, list) else []:
        model_id = model.get("modelId") or model.get("id")
        if not model_id:
            continue
        tags = ", ".join((model.get("tags") or [])[:4])
        likes = int(model.get("likes") or 0)
        items.append({
            "source": "Hugging Face",
            "title": model_id,
            "summary": f"Trending Hugging Face model. Tags: {tags or 'not listed' }.",
            "url": f"https://huggingface.co/{model_id}",
            "heat": min(34, max(6, likes // 12)),
            "freshness": 14,
            "usability": 12,
            "novelty": 12,
        })
    return items


def parse_rss_date(entry: ET.Element) -> str:
    for tag in ("pubDate", "updated", "published"):
        value = entry.findtext(tag)
        if value:
            return value
    return ""


def fetch_rss(config: dict) -> list[dict]:
    items: list[dict] = []
    namespaces = {"atom": "http://www.w3.org/2005/Atom"}
    for feed in config.get("rss", []):
        text = request_text(feed["url"])
        root = ET.fromstring(text)
        if root.tag.endswith("rss") or root.find("channel") is not None:
            entries = root.findall("./channel/item")[:5]
            for entry in entries:
                title = entry.findtext("title") or "Untitled"
                summary = entry.findtext("description") or ""
                link = entry.findtext("link") or feed["url"]
                items.append({"source": "RSS", "source_name": feed["name"], "title": title, "summary": clean_text(summary), "url": link, "heat": 12, "freshness": 14, "usability": 9, "novelty": 11, "date": parse_rss_date(entry)})
        else:
            entries = root.findall("atom:entry", namespaces)[:5]
            for entry in entries:
                title = entry.findtext("atom:title", default="Untitled", namespaces=namespaces)
                summary = entry.findtext("atom:summary", default="", namespaces=namespaces) or entry.findtext("atom:content", default="", namespaces=namespaces)
                link_node = entry.find("atom:link", namespaces)
                link = link_node.attrib.get("href") if link_node is not None else feed["url"]
                items.append({"source": "RSS", "source_name": feed["name"], "title": title, "summary": clean_text(summary), "url": link, "heat": 12, "freshness": 14, "usability": 9, "novelty": 11, "date": parse_rss_date(entry)})
    return items


def dedupe(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for item in items:
        key = re.sub(r"\W+", "", (item.get("url") or item["title"]).lower())[:96]
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def select_items(items: list[dict], limit: int = 9) -> list[dict]:
    for item in items:
        item["score"] = score_item(item)
        item["metrics"] = metrics_for(item, item["score"])
        item["category"] = classify(item)
        item["action"] = action_for(item)
        item["risk"] = risk_for(item)
        item["summary"] = clean_text(item.get("summary", ""), 170)
    sorted_items = sorted(items, key=lambda x: x["score"], reverse=True)
    chosen: list[dict] = []
    source_counts: dict[str, int] = {}
    for item in sorted_items:
        count = source_counts.get(item["source"], 0)
        if count >= 4:
            continue
        chosen.append(item)
        source_counts[item["source"]] = count + 1
        if len(chosen) >= limit:
            break
    return chosen


def mini_radar(values: dict[str, int]) -> str:
    nums = [values["heat"], values["growth"], values["use"], values["novelty"], values["activity"]]
    return ",".join(str(n) for n in nums)


def render_html(day: dt.date, items: list[dict]) -> str:
    report_date = day.isoformat()
    top = items[0]
    top_three = items[:3]
    cards = []
    for item in items:
        cards.append(f"""
        <article class="card">
          <header><div><span class="pill">{html.escape(item['source'])}</span><h3>{html.escape(item['title'])}</h3></div><strong>{item['score']}</strong></header>
          <div class="card-body"><div><p>{html.escape(item['summary'])}</p><div class="decision"><div><b>行动建议</b><span>{html.escape(item['action'])}</span></div><div><b>风险</b><span>{html.escape(item['risk'])}</span></div></div></div><div class="mini" data-values="{mini_radar(item['metrics'])}"></div></div>
          <a class="link" href="{html.escape(item['url'])}" target="_blank" rel="noreferrer">打开原文 →</a>
        </article>""")
    quick = []
    labels = ["最值得点开", "最适合试用", "最值得收藏"]
    for index, item in enumerate(top_three):
        quick.append(f"""
        <a class="quick" href="{html.escape(item['url'])}" target="_blank" rel="noreferrer"><em>{index + 1:02d}</em><b>{labels[index]} · {html.escape(item['title'])}</b><p>{html.escape(item['summary'])}</p><span>打开 →</span></a>""")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{report_date} AI 内容雷达</title>
  <style>
    :root{{--bg:#f5f4ef;--paper:#fffdf8;--ink:#17211f;--muted:#66736e;--line:#d7d9d1;--soft:#eef3ed;--green:#28685b;--deep:#123f38;--warm:#c86b4f;--gold:#d2a83f}}*{{box-sizing:border-box}}body{{margin:0;background:linear-gradient(180deg,#fbfaf6,var(--bg));color:var(--ink);font:16px/1.62 Arial,Helvetica,sans-serif}}main{{width:min(1160px,calc(100% - 32px));margin:auto;padding:30px 0 56px}}a{{color:inherit}}.topbar{{height:8px;background:linear-gradient(90deg,var(--green),var(--warm),var(--gold));border-radius:999px;margin-bottom:24px}}.hero{{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:22px}}.hero-copy,.date-card,.panel,.card,.trend{{border:1px solid var(--line);border-radius:12px}}.hero-copy,.panel,.card,.trend{{background:var(--paper)}}.hero-copy{{padding:26px}}.date-card{{background:var(--deep);color:#eef7f2;padding:22px;display:grid;align-content:space-between}}.date-card strong{{display:block;font-size:30px;line-height:1.08}}.date-card span,.date-card small{{color:#bad0c8}}.eyebrow{{margin:0 0 8px;color:var(--green);font-weight:900;letter-spacing:.08em;text-transform:uppercase}}h1,h2,h3,p{{margin-top:0}}h1{{margin:0 0 12px;font-size:clamp(38px,6vw,76px);line-height:.98}}h2{{font-size:26px;margin-bottom:12px}}.lead{{max-width:760px;margin:0;color:var(--muted);font-size:18px}}.section{{margin-top:24px}}.section-head{{display:flex;align-items:end;justify-content:space-between;gap:18px;margin-bottom:12px}}.section-head p{{margin:0;max-width:620px;color:var(--muted)}}.quick-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.quick{{position:relative;display:grid;gap:10px;min-height:168px;padding:17px;border-radius:12px;text-decoration:none;overflow:hidden;border:1px solid var(--line);background:linear-gradient(145deg,#fffdf8,#e7f0eb)}}.quick:hover{{transform:translateY(-2px);box-shadow:0 16px 34px rgba(31,36,33,.11);border-color:var(--green)}}.quick em{{position:absolute;right:10px;top:2px;font-size:70px;font-style:normal;font-weight:900;line-height:1;color:rgba(18,63,56,.10)}}.quick b{{position:relative;color:var(--deep);font-size:18px}}.quick p{{position:relative;margin:0;color:var(--muted)}}.quick span{{position:relative;color:var(--green);font-size:13px;font-weight:900;align-self:end}}.dashboard{{display:grid;grid-template-columns:minmax(0,1fr) 380px;gap:18px}}.panel{{padding:22px}}.feature-title{{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}}.feature-title h2{{font-size:38px;margin:0}}.score{{font-size:42px;line-height:1;color:var(--green);font-weight:900}}.pill{{display:inline-flex;border-radius:999px;background:#dcebe5;color:var(--deep);font-size:13px;font-weight:900;padding:5px 9px}}.card-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}}.card{{padding:18px}}.card header{{display:flex;justify-content:space-between;gap:12px;margin-bottom:8px}}.card h3{{margin:4px 0 0;font-size:20px}}.card strong{{font-size:26px;color:var(--green)}}.card-body{{display:grid;grid-template-columns:minmax(0,1fr) 126px;gap:14px;align-items:start}}.card p,.trend p{{color:var(--muted)}}.decision{{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:12px}}.decision div{{background:var(--soft);border-radius:8px;padding:10px}}.decision b{{display:block;font-size:13px}}.decision span{{color:var(--muted);font-size:14px}}.link{{display:inline-flex;margin-top:14px;color:var(--deep);font-weight:900;text-decoration:none}}.mini{{width:126px;min-height:126px;border:1px solid var(--line);border-radius:10px;background:linear-gradient(180deg,#fbfaf6,#eef3ed);display:grid;place-items:center}}.mini svg{{width:112px;height:112px;display:block}}.mini-grid{{fill:none;stroke:#cfd7cf;stroke-width:1}}.mini-axis{{stroke:#c4cec5;stroke-width:1}}.mini-shape{{fill:rgba(40,104,91,.22);stroke:var(--green);stroke-width:2.2}}.mini-dot{{fill:var(--deep);stroke:var(--paper);stroke-width:1.5}}.mini-label{{fill:var(--muted);font-size:6.5px;font-weight:800}}.trend-grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}}.trend{{padding:18px}}.note{{margin-top:22px;border-top:1px solid var(--line);padding-top:15px;color:var(--muted);font-size:13px}}@media(max-width:920px){{.hero,.dashboard,.quick-grid,.card-grid,.trend-grid{{grid-template-columns:1fr}}.decision{{grid-template-columns:1fr}}}}@media(max-width:560px){{.card-body{{grid-template-columns:1fr}}.mini{{width:100%;min-height:150px}}.mini svg{{width:132px;height:132px}}}}
  </style>
</head>
<body>
  <main>
    <div class="topbar"></div>
    <section class="hero"><div class="hero-copy"><p class="eyebrow">Daily AI Content Radar</p><h1>AI 内容雷达</h1><p class="lead">多平台自动生成版：综合 GitHub、Hacker News、Hugging Face 和高质量 RSS，筛出今天最值得看的 AI 项目、讨论、模型和文章。</p></div><aside class="date-card"><div><strong>{report_date}</strong><span>今日主线：AI 内容信号继续向 agent、工具链、模型发布和真实使用反馈集中。</span></div><small>自动抓取 · 自动评分 · 自动推送</small></aside></section>
    <section class="section"><div class="section-head"><h2>今日结论</h2><p>每张卡都可以直接打开来源。</p></div><div class="quick-grid">{''.join(quick)}</div></section>
    <section class="section"><div class="section-head"><h2>主信号</h2><p>今日最高分内容，用来决定先看哪里。</p></div><div class="dashboard"><article class="panel"><span class="pill">{html.escape(top['source'])}</span><div class="feature-title"><h2>{html.escape(top['title'])}</h2><div class="score">{top['score']}</div></div><p>{html.escape(top['summary'])}</p><div class="decision"><div><b>行动建议</b><span>{html.escape(top['action'])}</span></div><div><b>风险</b><span>{html.escape(top['risk'])}</span></div></div><a class="link" href="{html.escape(top['url'])}" target="_blank" rel="noreferrer">打开来源 →</a></article><aside class="panel"><div class="mini" data-values="{mini_radar(top['metrics'])}"></div></aside></div></section>
    <section class="section"><div class="section-head"><h2>今日内容池</h2><p>按自动评分筛选出的候选内容，每条都带五轴小雷达。</p></div><div class="card-grid">{''.join(cards)}</div></section>
    <section class="section"><div class="section-head"><h2>今日趋势</h2><p>自动版趋势判断先保持克制，重点看跨平台信号是否相互印证。</p></div><div class="trend-grid"><article class="trend"><h3>项目与讨论开始融合</h3><p>GitHub 热项目需要结合 HN/RSS 讨论判断真实关注点。</p></article><article class="trend"><h3>模型/Demo 是补充信号</h3><p>Hugging Face 可以帮助发现可试用内容，而不只是读新闻。</p></article><article class="trend"><h3>微信摘要应该先给结论</h3><p>推送里直接给 Top 3 和今日主线，链接只作为深入阅读入口。</p></article></div><p class="note">数据源：公开 GitHub Search、Hacker News Algolia、Hugging Face API、RSS。自动评分用于辅助筛选，不等同于事实确认、投资、采购、安全或合规建议。</p></section>
  </main>
  <script>
    const miniAxes=["热","增","用","新","活"];function miniPoint(i,v){{const a=-Math.PI/2+i*Math.PI*2/5,r=38*v/100;return[50+Math.cos(a)*r,50+Math.sin(a)*r]}}function miniPolygon(v){{return Array.from({{length:5}},(_,i)=>miniPoint(i,v).join(",")).join(" ")}}document.querySelectorAll(".mini").forEach(node=>{{const values=node.dataset.values.split(",").map(Number),points=values.map((v,i)=>miniPoint(i,v).join(",")).join(" "),axes=miniAxes.map((label,i)=>{{const end=miniPoint(i,100),text=miniPoint(i,116);return `<line class="mini-axis" x1="50" y1="50" x2="${{end[0]}}" y2="${{end[1]}}"></line><text class="mini-label" x="${{text[0]}}" y="${{text[1]}}" text-anchor="middle" dominant-baseline="middle">${{label}}</text>`}}).join(""),dots=values.map((v,i)=>{{const p=miniPoint(i,v);return `<circle class="mini-dot" cx="${{p[0]}}" cy="${{p[1]}}" r="2.7"></circle>`}}).join("");node.innerHTML=`<svg viewBox="0 0 100 100" role="img"><polygon class="mini-grid" points="${{miniPolygon(35)}}"></polygon><polygon class="mini-grid" points="${{miniPolygon(70)}}"></polygon><polygon class="mini-grid" points="${{miniPolygon(100)}}"></polygon>${{axes}}<polygon class="mini-shape" points="${{points}}"></polygon>${{dots}}</svg>`}});
  </script>
</body>
</html>
"""


def render_index(day: dt.date) -> str:
    date = day.isoformat()
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI 内容雷达</title>
  <meta http-equiv="refresh" content="0; url=./ai-project-radar-{date}.html">
</head>
<body>
  <main>
    <p>正在打开 AI 内容雷达。</p>
    <p><a href="./ai-project-radar-{date}.html">如果没有自动跳转，点击这里。</a></p>
  </main>
</body>
</html>
"""


def write_outputs(day: dt.date, items: list[dict]) -> dict:
    html_path = ROOT / f"ai-project-radar-{day.isoformat()}.html"
    html_path.write_text(render_html(day, items), encoding="utf-8")
    (ROOT / "index.html").write_text(render_index(day), encoding="utf-8")
    report_url = f"{BASE_URL}/ai-project-radar-{day.isoformat()}.html"
    summary = {
        "date": day.isoformat(),
        "title": f"AI 内容雷达 · {day.isoformat()}",
        "headline": "今日 AI 内容雷达已更新：多平台自动生成版。",
        "report_url": report_url,
        "top_items": [{"title": i["title"], "source": i["source"], "url": i["url"], "score": i["score"]} for i in items[:3]],
    }
    SUMMARY_PATH.parent.mkdir(exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Report date in YYYY-MM-DD")
    args = parser.parse_args()
    day = iso_today(args.date)
    config = json.loads(SOURCES_PATH.read_text(encoding="utf-8"))
    all_items: list[dict] = []
    all_items += safe_fetch("GitHub", lambda: fetch_github(config, day), [])
    all_items += safe_fetch("Hacker News", lambda: fetch_hn(config, day), [])
    all_items += safe_fetch("Hugging Face", lambda: fetch_hugging_face(day), [])
    all_items += safe_fetch("RSS", lambda: fetch_rss(config), [])
    items = select_items(dedupe(all_items), limit=9)
    if not items:
        raise SystemExit("No radar items collected.")
    summary = write_outputs(day, items)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
