#!/usr/bin/env python3
"""Fetch X posts for the Daily AI Content Radar.

The script reads X_BEARER_TOKEN from the local .env.ai-radar file and writes a
sanitized JSON payload for the report generator. It never prints the token.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
ENV_PATH = PROJECT_ROOT / ".env.ai-radar"
X_SOURCES_PATH = ROOT / "data" / "x-sources.json"
OUT_DIR = ROOT / "data" / "x"
USER_AGENT = "ai-radar-x-fetch/1.0"


def load_env(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def x_request(path: str, token: str, params: dict[str, str] | None = None) -> dict:
    url = "https://api.x.com/2/" + path.lstrip("/")
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def account_handles(config: dict) -> list[str]:
    handles: list[str] = []
    for account in config.get("priority_accounts", []):
        url = account.get("url", "")
        handle = url.rstrip("/").rsplit("/", 1)[-1].strip()
        if handle and handle not in handles:
            handles.append(handle)
    return handles


def public_metrics_score(tweet: dict) -> int:
    metrics = tweet.get("public_metrics") or {}
    likes = int(metrics.get("like_count") or 0)
    reposts = int(metrics.get("retweet_count") or 0)
    replies = int(metrics.get("reply_count") or 0)
    quotes = int(metrics.get("quote_count") or 0)
    return likes + reposts * 2 + replies * 2 + quotes * 2


def normalize_tweet(tweet: dict, author: dict, source_query: str) -> dict:
    username = author.get("username") or "unknown"
    tweet_id = tweet.get("id", "")
    metrics = tweet.get("public_metrics") or {}
    text = " ".join((tweet.get("text") or "").split())
    return {
        "id": tweet_id,
        "author_name": author.get("name") or username,
        "author_username": username,
        "created_at": tweet.get("created_at"),
        "text": text,
        "url": f"https://x.com/{username}/status/{tweet_id}" if tweet_id else "",
        "source_query": source_query,
        "public_metrics": {
            "likes": int(metrics.get("like_count") or 0),
            "reposts": int(metrics.get("retweet_count") or 0),
            "replies": int(metrics.get("reply_count") or 0),
            "quotes": int(metrics.get("quote_count") or 0),
        },
        "quality_score": public_metrics_score(tweet),
    }


def fetch_account_posts(token: str, handles: list[str], max_accounts: int) -> tuple[list[dict], list[dict]]:
    posts: list[dict] = []
    filtered: list[dict] = []
    for handle in handles[:max_accounts]:
        try:
            user_data = x_request(
                f"users/by/username/{handle}",
                token,
                {"user.fields": "id,name,username,verified"},
            )
            user = user_data.get("data") or {}
            user_id = user.get("id")
            if not user_id:
                filtered.append({"source": handle, "reason": "user_not_found"})
                continue
            data = x_request(
                f"users/{user_id}/tweets",
                token,
                {
                    "max_results": "5",
                    "exclude": "retweets,replies",
                    "tweet.fields": "created_at,public_metrics,lang",
                },
            )
            for tweet in data.get("data") or []:
                text = tweet.get("text") or ""
                if len(text.strip()) < 40:
                    filtered.append({"source": handle, "tweet_id": tweet.get("id"), "reason": "too_short"})
                    continue
                posts.append(normalize_tweet(tweet, user, f"account:{handle}"))
            time.sleep(0.8)
        except urllib.error.HTTPError as exc:
            filtered.append({"source": handle, "reason": f"http_{exc.code}"})
        except Exception as exc:  # noqa: BLE001 - keep batch fetch resilient.
            filtered.append({"source": handle, "reason": exc.__class__.__name__})
    return posts, filtered


def fetch_search_posts(token: str, queries: list[str], max_queries: int) -> tuple[list[dict], list[dict]]:
    posts: list[dict] = []
    filtered: list[dict] = []
    for query in queries[:max_queries]:
        try:
            data = x_request(
                "tweets/search/recent",
                token,
                {
                    "query": f"({query}) -is:retweet -is:reply",
                    "max_results": "10",
                    "tweet.fields": "created_at,public_metrics,author_id,lang",
                    "expansions": "author_id",
                    "user.fields": "name,username,verified",
                },
            )
            users = {user["id"]: user for user in data.get("includes", {}).get("users", [])}
            for tweet in data.get("data") or []:
                author = users.get(tweet.get("author_id"), {"username": "unknown"})
                text = tweet.get("text") or ""
                if len(text.strip()) < 40:
                    filtered.append({"source": query, "tweet_id": tweet.get("id"), "reason": "too_short"})
                    continue
                posts.append(normalize_tweet(tweet, author, f"search:{query}"))
            time.sleep(0.8)
        except urllib.error.HTTPError as exc:
            filtered.append({"source": query, "reason": f"http_{exc.code}"})
        except Exception as exc:  # noqa: BLE001
            filtered.append({"source": query, "reason": exc.__class__.__name__})
    return posts, filtered


def dedupe_posts(posts: list[dict]) -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for post in sorted(posts, key=lambda item: item.get("quality_score", 0), reverse=True):
        key = post.get("id") or post.get("url")
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(post)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date().isoformat())
    parser.add_argument("--max-accounts", type=int, default=8)
    parser.add_argument("--max-queries", type=int, default=2)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    env = load_env(ENV_PATH)
    token = env.get("X_BEARER_TOKEN") or os.environ.get("X_BEARER_TOKEN")
    if not token:
        print(json.dumps({"status": "missing_token"}, ensure_ascii=False))
        return 2

    config = json.loads(X_SOURCES_PATH.read_text(encoding="utf-8"))
    status = {"date": args.date, "status": "ok", "api": "x", "token": "present"}
    account_posts, account_filtered = fetch_account_posts(token, account_handles(config), args.max_accounts)
    search_posts, search_filtered = fetch_search_posts(token, config.get("search_queries", []), args.max_queries)
    posts = dedupe_posts(account_posts + search_posts)[: args.limit]
    payload = {
        **status,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "target_count": config.get("target_count"),
        "posts": posts,
        "filtered": account_filtered + search_filtered,
        "counts": {
            "posts": len(posts),
            "filtered": len(account_filtered) + len(search_filtered),
            "account_candidates": len(account_posts),
            "search_candidates": len(search_posts),
        },
        "standalone_x_page_recommended": len(posts) >= 5,
    }
    if not args.dry_run:
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        (OUT_DIR / f"{args.date}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "status": payload["status"],
        "date": payload["date"],
        "posts": payload["counts"]["posts"],
        "filtered": payload["counts"]["filtered"],
        "standalone_x_page_recommended": payload["standalone_x_page_recommended"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
