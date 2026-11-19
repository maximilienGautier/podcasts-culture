#!/usr/bin/env python3
"""Régénère site/feed.xml (RSS podcast avec balises iTunes) à partir des
épisodes du dépôt et des métadonnées attachées à leurs Releases.

    python feed.py                       # dépôt déduit de `gh repo view`
    python feed.py --repo moi/podcasts-culture
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import yaml

from build import ROOT, parse_episode
from publish import release_meta

ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
ATOM = "http://www.w3.org/2005/Atom"
ET.register_namespace("itunes", ITUNES)
ET.register_namespace("atom", ATOM)


def sub(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})
    if text is not None:
        el.text = str(text)
    return el


def detect_repo() -> str:
    if os.environ.get("GITHUB_REPOSITORY"):
        return os.environ["GITHUB_REPOSITORY"]
    r = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


def hms(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--repo")
    ap.add_argument("--out", type=Path, default=ROOT / "site")
    args = ap.parse_args()

    repo = args.repo or detect_repo()
    owner, name = repo.split("/")
    site_url = f"https://{owner.lower()}.github.io/{name}/"
    pod = yaml.safe_load((ROOT / "podcast.yaml").read_text(encoding="utf-8"))
    args.out.mkdir(parents=True, exist_ok=True)
    cover = ROOT / pod.get("cover", "cover.jpg")
    shutil.copy(cover, args.out / cover.name)
    (args.out / ".nojekyll").touch()

    rss = ET.Element("rss", {"version": "2.0"})
    ch = sub(rss, "channel")
    sub(ch, "title", pod["title"])
    sub(ch, "link", site_url)
    sub(ch, "description", pod["description"])
    sub(ch, "language", pod.get("language", "fr"))
    sub(ch, f"{{{ATOM}}}link", href=site_url + "feed.xml", rel="self", type="application/rss+xml")
    sub(ch, f"{{{ITUNES}}}author", pod["author"])
    sub(ch, f"{{{ITUNES}}}summary", pod["description"])
    sub(ch, f"{{{ITUNES}}}type", "episodic")
    sub(ch, f"{{{ITUNES}}}explicit", "false")
    sub(ch, f"{{{ITUNES}}}image", href=site_url + cover.name)
    ET.SubElement(ch, f"{{{ITUNES}}}category", {"text": pod.get("category", "Education")})
    if pod.get("block"):
        sub(ch, f"{{{ITUNES}}}block", "Yes")
    img = sub(ch, "image")
    sub(img, "url", site_url + cover.name)
    sub(img, "title", pod["title"])
    sub(img, "link", site_url)

    items = []
    for md in sorted((ROOT / "episodes").glob("*.md"), reverse=True):
        tag = md.stem
        meta, _ = parse_episode(md)
        info = release_meta(tag)
        if not info:
            print(f"! {tag} : pas encore de Release, ignoré")
            continue
        items.append((meta, info, tag))

    for meta, info, tag in items:
        it = sub(ch, "item")
        sub(it, "title", meta["title"])
        desc = meta["description"]
        if len(info.get("chapters", [])) > 1:
            desc += "\n\n" + "\n".join(f"{hms(c['start'])} {c['title']}" for c in info["chapters"])
        sub(it, "description", desc)
        sub(it, f"{{{ITUNES}}}summary", desc)
        pub = datetime.fromisoformat(meta["date"][:10]).replace(hour=6, tzinfo=timezone.utc)
        sub(it, "pubDate", format_datetime(pub))
        sub(it, "guid", f"{repo}/{tag}", isPermaLink="false")
        url = f"https://github.com/{repo}/releases/download/{tag}/{tag}.mp3"
        sub(it, "enclosure", url=url, length=info["bytes"], type="audio/mpeg")
        sub(it, "link", f"https://github.com/{repo}/releases/tag/{tag}")
        sub(it, f"{{{ITUNES}}}duration", int(round(info["duration"])))
        sub(it, f"{{{ITUNES}}}episodeType", "full")
        sub(it, f"{{{ITUNES}}}explicit", "false")

    if items:
        last = max(datetime.fromisoformat(m["date"][:10]) for m, _, _ in items)
        sub(ch, "lastBuildDate", format_datetime(last.replace(hour=6, tzinfo=timezone.utc)))

    ET.indent(rss)
    xml = ET.tostring(rss, encoding="unicode", xml_declaration=False)
    (args.out / "feed.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + xml + "\n",
                                       encoding="utf-8")
    print(f"→ {args.out / 'feed.xml'} : {len(items)} épisode(s), {site_url}feed.xml")


if __name__ == "__main__":
    main()
