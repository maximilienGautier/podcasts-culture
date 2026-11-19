#!/usr/bin/env python3
"""Synchronise les épisodes avec les GitHub Releases (une Release par épisode).

Pour chaque episodes/*.md : si la Release n'existe pas, ou si le script a
changé depuis la dernière génération, reconstruit le MP3 et le (ré)attache.
Utilisé par le workflow ; marche aussi en local avec `gh` connecté.

    python publish.py            # seulement ce qui a changé
    python publish.py --force    # tout régénérer
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from build import ROOT, build, parse_episode


def gh(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def release_meta(tag: str) -> dict | None:
    """Métadonnées JSON attachées à la Release, ou None si elle n'existe pas."""
    if gh("release", "view", tag, check=False).returncode != 0:
        return None
    r = gh("release", "download", tag, "-p", f"{tag}.json", "-O", "-", check=False)
    if r.returncode != 0:
        return {}
    return json.loads(r.stdout)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    for md in sorted((ROOT / "episodes").glob("*.md")):
        tag = md.stem
        meta, _ = parse_episode(md)          # échoue tôt si le script est mal formé
        current = release_meta(tag)
        sha = hashlib.sha256(md.read_bytes()).hexdigest()
        if current and current.get("source_sha256") == sha and not args.force:
            print(f"= {tag} : à jour")
            continue

        info = build(md)
        mp3 = ROOT / "build" / f"{tag}.mp3"
        js = mp3.with_suffix(".json")
        notes = f"{meta['description']}\n\nDurée : {round(info['duration'] / 60)} min"
        if current is None:
            gh("release", "create", tag, str(mp3), str(js),
               "--title", meta["title"], "--notes", notes)
            print(f"+ {tag} : Release créée")
        else:
            gh("release", "upload", tag, str(mp3), str(js), "--clobber")
            gh("release", "edit", tag, "--title", meta["title"], "--notes", notes)
            print(f"~ {tag} : Release mise à jour")


if __name__ == "__main__":
    main()
