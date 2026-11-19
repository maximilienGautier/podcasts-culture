"""Moteurs de synthèse vocale interchangeables.

Chaque moteur est une classe qui sait transformer un texte en fichier audio
avec une voix donnée. build.py et samples.py ne connaissent que l'interface
Engine : changer de moteur se fait dans voices.yaml (clé engine) ou avec
l'option --engine.
"""

from __future__ import annotations

import asyncio
import hashlib
import subprocess
import sys
import time
from abc import ABC, abstractmethod
from pathlib import Path


class Engine(ABC):
    #: nom utilisé dans voices.yaml (clé engine, et clé de voix par locuteur)
    name: str = ""
    #: extension du fichier produit par synthesize()
    ext: str = "wav"

    @abstractmethod
    def synthesize(self, text: str, voice: str, rate: str, out_path: Path) -> None:
        """Écrit dans out_path l'audio de `text` prononcé par `voice`.

        `rate` suit la convention edge-tts ("+0%", "-10%", "+15%") ; chaque
        moteur la traduit dans ses propres réglages.
        """

    def voice_for(self, speaker_cfg: dict) -> str:
        try:
            return speaker_cfg[self.name]
        except KeyError:
            raise SystemExit(
                f"voices.yaml : pas de voix « {self.name} » définie pour ce locuteur : {speaker_cfg}"
            )

    def cache_key(self, text: str, voice: str, rate: str) -> str:
        h = hashlib.sha256(f"{self.name}|{voice}|{rate}|{text}".encode()).hexdigest()
        return h[:24]


def rate_to_factor(rate: str) -> float:
    """"+10%" -> 1.10 ; "-20%" -> 0.80."""
    rate = (rate or "+0%").strip().rstrip("%")
    return 1 + float(rate) / 100


class EdgeEngine(Engine):
    """Voix neuronales de Microsoft Edge, via le paquet edge-tts (gratuit, sans clé)."""

    name = "edge"
    ext = "mp3"

    def __init__(self, retries: int = 6, base_delay: float = 2.0):
        self.retries = retries
        self.base_delay = base_delay

    async def _run(self, text: str, voice: str, rate: str, out_path: Path) -> None:
        import edge_tts

        await edge_tts.Communicate(text, voice, rate=rate).save(str(out_path))

    def synthesize(self, text: str, voice: str, rate: str, out_path: Path) -> None:
        tmp = out_path.with_suffix(".part")
        for attempt in range(1, self.retries + 1):
            try:
                asyncio.run(self._run(text, voice, rate, tmp))
                if tmp.stat().st_size == 0:
                    raise RuntimeError("fichier audio vide")
                tmp.replace(out_path)
                return
            except Exception as exc:  # réseau, limitation de débit, réponse vide…
                tmp.unlink(missing_ok=True)
                if attempt == self.retries:
                    raise RuntimeError(
                        f"edge-tts a échoué {self.retries} fois ({voice}) : {exc}"
                    ) from exc
                delay = self.base_delay * 2 ** (attempt - 1)
                print(f"  edge-tts, essai {attempt} raté ({exc!r}), nouvel essai dans {delay:.0f} s",
                      file=sys.stderr)
                time.sleep(delay)


class PiperEngine(Engine):
    """Piper : synthèse locale, gratuite, hors ligne. Solution de repli.

    Pas encore branché : voir la section « Passer à Piper » du README.
    Esquisse de l'implémentation :
        pip install piper-tts
        python -m piper.download_voices fr_FR-siwis-medium
        echo "texte" | piper -m fr_FR-siwis-medium --length-scale 1.0 -f out.wav
    avec length_scale = 1 / rate_to_factor(rate).
    """

    name = "piper"
    ext = "wav"

    def synthesize(self, text: str, voice: str, rate: str, out_path: Path) -> None:
        raise NotImplementedError(
            "Le moteur Piper n'est pas encore implémenté : voir « Passer à Piper » dans le README."
        )


class ToneEngine(Engine):
    """Moteur factice, hors ligne : un bip dont la durée imite la parole.

    Sert seulement à tester la chaîne (pauses, concaténation, chapitres,
    encodage) sans réseau : python build.py --engine test episodes/x.md
    """

    name = "test"
    ext = "wav"
    words_per_minute = 160

    def voice_for(self, speaker_cfg: dict) -> str:
        return speaker_cfg.get("edge", "test")

    def synthesize(self, text: str, voice: str, rate: str, out_path: Path) -> None:
        words = len(text.split())
        seconds = words / self.words_per_minute * 60 / rate_to_factor(rate)
        freq = 300 + int(hashlib.md5(voice.encode()).hexdigest(), 16) % 400
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-f", "lavfi",
             "-i", f"sine=frequency={freq}:duration={seconds:.2f}:sample_rate=24000",
             "-af", "volume=0.3", str(out_path)],
            check=True,
        )


ENGINES = {cls.name: cls for cls in (EdgeEngine, PiperEngine, ToneEngine)}


def get_engine(name: str) -> Engine:
    try:
        return ENGINES[name]()
    except KeyError:
        raise SystemExit(f"Moteur inconnu : {name}. Choix : {', '.join(ENGINES)}")
