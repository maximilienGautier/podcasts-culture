#!/usr/bin/env python3
"""Génère le même extrait d'environ 20 secondes avec plusieurs voix edge-tts,
pour les comparer à l'oreille.

    python samples.py                 # → samples/<voix>.mp3
    python samples.py --rate "+10%"   # même chose, en plus rapide

Une voix indisponible est signalée puis ignorée.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from engines import EdgeEngine

VOICES = {
    "vivienne": "fr-FR-VivienneMultilingualNeural",
    "remy": "fr-FR-RemyMultilingualNeural",
    "denise": "fr-FR-DeniseNeural",
    "henri": "fr-FR-HenriNeural",
    "eloise": "fr-FR-EloiseNeural",
    "jerome": "fr-FR-JeromeNeural",
}

TEXT = (
    "En dix-sept cent quatre-vingt-onze, l'Académie des sciences propose une unité "
    "tirée de la nature : la dix-millionième partie du quart du méridien terrestre. "
    "Pendant six ans, deux astronomes, Delambre et Méchain, mesurent l'arc entre "
    "Dunkerque et Barcelone. Le résultat ? Un mètre étalon en platine, trop court "
    "d'environ deux dixièmes de millimètre. Pas mal, pour l'époque, non ?"
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rate", default="+0%")
    ap.add_argument("--out", type=Path, default=Path("samples"))
    args = ap.parse_args()
    args.out.mkdir(exist_ok=True)

    engine = EdgeEngine(retries=3)
    ok = 0
    for i, (name, voice) in enumerate(VOICES.items(), 1):
        path = args.out / f"{i}-{name}.mp3"
        try:
            engine.synthesize(TEXT, voice, args.rate, path)
            print(f"✓ {path}  ({voice})")
            ok += 1
        except Exception as exc:
            print(f"✗ {name} ({voice}) indisponible : {exc}")
    if ok == 0:
        raise SystemExit("Aucune voix n'a fonctionné (réseau ?)")


if __name__ == "__main__":
    main()
