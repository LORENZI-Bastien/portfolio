# Point politique quotidien

Chaque matin (7 h 30 par défaut), un message Discord résume ce qui s'est passé au Parlement depuis la veille, à partir des **données publiques officielles uniquement** :

| Rubrique | Source officielle |
|---|---|
| 🏛️ Votes de l'Assemblée nationale (adopté / rejeté, pour / contre / abstentions) | Open data de l'Assemblée : fichier des scrutins de la 17e législature, mis à jour chaque jour |
| 🏛️ Votes du Sénat (adoption / rejet) | Liste officielle des scrutins publics de la session sur senat.fr |
| 📜 Panorama des lois (lois promulguées, textes en cours) | Flux « Panorama des lois » de vie-publique.fr (DILA, service du Premier ministre) |
| 📥 Nouveaux textes déposés au Sénat | Flux RSS « derniers textes » du Sénat |
| 🧠 Contexte (facultatif) | 3 à 5 phrases écrites par l'IA locale **à partir des seuls faits ci-dessus**, consigne de neutralité stricte |

**Qui a voté quoi (masqué par défaut)** : sous chaque vote important, une ligne cachée (spoiler Discord, case noire) donne le vote de chaque groupe, par exemple `RN ✅120 ⚪2 · LFI-NFP ❌71`. Il faut cliquer dessus pour l'afficher. Un fichier `votes-AAAA-MM-JJ.txt` joint au message donne, groupe par groupe, le nom de chaque député ou sénateur qui a voté pour, contre, s'est abstenu ou n'a pas voté ; Discord l'affiche replié, on l'ouvre si on veut. Sources : vote nominatif dans l'open data de l'Assemblée (noms et sigles des groupes via la liste officielle des députés, mise en cache une semaine) et page officielle de chaque scrutin du Sénat.

Les votes « qui comptent » sont mis en avant : vote sur l'ensemble d'un texte, scrutin solennel, motion de censure ou de rejet, conclusions de commission mixte paritaire, déclaration du Gouvernement. Les centaines de votes sur amendements sont seulement comptés (« 143 autres scrutins : 37 adoptés, 106 rejetés »).

Le service retient ce qu'il a déjà envoyé (`data/etat.json`) : pas de doublon, et le lundi le point couvre tout le week-end. Si une source est en panne, le message le dit et la rattrape le lendemain.

## Installation sur le Pi

```bash
cp -r politique-kit ~/pi-kit/politique && cd ~/pi-kit/politique
cp .env.example .env && chmod 600 .env
nano .env                       # coller le webhook Discord (jamais dans un chat)
docker compose build
docker compose run --rm point-politique python point_politique.py --dry-run   # aperçu, rien n'est envoyé
docker compose run --rm point-politique python point_politique.py --once      # premier vrai envoi
docker compose up -d            # ensuite tous les jours à HEURE_ENVOI
docker logs -f point-politique
```

Aucun port ouvert, aucun compte, aucune clé d'API : seules des requêtes sortantes vers les sites officiels et Discord.

## IA locale (facultatif)

`OLLAMA_URL` doit pointer vers un Ollama joignable depuis le Pi. Sur la tour, Ollama n'écoute que sur la machine elle-même : il faudrait le faire écouter sur l'adresse Tailscale (variable `OLLAMA_HOST`) et le limiter au Pi par le pare-feu Windows. La tour étant éteinte la nuit, le paragraphe sera souvent absent à 7 h 30 : c'est prévu, le reste du point part quand même.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Tests hors ligne sur des exemples au format réel des sources (zip de l'Assemblée, page du Sénat, flux RSS en ISO-8859-15), état anti-doublon, découpage Discord (2 000 caractères max) et source en panne.

## Limites connues

- Les pages des scrutins du Sénat sont du HTML : si le Sénat change sa mise en page, la rubrique Sénat affichera « injoignable » ou perdra le détail par groupe, sans bloquer le reste.
- Le détail nominatif n'est donné que pour les votes mis en avant (pas pour les centaines d'amendements).
- Un député qui a quitté l'Assemblée apparaît sous sa référence officielle (« ancien député PA… ») car la liste utilisée ne contient que les députés en exercice.
- Le Journal officiel (Légifrance) demande un compte PISTE : non utilisé. Les lois promulguées arrivent par vie-publique, qui suit chaque loi jusqu'à sa publication.
- Le « contexte » IA est un résumé automatique : à vérifier sur les liens.
