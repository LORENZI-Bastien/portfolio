#!/usr/bin/env python3
"""Point politique quotidien : Assemblée nationale, Sénat, lois promulguées.

Récupère uniquement des données publiques officielles, garde ce qui est
nouveau depuis le dernier envoi et poste un résumé factuel sur Discord.
Résumé « contexte » facultatif par une IA locale (Ollama).

Python standard uniquement (aucune dépendance).

Usage :
  python point_politique.py --once --dry-run   # affiche sans envoyer ni mémoriser
  python point_politique.py --once             # envoie maintenant
  python point_politique.py                    # tourne en continu, envoi chaque jour à HEURE_ENVOI
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import html
import io
import json
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

# --------------------------------------------------------------------------
# Réglages (variables d'environnement)
# --------------------------------------------------------------------------
TZ = ZoneInfo(os.environ.get("TZ", "Europe/Paris"))
HEURE_ENVOI = os.environ.get("HEURE_ENVOI", "07:30")
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
ETAT = Path(os.environ.get("FICHIER_ETAT", "/data/etat.json"))
JOURS_PREMIER_ENVOI = int(os.environ.get("JOURS_PREMIER_ENVOI", "3"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "").strip().rstrip("/")
OLLAMA_MODELE = os.environ.get("OLLAMA_MODELE", "qwen3.5:4b")
MAX_DEPOTS = int(os.environ.get("MAX_DEPOTS", "6"))
UA = "point-politique/1.0 (homelab personnel; usage non commercial)"

URL_AN_SCRUTINS = ("https://data.assemblee-nationale.fr/static/openData/repository/"
                   "17/loi/scrutins/Scrutins.json.zip")
URL_AN_SCRUTIN = "https://www.assemblee-nationale.fr/dyn/17/scrutins/{n}"
URL_SENAT_SCRUTINS = "https://www.senat.fr/scrutin-public/scr{session}.html"
URL_SENAT_SCRUTIN = "https://www.senat.fr/scrutin-public/{session}/scr{session}-{n}.html"
URL_AN_DEPUTES = ("https://data.assemblee-nationale.fr/static/openData/repository/17/amo/"
                  "deputes_actifs_mandats_actifs_organes/AMO10_deputes_actifs_mandats_actifs_organes.json.zip")
URL_SENAT_TEXTES = "https://www.senat.fr/rss/textes.rss"
URL_VIE_PUBLIQUE_LOIS = "https://www.vie-publique.fr/lois-feeds.xml"

MOIS = {"janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
        "juin": 6, "juillet": 7, "août": 8, "aout": 8, "septembre": 9,
        "octobre": 10, "novembre": 11, "décembre": 12, "decembre": 12}
MOIS_EN = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


# --------------------------------------------------------------------------
# Outils
# --------------------------------------------------------------------------
def telecharger(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        brut = r.read()
        # vie-publique renvoie du gzip même sans Accept-Encoding
        if r.headers.get("Content-Encoding", "").lower() == "gzip" or brut[:2] == b"\x1f\x8b":
            brut = gzip.decompress(brut)
        return brut


def telecharger_fichier(url: str, timeout: int = 300) -> str:
    """Télécharge un gros fichier sur disque (évite de tout garder en RAM)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    fd, chemin = tempfile.mkstemp(suffix=".zip")
    with urllib.request.urlopen(req, timeout=timeout) as r, os.fdopen(fd, "wb") as f:
        while bloc := r.read(1 << 20):
            f.write(bloc)
    return chemin


def decoder_html(brut: bytes) -> str:
    m = re.search(rb'charset=["\']?([\w-]+)', brut[:2000], re.I)
    for enc in ([m.group(1).decode()] if m else []) + ["utf-8", "cp1252"]:
        try:
            return brut.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return brut.decode("utf-8", "replace")


def date_rss(texte: str) -> dt.date | None:
    """Gère « Fri, 06 Nov 2026 » et la variante du Sénat « Fri,06 Nov 2026 »."""
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})", texte or "")
    if m and m.group(2).lower() in MOIS_EN:
        return dt.date(int(m.group(3)), MOIS_EN[m.group(2).lower()], int(m.group(1)))
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", texte or "")
    return dt.date(*map(int, m.groups())) if m else None


def nettoyer(texte: str) -> str:
    texte = html.unescape(re.sub(r"<[^>]+>", " ", texte or ""))
    return re.sub(r"\s+", " ", texte).strip()


def raccourcir(texte: str, n: int = 220) -> str:
    return texte if len(texte) <= n else texte[: n - 1].rstrip() + "…"


def session_parlementaire(jour: dt.date) -> int:
    """La session ordinaire commence le 1er octobre (juillet-sept = session précédente)."""
    return jour.year if jour.month >= 10 else jour.year - 1


def est_important(titre: str, type_vote: str = "") -> bool:
    """Vote sur un texte entier, motion ou déclaration : ce qui compte vraiment."""
    t = (titre + " " + type_vote).lower()
    return any(k in t for k in (
        "l'ensemble", "l’ensemble", "solennel", "motion de censure", "motion de rejet",
        "motion référendaire", "déclaration du gouvernement", "question préalable",
        "engagement de la responsabilité", "49, alinéa 3", "49.3", "article 50-1",
        "première partie du projet de loi de finances",
        "proposition de résolution", "conclusions de la commission mixte",
    ))


# --------------------------------------------------------------------------
# Assemblée nationale : scrutins publics (open data officiel, mis à jour chaque jour)
# --------------------------------------------------------------------------
def lire_scrutin_an(donnees: dict) -> dict:
    s = donnees.get("scrutin", donnees)
    synthese = s.get("syntheseVote") or {}
    decompte = synthese.get("decompte") or {}
    titre = nettoyer(s.get("titre") or (s.get("objet") or {}).get("libelle") or "")
    sort = (s.get("sort") or {}).get("code", "")
    return {
        "numero": int(s.get("numero")),
        "date": s.get("dateScrutin", "")[:10],
        "titre": titre,
        "type": ((s.get("typeVote") or {}).get("libelleTypeVote") or ""),
        "resultat": "adopté" if "adopt" in sort.lower() else ("rejeté" if sort else "?"),
        "pour": decompte.get("pour"),
        "contre": decompte.get("contre"),
        "abstentions": decompte.get("abstentions"),
        "groupes": groupes_an(s),
    }


def _liste(x):
    """L'open data met un objet seul au lieu d'une liste quand il n'y a qu'un élément."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _texte_uid(x):
    return x.get("#text", "") if isinstance(x, dict) else (x or "")


POSITIONS = (("pours", "pour"), ("contres", "contre"), ("abstentions", "abstention"), ("nonVotants", "non-votant"))


def groupes_an(s: dict) -> list[dict]:
    """Vote de chaque groupe politique, avec la référence de chaque député."""
    organe = ((s.get("ventilationVotes") or {}).get("organe") or {})
    res = []
    for g in _liste((organe.get("groupes") or {}).get("groupe")):
        vote = g.get("vote") or {}
        voix = vote.get("decompteVoix") or {}
        nominatif = vote.get("decompteNominatif") or {}
        noms = {}
        for cle, pos in POSITIONS:
            noms[pos] = [v.get("acteurRef", "") for v in _liste((nominatif.get(cle) or {}).get("votant"))]
        res.append({
            "groupe": g.get("organeRef", ""),
            "membres": int(g.get("nombreMembresGroupe") or 0),
            "pour": int(voix.get("pour") or 0),
            "contre": int(voix.get("contre") or 0),
            "abstention": int(voix.get("abstentions") or 0),
            "noms": noms,
        })
    return res


def lire_deputes_zip(chemin) -> dict:
    """AMO10 : noms des députés en exercice et sigles des groupes."""
    acteurs, organes = {}, {}
    with zipfile.ZipFile(chemin) as z:
        for nom in z.namelist():
            if not nom.endswith(".json"):
                continue
            d = json.loads(z.read(nom))
            if "acteur" in d:
                a = d["acteur"]
                ident = (a.get("etatCivil") or {}).get("ident") or {}
                acteurs[_texte_uid(a.get("uid"))] = f"{ident.get('prenom', '')} {ident.get('nom', '')}".strip()
            elif "organe" in d:
                o = d["organe"]
                organes[_texte_uid(o.get("uid"))] = (o.get("libelleAbrev") or o.get("libelleAbrege")
                                                     or o.get("libelle") or "")
    return {"acteurs": acteurs, "organes": organes}


def deputes() -> dict:
    """Annuaire des députés, mis en cache une semaine dans /data."""
    cache = ETAT.parent / "deputes.json"
    try:
        if time.time() - cache.stat().st_mtime < 7 * 86400:
            return json.loads(cache.read_text())
    except (OSError, ValueError):
        pass
    chemin = telecharger_fichier(URL_AN_DEPUTES)
    try:
        annuaire = lire_deputes_zip(chemin)
    finally:
        os.unlink(chemin)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(annuaire, ensure_ascii=False))
    return annuaire


def nommer_an(votes: list[dict], annuaire: dict) -> None:
    for s in votes:
        for g in s["groupes"]:
            g["groupe"] = annuaire["organes"].get(g["groupe"], g["groupe"])
            g["noms"] = {pos: [annuaire["acteurs"].get(r, f"(ancien député {r})") for r in refs]
                         for pos, refs in g["noms"].items()}


def scrutins_an(dernier_numero: int | None, depuis: dt.date) -> list[dict]:
    chemin = telecharger_fichier(URL_AN_SCRUTINS)
    try:
        return scrutins_an_depuis_zip(chemin, dernier_numero, depuis)
    finally:
        os.unlink(chemin)


def scrutins_an_depuis_zip(chemin, dernier_numero: int | None, depuis: dt.date) -> list[dict]:
    res = []
    with zipfile.ZipFile(chemin) as z:
        for nom in z.namelist():
            m = re.search(r"V(\d+)\.json$", nom)
            if not m:
                continue
            # Le numéro est dans le nom du fichier : on saute ceux déjà vus sans les lire.
            if dernier_numero is not None and int(m.group(1)) <= dernier_numero:
                continue
            s = lire_scrutin_an(json.loads(z.read(nom)))
            if dernier_numero is None and s["date"] < depuis.isoformat():
                continue
            res.append(s)
    return sorted(res, key=lambda s: s["numero"])


# --------------------------------------------------------------------------
# Sénat : liste des scrutins publics de la session (page HTML officielle)
# --------------------------------------------------------------------------
class _Texte(HTMLParser):
    BLOCS = {"p", "div", "li", "tr", "br", "h1", "h2", "h3", "h4", "td", "dt", "dd"}

    def __init__(self):
        super().__init__()
        self.morceaux: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.BLOCS:
            self.morceaux.append("\n")

    def handle_endtag(self, tag):
        if tag in self.BLOCS:
            self.morceaux.append("\n")

    def handle_data(self, data):
        self.morceaux.append(data)


def scrutins_senat_depuis_html(page: str, session: int) -> list[dict]:
    p = _Texte()
    p.feed(page)
    texte = re.sub(r"[ \t\xa0]+", " ", "".join(p.morceaux))
    # Dates de séance présentes dans la page (« jeudi 5 novembre 2026 »)
    dates = [(m.start(), dt.date(int(m.group(3)), MOIS[m.group(2).lower()], int(m.group(1))))
             for m in re.finditer(r"(\d{1,2})(?:er)? (" + "|".join(MOIS) + r") (\d{4})", texte, re.I)]
    res = []
    motif = re.compile(r"Scrutin\s+n\s*°\s*(\d+)\s*:?\s*(.+?)\s*(Adoption|Rejet)\b", re.I | re.S)
    for m in motif.finditer(texte):
        precedentes = [d for pos, d in dates if pos < m.start()]
        res.append({
            "numero": int(m.group(1)),
            "date": precedentes[-1].isoformat() if precedentes else "",
            "titre": raccourcir(re.sub(r"\s*-?\s*consulter le dossier législatif\.?", "", nettoyer(m.group(2)), flags=re.I), 400),
            "resultat": "adopté" if m.group(3).lower() == "adoption" else "rejeté",
            "lien": URL_SENAT_SCRUTIN.format(session=session, n=int(m.group(1))),
        })
    return sorted({s["numero"]: s for s in res}.values(), key=lambda s: s["numero"])


def scrutins_senat(dernier_numero: int | None, aujourd_hui: dt.date) -> tuple[int, list[dict]]:
    session = session_parlementaire(aujourd_hui)
    page = decoder_html(telecharger(URL_SENAT_SCRUTINS.format(session=session)))
    tous = scrutins_senat_depuis_html(page, session)
    if dernier_numero is None:  # premier lancement : on ne garde que les derniers
        tous = tous[-15:]
    else:
        tous = [s for s in tous if s["numero"] > dernier_numero]
    return session, tous


# --------------------------------------------------------------------------
# Flux RSS : textes déposés au Sénat, Panorama des lois (vie-publique / DILA)
# --------------------------------------------------------------------------
SIGLES_SENAT = {
    "les républicains": "LR", "union centriste": "UC", "écologiste - solidarité": "GEST", "socialiste, écologiste et républicain": "SER",
    "communiste républicain citoyen et écologiste": "CRCE-K", "rassemblement démocratique et social européen": "RDSE",
    "rassemblement des démocrates, progressistes et indépendants": "RDPI",
    "écologiste - solidarité et territoires": "GEST", "union nationale pour les territoires": "UNT", "les indépendants - république et territoires": "LIRT",
    "sénateurs ne figurant sur la liste d'aucun groupe": "Non-inscrits", "aucun groupe": "Non-inscrits",
}
LIBELLES_SENAT = {"pour": "pour", "contre": "contre", "abstention": "abstention", "abstentions": "abstention",
                  "n'a pas pris part au vote": "non-votant", "n'ont pas pris part au vote": "non-votant"}


def sigle_senat(nom: str) -> str:
    bas = nom.lower().replace("’", "'")
    for cle, sigle in SIGLES_SENAT.items():
        if bas.startswith(cle) or cle in bas:
            return sigle
    return nom


def noms_senat(texte: str) -> list[str]:
    noms = []
    for morceau in texte.split(","):
        morceau = re.sub(r"^\s*(?:MM\.|Mmes|Mme|M\.)\s+", "", morceau.strip())
        if not morceau:
            continue
        if noms and re.match(r"(?i)(président|vice-président|qui présidait)", morceau):
            noms[-1] += f" ({morceau})"
        else:
            noms.append(morceau)
    return noms


def detail_senat_depuis_html(page: str) -> dict:
    """Page d'un scrutin du Sénat : totaux + vote de chaque groupe avec les noms.

    Le HTML coupe les noms de groupe et les listes sur plusieurs lignes : on travaille
    donc sur le texte mis à plat (un seul espace entre chaque mot).
    """
    p = _Texte()
    p.feed(page)
    texte = re.sub(r"\s+", " ", "".join(p.morceaux).replace("\xa0", " ").replace("’", "'"))
    debut = texte.lower().find("analyse par groupes")
    fin = texte.lower().find("analyse détaillée", max(debut, 0))
    res = {"groupes": []}
    resultat = texte[:debut] if debut >= 0 else texte
    for cle, motif in (("pour", r"(\d+)\s*pour\b"), ("contre", r"(\d+)\s*contre\b"),
                       ("abstentions", r"Abstentions?\s*:\s*(\d+)")):
        m = re.search(motif, resultat, re.I)
        if m:
            res[cle] = int(m.group(1))
    if debut < 0:
        return res
    section = texte[debut:fin if fin > 0 else len(texte)]
    entete = re.compile(r"((?:Groupe\s|Sénateurs ne figurant)[^:]{2,150}?)\s*:\s*(\d+)\s*sénateurs?", re.I)
    labels = r"Pour|Contre|Abstentions?|N'ont pas pris part au vote|N'a pas pris part au vote"
    entetes = list(entete.finditer(section))
    for k, m in enumerate(entetes):
        bloc = section[m.end(): entetes[k + 1].start() if k + 1 < len(entetes) else len(section)]
        nom = re.sub(r"^Groupe\s+(?:du\s+|de la\s+|des\s+)?", "", m.group(1).strip(), flags=re.I)
        g = {"groupe": sigle_senat(nom), "membres": int(m.group(2)), "pour": 0, "contre": 0, "abstention": 0,
             "noms": {"pour": [], "contre": [], "abstention": [], "non-votant": []}}
        for pos, motif in (("pour", r"\bPour\s*:\s*(\d+)"), ("contre", r"\bContre\s*:\s*(\d+)"),
                           ("abstention", r"\bAbstentions?\s*:\s*(\d+)")):
            c = re.search(motif, bloc)
            if c:
                g[pos] = int(c.group(1))
        for n in re.finditer(rf"({labels})\s*:\s*((?:MM?\.|Mmes?)\s.+?)(?=\s(?:{labels})\s*:|$)", bloc):
            g["noms"][LIBELLES_SENAT[n.group(1).lower()]] += noms_senat(n.group(2))
        res["groupes"].append(g)
    return res


def lire_rss(brut: bytes) -> list[dict]:
    racine = ET.fromstring(brut)  # gère l'encodage déclaré (iso-8859-15 au Sénat)
    items = []
    for it in racine.iter("item"):
        def champ(*noms):
            for nom in noms:
                for enfant in it:
                    if enfant.tag.split("}")[-1] == nom and (enfant.text or "".join(enfant.itertext())).strip():
                        return nettoyer("".join(enfant.itertext()))
            return ""
        items.append({
            "titre": champ("title"),
            "lien": champ("link", "guid").split("?egn-")[0],
            "date": date_rss(champ("pubDate", "date")),
            "type": champ("type", "category"),
            "sujets": champ("subject"),
            "id": champ("guid", "identifier", "link"),
        })
    return items


# --------------------------------------------------------------------------
# Résumé IA facultatif
# --------------------------------------------------------------------------
CONSIGNE_IA = (
    "Tu es un rédacteur de dépêches parlementaires strictement neutre. À partir UNIQUEMENT "
    "des faits fournis, écris en français 3 à 5 phrases simples qui expliquent le contexte "
    "de la journée parlementaire pour un étudiant : de quoi parlent les textes importants, "
    "où ils en sont dans la procédure (Assemblée, Sénat, commission mixte paritaire, "
    "promulgation). N'invente aucun fait, aucun chiffre, aucune réaction. Pas d'opinion, "
    "pas d'adjectif évaluatif, pas de nom de parti sauf s'il est dans les faits. "
    "Si les faits sont trop maigres, réponds seulement : RIEN."
)


def resume_ia(faits: str) -> str:
    if not OLLAMA_URL or not faits.strip():
        return ""
    corps = json.dumps({
        "model": OLLAMA_MODELE, "stream": False, "think": False,
        "options": {"temperature": 0.2, "num_ctx": 8192},
        "messages": [{"role": "system", "content": CONSIGNE_IA},
                     {"role": "user", "content": faits[:12000]}],
    }).encode()
    req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=corps,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            texte = json.loads(r.read())["message"]["content"]
    except (urllib.error.URLError, OSError, KeyError, ValueError) as e:
        print(f"[ia] indisponible : {e}", file=sys.stderr)
        return ""
    texte = re.sub(r"<think>.*?</think>", "", texte, flags=re.S).strip()
    return "" if texte.upper().startswith("RIEN") else texte


# --------------------------------------------------------------------------
# Mise en forme
# --------------------------------------------------------------------------
def ligne_vote(s: dict, lien: str) -> str:
    icone = "✅" if s["resultat"] == "adopté" else "❌"
    chiffres = ""
    if s.get("pour") is not None:
        chiffres = f" ({s['pour']} pour, {s['contre']} contre, {s['abstentions']} abst.)"
    ligne = f"{icone} **{s['resultat'].capitalize()}**{chiffres} : {raccourcir(s['titre'])} [lien](<{lien}>)"
    if s.get("groupes"):
        # Masqué derrière un spoiler Discord : il faut cliquer pour l'afficher
        parts = []
        for g in sorted(s["groupes"], key=lambda g: -g["membres"]):
            v = " ".join(x for x in (f"✅{g['pour']}" if g["pour"] else "", f"❌{g['contre']}" if g["contre"] else "",
                                     f"⚪{g['abstention']}" if g["abstention"] else "") if x) or "–"
            parts.append(f"{g['groupe']} {v}")
        ligne += "\n> ||🗳️ " + " · ".join(parts) + "||"
    return ligne


def detail_nominatif(aujourd_hui: dt.date, votes: list[tuple[str, dict, str]]) -> str:
    """Fichier texte joint au message : qui a voté quoi, groupe par groupe."""
    sortie = [f"DÉTAIL NOMINATIF DES VOTES ({aujourd_hui:%d/%m/%Y})",
              "Sources : open data de l'Assemblée nationale, scrutins publics du Sénat.", ""]
    for chambre, s, lien in votes:
        if not s.get("groupes"):
            continue
        sortie += ["=" * 70, f"{chambre.upper()} - scrutin n° {s['numero']} du {s['date']}", s["titre"]]
        total = f" : {s['pour']} pour, {s['contre']} contre, {s.get('abstentions', 0)} abstentions" if s.get("pour") is not None else ""
        sortie += [f"Résultat : {s['resultat'].upper()}{total}", lien, ""]
        for g in sorted(s["groupes"], key=lambda g: -g["membres"]):
            sortie.append(f"-- {g['groupe']} ({g['membres']} membres) : {g['pour']} pour, {g['contre']} contre, {g['abstention']} abst.")
            for pos, titre in (("pour", "Pour"), ("contre", "Contre"), ("abstention", "Abstention"), ("non-votant", "N'ont pas voté")):
                if g["noms"].get(pos):
                    sortie.append(f"   {titre} ({len(g['noms'][pos])}) : " + ", ".join(sorted(g["noms"][pos])))
            sortie.append("")
    return "\n".join(sortie) if len(sortie) > 3 else ""


def bloc_votes(nom: str, votes: list[dict], lien_de) -> tuple[list[str], str]:
    if not votes:
        return [], ""
    importants = [s for s in votes if est_important(s["titre"], s.get("type", ""))]
    autres = [s for s in votes if s not in importants]
    lignes = [f"## 🏛️ {nom}"]
    if importants:
        lignes += [ligne_vote(s, lien_de(s)) for s in importants]
    else:
        lignes.append("_Aucun vote sur un texte entier ou une motion._")
    if autres:
        a = sum(s["resultat"] == "adopté" for s in autres)
        r = len(autres) - a
        lignes.append(f"➕ {len(autres)} autre{'s' * (len(autres) > 1)} scrutin{'s' * (len(autres) > 1)} "
                      f"(amendements, articles) : {a} adopté{'s' * (a > 1)}, {r} rejeté{'s' * (r > 1)}.")
    faits = "\n".join(f"{nom} {s['date']} : {s['titre']} -> {s['resultat']}" for s in importants)
    return lignes, faits


def construire(aujourd_hui: dt.date, an: list[dict], senat: list[dict],
               lois: list[dict], depots: list[dict], erreurs: list[str]) -> tuple[str, str]:
    jours = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
    mois = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
            "septembre", "octobre", "novembre", "décembre"]
    titre = f"# 🇫🇷 Point politique du {jours[aujourd_hui.weekday()]} {aujourd_hui.day} {mois[aujourd_hui.month - 1]}"
    lignes, faits = [titre], []

    l, f = bloc_votes("Assemblée nationale", an, lambda s: URL_AN_SCRUTIN.format(n=s["numero"]))
    lignes += l; faits.append(f)
    l, f = bloc_votes("Sénat", senat, lambda s: s["lien"])
    lignes += l; faits.append(f)

    if lois:
        lignes.append("## 📜 Panorama des lois (promulguées ou en cours)")
        for it in lois:
            genre = f" _({it['type']})_" if it["type"] else ""
            lignes.append(f"• {raccourcir(it['titre'])}{genre} [fiche](<{it['lien']}>)")
            faits.append(f"Panorama des lois : {it['titre']} ({it['type']}) sujets : {it['sujets']}")
    if depots:
        lignes.append("## 📥 Nouveaux textes déposés au Sénat")
        for it in depots[:MAX_DEPOTS]:
            genre = f" _({it['type']})_" if it["type"] else ""
            lignes.append(f"• {raccourcir(it['titre'], 160)}{genre} [texte](<{it['lien']}>)")
        if len(depots) > MAX_DEPOTS:
            lignes.append(f"… et {len(depots) - MAX_DEPOTS} autres.")

    if len(lignes) == 1:
        lignes.append("Rien de nouveau publié depuis le dernier point (pas de séance ou week-end).")
    if erreurs:
        lignes.append("⚠️ Source(s) injoignable(s) aujourd'hui : " + ", ".join(erreurs) + ". Elles seront rattrapées au prochain envoi.")
    lignes.append("-# Sources officielles : data.assemblee-nationale.fr, senat.fr, vie-publique.fr (DILA).")
    return "\n".join(lignes), "\n".join(x for x in faits if x)


def decouper(texte: str, limite: int = 1900) -> list[str]:
    morceaux, courant = [], ""
    for ligne in texte.split("\n"):
        if len(courant) + len(ligne) + 1 > limite and courant:
            morceaux.append(courant)
            courant = ""
        courant += ligne[:limite] + "\n"
    if courant.strip():
        morceaux.append(courant)
    return morceaux


def multipart(payload: dict, nom_fichier: str, contenu: bytes) -> tuple[bytes, str]:
    frontiere = "----pointpolitique" + os.urandom(8).hex()
    corps = (f"--{frontiere}\r\nContent-Disposition: form-data; name=\"payload_json\"\r\n"
             f"Content-Type: application/json\r\n\r\n{json.dumps(payload)}\r\n"
             f"--{frontiere}\r\nContent-Disposition: form-data; name=\"files[0]\"; filename=\"{nom_fichier}\"\r\n"
             f"Content-Type: text/plain; charset=utf-8\r\n\r\n").encode() + contenu + f"\r\n--{frontiere}--\r\n".encode()
    return corps, f"multipart/form-data; boundary={frontiere}"


def envoyer_discord(texte: str, piece_jointe: tuple[str, str] | None = None) -> None:
    morceaux = decouper(texte)
    for i, morceau in enumerate(morceaux):
        payload = {"username": "Point politique", "content": morceau, "allowed_mentions": {"parse": []}}
        if piece_jointe and i == len(morceaux) - 1:
            corps, type_contenu = multipart(payload, piece_jointe[0], piece_jointe[1].encode())
        else:
            corps, type_contenu = json.dumps(payload).encode(), "application/json"
        req = urllib.request.Request(DISCORD_WEBHOOK_URL, data=corps, headers={
            "Content-Type": type_contenu, "User-Agent": UA})
        for essai in range(3):
            try:
                urllib.request.urlopen(req, timeout=30).read()
                break
            except urllib.error.HTTPError as e:
                if e.code == 429 and essai < 2:
                    time.sleep(float(e.headers.get("Retry-After", "2")))
                    continue
                raise
        time.sleep(1)


# --------------------------------------------------------------------------
# Programme principal
# --------------------------------------------------------------------------
def charger_etat() -> dict:
    try:
        return json.loads(ETAT.read_text())
    except (OSError, ValueError):
        return {}


def un_point(envoyer: bool) -> str:
    etat = charger_etat()
    aujourd_hui = dt.datetime.now(TZ).date()
    depuis = aujourd_hui - dt.timedelta(days=JOURS_PREMIER_ENVOI)
    nouvel_etat = dict(etat)
    erreurs: list[str] = []
    an = senat = lois = depots = []

    try:
        an = scrutins_an(etat.get("an_dernier"), depuis)
        if an:
            nouvel_etat["an_dernier"] = an[-1]["numero"]
    except Exception as e:  # noqa: BLE001 (une source en panne ne bloque pas les autres)
        print(f"[an] {e!r}", file=sys.stderr); erreurs.append("Assemblée nationale")

    try:
        session, senat = scrutins_senat(
            etat.get("senat_dernier") if etat.get("senat_session") == session_parlementaire(aujourd_hui) else None,
            aujourd_hui)
        nouvel_etat["senat_session"] = session
        if senat:
            nouvel_etat["senat_dernier"] = senat[-1]["numero"]
    except Exception as e:  # noqa: BLE001
        print(f"[senat] {e!r}", file=sys.stderr); erreurs.append("Sénat (scrutins)")

    for cle, url, nom in (("lois_vus", URL_VIE_PUBLIQUE_LOIS, "vie-publique"),
                          ("depots_vus", URL_SENAT_TEXTES, "Sénat (textes)")):
        try:
            items = lire_rss(telecharger(url))
            vus = set(etat.get(cle, []))
            if cle in etat:
                nouveaux = [i for i in items if i["id"] not in vus]
            else:
                # Premier lancement : une semaine de flux pour avoir un peu de contexte
                nouveaux = [i for i in items if i["date"] and i["date"] >= aujourd_hui - dt.timedelta(days=7)]
            nouvel_etat[cle] = sorted(vus | {i["id"] for i in items})[-500:]
            if cle == "lois_vus":
                lois = nouveaux
            else:
                depots = nouveaux
        except Exception as e:  # noqa: BLE001
            print(f"[{nom}] {e!r}", file=sys.stderr); erreurs.append(nom)

    # Détail nominatif, seulement pour les votes mis en avant
    an_imp = [s for s in an if est_important(s["titre"], s.get("type", ""))]
    for s in an:
        if s not in an_imp:
            s["groupes"] = []
    if an_imp:
        try:
            nommer_an(an_imp, deputes())
        except Exception as e:  # noqa: BLE001
            print(f"[deputes] {e!r}", file=sys.stderr)
            for s in an_imp:
                s["groupes"] = []
    for s in senat:
        if est_important(s["titre"]):
            try:
                s.update(detail_senat_depuis_html(decoder_html(telecharger(s["lien"]))))
            except Exception as e:  # noqa: BLE001
                print(f"[senat detail {s['numero']}] {e!r}", file=sys.stderr)

    texte, faits = construire(aujourd_hui, an, senat, lois, depots, erreurs)
    detail = detail_nominatif(aujourd_hui, [("Assemblée nationale", s, URL_AN_SCRUTIN.format(n=s["numero"])) for s in an_imp]
                              + [("Sénat", s, s["lien"]) for s in senat if s.get("groupes")])
    if detail:
        texte = texte.replace("\n-# Sources", "\n📎 Qui a voté quoi : clique sur les cases noires pour voir le vote de chaque groupe, "
                              "et ouvre le fichier joint pour les noms.\n-# Sources", 1)
    contexte = resume_ia(faits)
    if contexte:
        texte = texte.replace("\n-# Sources", f"\n## 🧠 Contexte (résumé IA locale, à vérifier)\n{contexte}\n-# Sources", 1)

    if envoyer:
        if not DISCORD_WEBHOOK_URL:
            raise SystemExit("DISCORD_WEBHOOK_URL manquant dans .env")
        envoyer_discord(texte, (f"votes-{aujourd_hui}.txt", detail) if detail else None)
        ETAT.parent.mkdir(parents=True, exist_ok=True)
        nouvel_etat["dernier_envoi"] = dt.datetime.now(TZ).isoformat(timespec="seconds")
        ETAT.write_text(json.dumps(nouvel_etat, ensure_ascii=False, indent=1))
    if detail and not envoyer:
        texte += "\n\n----- fichier joint -----\n" + detail
    return texte


def boucle() -> None:
    h, m = map(int, HEURE_ENVOI.split(":"))
    print(f"Point politique : envoi chaque jour à {HEURE_ENVOI} ({TZ.key}).", flush=True)
    while True:
        maintenant = dt.datetime.now(TZ)
        cible = maintenant.replace(hour=h, minute=m, second=0, microsecond=0)
        if cible <= maintenant:
            cible += dt.timedelta(days=1)
        time.sleep(max(1, (cible - maintenant).total_seconds()))
        for essai in range(3):
            try:
                un_point(envoyer=True)
                print(f"[{dt.datetime.now(TZ):%Y-%m-%d %H:%M}] point envoyé", flush=True)
                break
            except Exception as e:  # noqa: BLE001
                print(f"[envoi] essai {essai + 1} raté : {e!r}", file=sys.stderr, flush=True)
                time.sleep(600)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--once", action="store_true", help="faire un point maintenant puis quitter")
    ap.add_argument("--dry-run", action="store_true", help="afficher sans envoyer ni mémoriser")
    a = ap.parse_args()
    if a.once or a.dry_run:
        print(un_point(envoyer=not a.dry_run))
    else:
        boucle()
