# podcasts-culture

Pipeline gratuit : un script Markdown devient un épisode MP3 à deux voix,
publié dans un flux RSS que l'on écoute dans Apple Podcasts.
Il n'y a ni service payant, ni clé d'API, ni serveur.

**Flux :** https://maximiliengautier.github.io/podcasts-culture/feed.xml

```
episodes/AAAA-MM-JJ-slug.md ──push──▶ GitHub Actions
                                       ├─ build.py   → MP3 (edge-tts + ffmpeg)
                                       ├─ publish.py → une Release par épisode
                                       └─ feed.py    → feed.xml sur GitHub Pages
```

## Fichiers

| Fichier | Rôle |
|---|---|
| `episodes/*.md` | Scripts des épisodes (format : voir `GUIDE-SCRIPT.md`). |
| `voices.yaml` | Moteur, voix, vitesse, pauses, volume cible. |
| `podcast.yaml` | Titre, auteur, description et pochette du flux. |
| `engines.py` | Moteurs de voix : une classe par moteur (Edge, Piper, test). |
| `build.py` | Script vers MP3 : synthèse, pauses, concaténation ffmpeg, normalisation, chapitres. |
| `samples.py` | Le même extrait de 20 secondes avec six voix, pour choisir. |
| `publish.py` | Crée ou met à jour la Release de chaque épisode nouveau ou modifié. |
| `feed.py` | Génère `site/feed.xml` (RSS 2.0 et balises iTunes). |
| `GUIDE-SCRIPT.md` | Consignes d'écriture pour Claude. |

## Utilisation en local

Prérequis : Python 3.10 ou plus récent, et ffmpeg (`brew install ffmpeg` sur Mac).

```bash
pip install -r requirements.txt
python build.py episodes/2026-11-19-invention-du-metre.md   # → build/….mp3
python build.py --engine test episodes/x.md   # hors ligne : des bips à la place des voix, pour tester le format
python samples.py                              # → samples/1-vivienne.mp3 … 6-jerome.mp3
python samples.py --rate "+10%"
```

Chaque réplique synthétisée est mise en cache dans `.cache/tts/`. Relancer après une
correction ne régénère que les répliques modifiées.

Sortie : MP3 mono à 64 kbit/s et 44,1 kHz, volume normalisé à −16 LUFS (EBU R128,
une seule passe), avec des chapitres ID3 tirés des titres `##`. Un fichier
`build/<slug>.json` donne la durée, le nombre de mots et le débit en mots par minute.

## Réglages

Tout se règle dans `voices.yaml` :

- `rate` : vitesse globale (`"+10%"` = 10 % plus rapide). On peut aussi la régler voix par voix.
- `pauses.replique` et `pauses.chapitre` : en millisecondes.
- `voices.CAMILLE.edge`, `voices.THOMAS.edge` : nom de la voix Edge. Pour voir toutes
  les voix françaises : `edge-tts --list-voices | grep fr-`.
- Pour ajouter un locuteur, ajoute une entrée sous `voices:`. Le nom doit être en
  majuscules, comme dans le script.

## Échantillons de voix sans ordinateur

Onglet **Actions** → « Échantillons de voix » → **Run workflow**. Les extraits sont
attachés à la Release « echantillons » du dépôt, et on peut les écouter depuis
l'iPhone. Si une voix n'est pas proposée par edge-tts, elle est signalée et ignorée.

## Publication

À chaque push qui touche `episodes/`, `podcast.yaml` ou `cover.jpg`, le workflow
`publish.yml` effectue trois étapes :

1. Il regénère seulement les épisodes nouveaux ou modifiés. Pour le savoir, il compare
   l'empreinte SHA-256 du script avec celle enregistrée dans la Release.
2. Il attache `<slug>.mp3` et `<slug>.json` à la Release `<slug>`.
3. Il reconstruit `feed.xml` à partir de tous les épisodes présents dans `episodes/`
   et le déploie sur GitHub Pages.

Pour tout regénérer, par exemple après un changement de voix : Actions → « Publier
les épisodes » → Run workflow, en cochant « Régénérer tous les MP3 ».

Pour retirer un épisode du flux, supprime son fichier `.md`. La Release reste ; on
peut la supprimer à la main.

## Confidentialité

Le dépôt est public pour que GitHub Pages reste gratuit. Le flux porte
`<itunes:block>Yes</itunes:block>` et n'est inscrit dans aucun annuaire : il est
**non répertorié**, mais pas secret. Toute personne qui connaît l'URL ou visite le
dépôt peut écouter les épisodes.

## Passer à Piper si edge-tts ne fonctionne plus

edge-tts utilise le service de lecture à voix haute du navigateur Edge, sans
garantie de la part de Microsoft. Si ce service est bloqué, on peut passer à
[Piper](https://github.com/OHF-Voice/piper1-gpl) : il est local, gratuit, et propose des
voix françaises (`fr_FR-siwis-medium`, `fr_FR-tom-medium`, `fr_FR-upmc-medium`…).

L'interface est prête : `PiperEngine` dans `engines.py`, et la clé `piper:` de chaque
voix dans `voices.yaml`. Il reste à faire :

1. Ajouter `piper-tts` à `requirements.txt`.
2. Écrire `PiperEngine.synthesize`. Elle doit télécharger le modèle s'il manque
   (`python -m piper.download_voices <voix>`), puis lancer
   `piper -m <voix> --length-scale <1/vitesse> -f <sortie.wav>` avec le texte sur
   l'entrée standard. `rate_to_factor()` convertit la vitesse.
3. Mettre `engine: piper` dans `voices.yaml`.
4. Dans le workflow, mettre les modèles en cache (`actions/cache` sur le dossier des
   voix) pour ne pas les retélécharger à chaque fois.

La qualité de Piper est nettement inférieure à celle des voix neuronales d'Edge, mais
il ne dépend d'aucun service.
