# Guide d'écriture des épisodes

Ce guide est destiné à Claude, qui écrit les scripts d'épisodes. Le script est lu
tel quel par deux voix de synthèse : tout ce qui est écrit est prononcé.

## Longueur

- Durée visée : **30 à 40 minutes**.
- Débit mesuré sur l'épisode d'essai : **environ 166 mots par minute**, pauses comprises.
- Il faut donc **5 000 à 6 500 mots** de répliques, environ **5 800 mots pour 35 minutes**.
- Avant de rendre le script, compte les mots des répliques. Ne compte pas l'en-tête
  ni les titres de chapitres.

## Les deux voix

- **CAMILLE** pose les questions, relance, reformule et demande des exemples. Elle
  n'est pas naïve : ses questions sont celles d'une auditrice cultivée qui veut
  comprendre en profondeur. Elle résume parfois avant de passer à la suite.
- **THOMAS** est l'expert. Il explique, donne les dates, les noms, les mécanismes,
  les causes et les conséquences, et nuance quand les historiens ou les spécialistes
  ne sont pas d'accord.
- Les répliques de Thomas sont plus longues, de trois à six phrases. Celles de Camille
  sont courtes, d'une à deux phrases.
- Ils se coupent parfois la parole et réagissent : « Attends, tu veux dire que… »,
  « Justement, c'est là que ça se complique. » Ces échanges restent naturels et rares.
- Le ton reste sérieux. Pas de remplissage, pas de blagues forcées, pas de
  compliments du type « Excellente question ». Chaque réplique apporte quelque chose.

## Style oral

Le texte est écrit pour l'oreille.

- **Nombres, dates et sigles s'écrivent comme ils se prononcent.**
  - « dix-sept cent quatre-vingt-neuf » et non « 1789 », ou « mille sept cent
    quatre-vingt-neuf » selon l'usage le plus naturel.
  - « trois virgule cinq pour cent » et non « 3,5 % ».
  - « l'O-N-U » ou « l'ONU » selon la prononciation réelle : un sigle épelé s'écrit
    avec des tirets (« la S-N-C-F »), un sigle prononcé comme un mot s'écrit tel quel
    (« l'OTAN », « l'UNESCO »).
  - « le quinzième siècle » et non « le XVe siècle ».
  - « Louis Quatorze » et non « Louis XIV ».
- **Pas de Markdown dans les répliques** : ni gras, ni italique, ni listes, ni
  liens, ni parenthèses de renvoi.
- Des phrases courtes ou moyennes. On évite les incises imbriquées.
- Un nom propre peu connu est expliqué ou situé à sa première apparition.
- Les guillemets « » sont permis pour une citation courte.

## Structure

1. **Accroche** : avant le premier chapitre, deux à quatre répliques. On y met un fait
   frappant, une question ou un paradoxe, puis on annonce en une phrase ce que
   l'épisode va couvrir.
2. **Chapitres** : quatre à sept chapitres, chacun introduit par `## Titre du chapitre`.
   Ces titres deviennent les chapitres du MP3 et ne sont pas lus à voix haute.
   Chaque chapitre dure quatre à huit minutes.
3. **Récapitulatif** : un dernier chapitre `## Récapitulatif`. Camille et Thomas y
   reprennent les trois à cinq idées essentielles, puis proposent une ou deux pistes
   pour aller plus loin, comme un livre, un lieu ou une question ouverte.

## Format exact du fichier

Nom : `episodes/AAAA-MM-JJ-slug.md`. Le slug est en minuscules, sans accents, avec des
tirets. Exemple : `episodes/2026-11-24-canal-de-suez.md`.

```markdown
---
title: "Le canal de Suez"
date: 2026-11-24
description: "Une phrase ou deux qui résument l'épisode, affichées dans Apple Podcasts."
---

CAMILLE: Première réplique de l'accroche.

THOMAS: Réponse de Thomas.

## Titre du premier chapitre

CAMILLE: Question.

THOMAS: Réponse, qui peut faire plusieurs phrases
et même passer à la ligne : tant qu'il n'y a pas de ligne vide,
c'est la même réplique.

## Récapitulatif

CAMILLE: …
```

Règles :

- **Une réplique par paragraphe**, séparée de la suivante par une ligne vide.
- Chaque réplique commence par `CAMILLE:` ou `THOMAS:`, en majuscules.
- Tout paragraphe qui ne commence pas ainsi fait échouer la génération, sauf un
  titre `## …` ou un commentaire `<!-- … -->`.
- Les trois clés de l'en-tête sont obligatoires. La date est au format `AAAA-MM-JJ`.

## Publier l'épisode

Dépôt : `maximilienGautier/podcasts-culture`, branche `main`.

1. Crée le fichier `episodes/AAAA-MM-JJ-slug.md` dans le dépôt, avec l'outil GitHub
   disponible dans la conversation : création ou mise à jour de fichier, ou commit
   poussé sur `main`. Message de commit : `Épisode : <titre>`.
2. Le push déclenche le workflow « Publier les épisodes ». En cinq à dix minutes, il
   génère le MP3, crée la Release et met à jour le flux.
3. L'épisode apparaît ensuite dans Apple Podcasts. L'application peut mettre un
   moment à rafraîchir le flux. Pour forcer, tire vers le bas sur la page de
   l'émission.

Pour corriger un épisode déjà publié, modifie le même fichier et pousse-le à nouveau :
le MP3 est régénéré et remplacé. Ne change pas le nom du fichier, sinon l'épisode
apparaît en double.

Pour vérifier le format sans réseau, depuis un ordinateur :
`python build.py --engine test episodes/AAAA-MM-JJ-slug.md`.
