#!/usr/bin/env python3
"""Fetch and summarize robotics news from top RSS feeds."""

from __future__ import annotations

import json
import re
import ssl
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "data" / "news.json"

# Top voices: research labs, industry media, university news, community
SOURCES = [
    {
        "name": "arXiv Robotics",
        "voice": "Global Research",
        "url": "https://rss.arxiv.org/rss/cs.RO",
        "type": "research",
    },
    {
        "name": "IEEE Spectrum",
        "voice": "IEEE",
        "url": "https://spectrum.ieee.org/rss/fulltext",
        "type": "industry",
        "keywords": ["robot", "robotics", "autonomous", "drone", "manipulation", "humanoid"],
    },
    {
        "name": "MIT News",
        "voice": "MIT",
        "url": "https://news.mit.edu/rss/research",
        "type": "labs",
        "keywords": ["robot", "robotics", "autonomous", "manipulation", "locomotion", "drone"],
    },
    {
        "name": "Stanford HAI",
        "voice": "Stanford",
        "url": "https://hai.stanford.edu/news/feed",
        "type": "labs",
        "keywords": ["robot", "robotics", "autonomous", "manipulation", "embodied", "humanoid"],
    },
    {
        "name": "Berkeley AI Research",
        "voice": "UC Berkeley",
        "url": "https://bair.berkeley.edu/blog/feed.xml",
        "type": "labs",
        "keywords": ["robot", "robotics", "manipulation", "locomotion", "autonomous"],
    },
    {
        "name": "The Robot Report",
        "voice": "Industry",
        "url": "https://www.therobotreport.com/feed/",
        "type": "industry",
    },
    {
        "name": "TechCrunch Robotics",
        "voice": "Startup Scene",
        "url": "https://techcrunch.com/category/robotics/feed/",
        "type": "industry",
    },
    {
        "name": "Robohub",
        "voice": "Global Community",
        "url": "https://robohub.org/feed/",
        "type": "community",
    },
    {
        "name": "ROS Discourse",
        "voice": "Open Robotics / ROS",
        "url": "https://discourse.ros.org/latest.rss",
        "type": "community",
    },
]

ROBOTICS_KEYWORDS = (
    "robot",
    "robotics",
    "manipul",
    "locomotion",
    "humanoid",
    "autonomous",
    "embodied",
    "drone",
    "uav",
    "slam",
    "haptic",
    "gripper",
    "actuator",
)

MAX_ITEMS = 30
SUMMARY_LEN = 220
USER_AGENT = "shelf-robotics-news/1.0 (github.com/herronoui/reading-resources)"


def fetch_xml(url: str) -> ET.Element | None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for ctx in (ssl.create_default_context(), ssl._create_unverified_context()):
        try:
            with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
                data = resp.read()
            return ET.fromstring(data)
        except Exception:
            continue
    print(f"  skip {url}: fetch failed")
    return None


def strip_html(text: str) -> str:
    text = unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def summarize(text: str, title: str) -> str:
    text = strip_html(text)
    if not text:
        return f"Latest from the robotics community: {title}."

    # Prefer first complete sentences for a readable blurb
    sentences = re.split(r"(?<=[.!?])\s+", text)
    summary = ""
    for sentence in sentences:
        candidate = (summary + " " + sentence).strip()
        if len(candidate) > SUMMARY_LEN and summary:
            break
        summary = candidate
        if len(summary) >= 120:
            break

    if not summary:
        summary = text[:SUMMARY_LEN]

    if len(summary) > SUMMARY_LEN:
        summary = summary[: SUMMARY_LEN - 1].rsplit(" ", 1)[0] + "…"

    return summary


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value[: len(fmt.replace("%z", "+0000"))], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def find_child(parent: ET.Element, name: str) -> ET.Element | None:
    for child in parent:
        if local_tag(child.tag) == name:
            return child
    return None


def find_text(parent: ET.Element, name: str) -> str:
    node = find_child(parent, name)
    return (node.text or "").strip() if node is not None else ""


def matches_keywords(item: dict, keywords: list[str] | None) -> bool:
    if not keywords:
        return True
    blob = f"{item['title']} {item['summary']}".lower()
    return any(k.lower() in blob for k in keywords)


def parse_items(root: ET.Element, source: dict) -> list[dict]:
    items: list[dict] = []
    channel = root.find("channel")
    if channel is not None:
        entries = channel.findall("item")
    else:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        entries = root.findall("atom:entry", ns) or root.findall("entry")

    for entry in entries:
        if local_tag(entry.tag) == "item":
            title = find_text(entry, "title")
            link = find_text(entry, "link")
            if not link:
                link_node = find_child(entry, "link")
                if link_node is not None:
                    link = link_node.text or link_node.get("href") or ""
            desc = find_text(entry, "description") or find_text(entry, "content")
            pub = find_text(entry, "pubDate") or find_text(entry, "date")
        else:
            title = find_text(entry, "title")
            link = entry.get("href") or ""
            if not link:
                link_node = find_child(entry, "link")
                if link_node is not None:
                    link = link_node.get("href") or link_node.text or ""
            summary_node = find_child(entry, "summary") or find_child(entry, "content")
            desc = summary_node.text if summary_node is not None else ""
            pub = find_text(entry, "published") or find_text(entry, "updated")

        title = strip_html(title)
        link = link.strip()
        if not title or not link:
            continue

        published = parse_date(pub)
        item = {
            "title": title,
            "summary": summarize(desc, title),
            "source": source["name"],
            "voice": source["voice"],
            "type": source["type"],
            "url": link,
            "published": published.isoformat() if published else None,
        }
        if matches_keywords(item, source.get("keywords")):
            items.append(item)
    return items


def dedupe(items: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        key = re.sub(r"\W+", "", item["title"].lower())[:80]
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def main() -> None:
    all_items: list[dict] = []

    for source in SOURCES:
        print(f"Fetching {source['name']}…")
        root = fetch_xml(source["url"])
        if root is None:
            continue
        parsed = parse_items(root, source)
        print(f"  {len(parsed)} items")
        all_items.extend(parsed)

    all_items = dedupe(all_items)
    all_items.sort(key=lambda x: x.get("published") or "", reverse=True)
    all_items = all_items[:MAX_ITEMS]

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "item_count": len(all_items),
        "sources": [s["name"] for s in SOURCES],
        "items": all_items,
    }

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(all_items)} items to {OUTPUT}")


if __name__ == "__main__":
    main()
