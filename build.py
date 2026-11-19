#!/usr/bin/env python3
"""Transforme un script d'épisode Markdown en MP3 à deux voix.

    python build.py episodes/2026-11-19-exemple.md
    python build.py episodes/x.md -o /tmp/x.mp3 --engine test

Produit build/<slug>.mp3 (mono, 64 kbit/s, volume normalisé, chapitres ID3)
et build/<slug>.json (durée, nombre de mots, empreinte du script).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import wave
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from engines import get_engine

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / ".cache" / "tts"
SAMPLE_RATE = 24000          # fréquence de travail (celle d'edge-tts)
OUT_SAMPLE_RATE = 44100      # fréquence du MP3 final, la plus compatible
BITRATE = "64k"

LINE_RE = re.compile(r"^([A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜ][A-ZÀÂÄÇÉÈÊËÎÏÔÖÙÛÜ\-]*)\s*:\s*(.+)$", re.S)


# --------------------------------------------------------------------------- lecture

@dataclass
class Line:
    speaker: str
    text: str


@dataclass
class Chapter:
    title: str | None
    lines: list[Line] = field(default_factory=list)


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[*_`]+", "", text)           # restes de Markdown éventuels
    return text


def parse_episode(path: Path) -> tuple[dict, list[Chapter]]:
    raw = path.read_text(encoding="utf-8")
    meta: dict = {}
    if raw.startswith("---"):
        _, front, raw = raw.split("---", 2)
        meta = yaml.safe_load(front) or {}
    for key in ("title", "date", "description"):
        if key not in meta:
            raise SystemExit(f"{path} : clé « {key} » absente de l'en-tête YAML")
    meta["date"] = str(meta["date"])

    raw = re.sub(r"<!--.*?-->", "", raw, flags=re.S)  # commentaires ignorés
    chapters = [Chapter(None)]
    paragraph: list[str] = []
    errors: list[str] = []

    def flush(lineno: int) -> None:
        if not paragraph:
            return
        text = " ".join(paragraph)
        paragraph.clear()
        m = LINE_RE.match(text)
        if not m:
            errors.append(f"ligne {lineno} : paragraphe sans « NOM: » → {text[:60]}…")
            return
        chapters[-1].lines.append(Line(m.group(1), clean_text(m.group(2))))

    lines = raw.splitlines()
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("## "):
            flush(i)
            chapters.append(Chapter(s[3:].strip()))
        elif s.startswith("# "):        # titre de niveau 1 : ignoré
            flush(i)
        elif not s:
            flush(i)
        else:
            paragraph.append(s)
    flush(len(lines))

    if errors:
        raise SystemExit(f"{path} :\n  " + "\n  ".join(errors))
    chapters = [c for c in chapters if c.lines]
    if not chapters:
        raise SystemExit(f"{path} : aucune réplique trouvée")
    return meta, chapters


# --------------------------------------------------------------------------- audio

def ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", *args], check=True)


def to_wav(src: Path, dst: Path) -> float:
    ffmpeg("-i", str(src), "-ac", "1", "-ar", str(SAMPLE_RATE), "-sample_fmt", "s16", str(dst))
    return wav_duration(dst)


def wav_duration(path: Path) -> float:
    with wave.open(str(path)) as w:
        return w.getnframes() / w.getframerate()


def write_silence(path: Path, ms: int) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(b"\x00\x00" * int(SAMPLE_RATE * ms / 1000))


def load_config() -> dict:
    return yaml.safe_load((ROOT / "voices.yaml").read_text(encoding="utf-8"))


def build(episode: Path, out: Path | None = None, engine_name: str | None = None,
          jobs: int = 4) -> dict:
    cfg = load_config()
    meta, chapters = parse_episode(episode)
    engine = get_engine(engine_name or cfg.get("engine", "edge"))
    voices = cfg["voices"]
    pauses = cfg.get("pauses", {})
    slug = episode.stem
    out = out or ROOT / "build" / f"{slug}.mp3"
    out.parent.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)

    # 1. Synthèse de chaque réplique (en parallèle, avec cache sur disque).
    jobs_list = []
    for ch in chapters:
        for ln in ch.lines:
            if ln.speaker not in voices:
                raise SystemExit(f"Locuteur inconnu « {ln.speaker} » : ajoutez-le dans voices.yaml")
            spk = voices[ln.speaker]
            voice = engine.voice_for(spk)
            rate = spk.get("rate", cfg.get("rate", "+0%"))
            key = engine.cache_key(ln.text, voice, rate)
            jobs_list.append((ln, voice, rate, CACHE / f"{key}.{engine.ext}"))

    todo = [j for j in jobs_list if not j[3].exists()]
    print(f"{slug} : {len(jobs_list)} répliques, {len(todo)} à synthétiser ({engine.name})")

    def run(job):
        ln, voice, rate, path = job
        engine.synthesize(ln.text, voice, rate, path)

    done = 0
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        for _ in pool.map(run, todo):
            done += 1
            if done % 20 == 0 or done == len(todo):
                print(f"  {done}/{len(todo)}")

    # 2. Conversion en WAV commun, pauses, liste de concaténation, chapitres.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        short, long_ = tmp / "pause.wav", tmp / "pause_chapitre.wav"
        write_silence(short, pauses.get("replique", 350))
        write_silence(long_, pauses.get("chapitre", 1300))
        short_d, long_d = wav_duration(short), wav_duration(long_)

        concat: list[Path] = []
        marks: list[tuple[str, float]] = []
        t = 0.0
        idx = 0
        for ci, ch in enumerate(chapters):
            if ci > 0:
                concat.append(long_)
                t += long_d
            marks.append((ch.title or meta["title"], t))
            for li, _ in enumerate(ch.lines):
                if li > 0:
                    concat.append(short)
                    t += short_d
                src = jobs_list[idx][3]
                idx += 1
                wav = tmp / f"{idx:05d}.wav"
                t += to_wav(src, wav)
                concat.append(wav)
        total = t

        listfile = tmp / "list.txt"
        listfile.write_text("".join(f"file '{p}'\n" for p in concat))

        md = [";FFMETADATA1",
              f"title={esc(meta['title'])}",
              f"artist={esc(load_podcast().get('author', ''))}",
              f"album={esc(load_podcast().get('title', ''))}",
              f"date={meta['date'][:4]}", "genre=Podcast"]
        for i, (title, start) in enumerate(marks):
            end = marks[i + 1][1] if i + 1 < len(marks) else total
            md += ["[CHAPTER]", "TIMEBASE=1/1000", f"START={int(start * 1000)}",
                   f"END={int(end * 1000)}", f"title={esc(title)}"]
        metafile = tmp / "meta.txt"
        metafile.write_text("\n".join(md) + "\n", encoding="utf-8")

        # 3. Concaténation, normalisation du volume, encodage MP3 mono 64k.
        loud = cfg.get("loudness", -16)
        ffmpeg("-f", "concat", "-safe", "0", "-i", str(listfile),
               "-i", str(metafile), "-map", "0:a", "-map_metadata", "1", "-map_chapters", "1",
               "-af", f"loudnorm=I={loud}:TP=-1.5:LRA=11",
               "-ac", "1", "-ar", str(OUT_SAMPLE_RATE),
               "-c:a", "libmp3lame", "-b:a", BITRATE, "-id3v2_version", "3",
               str(out))

    words = sum(len(ln.text.split()) for ch in chapters for ln in ch.lines)
    info = {
        "slug": slug,
        "title": meta["title"],
        "date": meta["date"],
        "description": meta["description"],
        "duration": round(probe_duration(out), 2),
        "bytes": out.stat().st_size,
        "words": words,
        "chapters": [{"title": t_, "start": round(s, 2)} for t_, s in marks],
        "source_sha256": hashlib.sha256(episode.read_bytes()).hexdigest(),
        "engine": engine.name,
    }
    out.with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False, indent=2))
    mins = info["duration"] / 60
    print(f"→ {out}  {mins:.1f} min, {words} mots, {words / mins:.0f} mots/min, "
          f"{info['bytes'] / 1e6:.1f} Mo, {len(marks)} chapitre(s)")
    return info


def esc(s: str) -> str:
    return re.sub(r"([=;#\\\n])", r"\\\1", str(s))


def load_podcast() -> dict:
    return yaml.safe_load((ROOT / "podcast.yaml").read_text(encoding="utf-8"))


def probe_duration(path: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(path)], capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("episode", type=Path)
    ap.add_argument("-o", "--output", type=Path)
    ap.add_argument("--engine", help="edge, piper ou test (par défaut : voices.yaml)")
    ap.add_argument("--jobs", type=int, default=4, help="synthèses en parallèle (défaut 4)")
    args = ap.parse_args()
    build(args.episode, args.output, args.engine, args.jobs)


if __name__ == "__main__":
    sys.exit(main())
