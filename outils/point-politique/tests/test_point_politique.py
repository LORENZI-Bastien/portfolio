"""Tests hors ligne : python3 -m unittest discover -s tests"""
import datetime as dt
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ["FICHIER_ETAT"] = str(Path(tempfile.mkdtemp()) / "etat.json")
import point_politique as pp  # noqa: E402


VENTILATION = {"organe": {"organeRef": "PO838901", "groupes": {"groupe": [
    {"organeRef": "PO800001", "nombreMembresGroupe": "123", "vote": {
        "positionMajoritaire": "pour",
        "decompteVoix": {"pour": "2", "contre": "0", "abstentions": "1", "nonVotants": "0"},
        "decompteNominatif": {"nonVotants": None, "contres": None,
                              "pours": {"votant": [{"acteurRef": "PA1"}, {"acteurRef": "PA2"}]},
                              "abstentions": {"votant": {"acteurRef": "PA3"}}}}},
    {"organeRef": "PO800002", "nombreMembresGroupe": "71", "vote": {
        "positionMajoritaire": "contre",
        "decompteVoix": {"pour": "0", "contre": "1", "abstentions": "0", "nonVotants": "0"},
        "decompteNominatif": {"nonVotants": None, "pours": None, "abstentions": None,
                              "contres": {"votant": {"acteurRef": "PA999"}}}}},
]}}}


def scrutin_an(n, date, titre, sort, typ="scrutin public ordinaire"):
    return {"scrutin": {"numero": str(n), "dateScrutin": date, "titre": titre,
                        "typeVote": {"libelleTypeVote": typ},
                        "sort": {"code": sort},
                        "syntheseVote": {"decompte": {"pour": "300", "contre": "200", "abstentions": "40"}},
                        "ventilationVotes": VENTILATION}}


def zip_amo():
    f = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    with zipfile.ZipFile(f, "w") as z:
        for uid, prenom, nom in (("PA1", "Alice", "Martin"), ("PA2", "Bruno", "Petit"), ("PA3", "Chloé", "Durand")):
            z.writestr(f"json/acteur/{uid}.json", json.dumps({"acteur": {"uid": {"#text": uid},
                       "etatCivil": {"ident": {"civ": "M.", "prenom": prenom, "nom": nom}}}}))
        for uid, sigle in (("PO800001", "AAA"), ("PO800002", "BBB")):
            z.writestr(f"json/organe/{uid}.json", json.dumps({"organe": {"uid": uid, "codeType": "GP",
                       "libelle": "Groupe " + sigle, "libelleAbrev": sigle}}))
    return f.name


def bloc_groupe(code, nom, membres, pour, contre, abst, nv, listes):
    noms = "".join(f'<li class="mb-2"><b>{lab}</b>&nbsp;:\n{txt}</li>' for lab, txt in listes)
    return f"""<div class="accordion-item" id="accordion-scrutin-{code}">
<h3 class="accordion-title fs-5">{nom}&nbsp;:
{membres}<span class="visually-hidden">s&eacute;nateurs</span></h3>
<ul class="list-inline mb-0" aria-label="Détail des votants pour le Groupe">
<li class="list-inline-item"><svg></svg>Pour&nbsp;:
<span class="ms-1 fw-semibold">{pour}</span></li>
<li class="list-inline-item">Contre&nbsp;: <span class="ms-1 fw-semibold">{contre}</span></li>
<li class="list-inline-item">Abstention&nbsp;: <span>{abst}</span></li><li>N'a
pas pris part au vote&nbsp;: <span>{nv}</span></li></ul>
<button>Voir le détail</button>
<div class="accordion-body"><ul class="list-unstyled mb-0">{noms}</ul></div></div>"""


# Reproduit la vraie page (relevée sur scr2026-56 le 2026-11-07) : noms de groupe et listes
# coupés sur plusieurs lignes, « 124sénateurs » collé, nombres dans des <span>.
SENAT_DETAIL = """<html><head><meta charset="utf-8"><title>Scrutin n°56</title></head><body>
<h1>Scrutin n°56 - séance du 5 novembre 2026</h1>
<h2>Résultat du scrutin</h2><p>Le Sénat n'a pas adopté</p>
<ul><li><strong>343</strong> votants</li><li><strong>343</strong> suffrages exprimés</li>
<li><strong>157</strong> pour</li><li><strong>186</strong> contre</li><li>Abstention : 0</li>
<li>N'ont pas pris part au vote : 5</li></ul>
<h2>Analyse par groupes politiques</h2>""" + bloc_groupe(
    "UMP", "Groupe Les R&eacute;publicains", 124, 0, 123, 0, 1,
    [("Contre", "Mmes Marie-Do Aeschlimann, G&eacute;raldine Amouroux, M. Jean-Claude Anglars,\nMme V&eacute;ronique Baude"),
     ("N'ont pas pris part au vote", "M. G&eacute;rard Larcher, Pr&eacute;sident du S&eacute;nat")]) + bloc_groupe(
    "SOCR", "Groupe Socialiste, &Eacute;cologiste et\nR&eacute;publicain", 62, 62, 0, 0, 0,
    [("Pour", "Mmes Viviane Artigalas,\nAudrey B&eacute;lim")]) + bloc_groupe(
    "UNT", "Groupe Union Nationale pour les\nTerritoires", 15, 0, 0, 15, 0,
    [("Abstention", "MM. Jean Un, Paul Deux")]) + bloc_groupe(
    "NI", "S&eacute;nateurs ne figurant sur la liste\nd'aucun groupe", 3, 1, 2, 0, 0,
    [("Pour", "M. Jean Untel"), ("Contre", "MM. Paul A, Jacques B")]) + """
<h2>Analyse détaillée</h2><h3>Ont voté pour</h3><ul><li>Viviane Artigalas</li></ul>
</body></html>"""


def zip_an(scrutins):
    f = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
    with zipfile.ZipFile(f, "w") as z:
        for s in scrutins:
            z.writestr(f"json/VTANR5L17V{s['scrutin']['numero']}.json", json.dumps(s))
    return f.name


SENAT_HTML = """<html><head><meta charset="utf-8"></head><body>
<h3>Séance du jeudi 5 novembre 2026</h3>
<ul><li><a href="2026/scr2026-56.html">Scrutin n° 56</a> : sur l'ensemble du projet de loi relatif à la
résilience des infrastructures critiques. Adoption</li>
<li><a href="2026/scr2026-55.html">Scrutin n° 55</a> : sur l'amendement n° 12 à l'article 3 du projet de loi relatif
à la résilience. Rejet</li></ul>
<h3>Séance du mardi 3 novembre 2026</h3>
<p>Scrutin N°50 : sur l'article unique de la proposition de loi visant à protéger les demandeurs de logement Adoption</p>
</body></html>"""

SENAT_RSS = """<?xml version="1.0" encoding="iso-8859-15"?>
<rss version="2.0"><channel><title>Sénat - derniers textes</title>
<item><title>Avenir d'Eurojust - texte N° 150</title><pubDate>Fri,06 Nov 2026 17:11:14 GMT</pubDate>
<link>http://www.senat.fr/leg/ppr26-150.html</link><guid>http://www.senat.fr/leg/ppr26-150.html</guid>
<category>proposition de résolution</category></item>
<item><title>Vieux texte</title><pubDate>Thu,01 Oct 2026 10:00:00 GMT</pubDate>
<link>http://www.senat.fr/leg/ppl26-001.html</link><guid>http://www.senat.fr/leg/ppl26-001.html</guid></item>
</channel></rss>""".encode("iso-8859-15")

VP_RSS = """<?xml version="1.0" encoding="utf-8"?>
<rss version="2.0" xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>
<item><title>Loi du 2 novembre 2026 portant abrogation du "code noir"</title>
<link>https://www.vie-publique.fr/loi/303397-code-noir?egn-publisher=dila_vp&amp;egn-name=informer_rss_lois</link>
<pubDate>Tue, 03 Nov 2026 00:00:00 +0100</pubDate><dc:type>Proposition de loi</dc:type>
<dc:subject>Histoire, Outre-mer</dc:subject><dc:identifier>303397</dc:identifier>
<guid isPermaLink="true">https://www.vie-publique.fr/loi/303397-code-noir</guid></item>
</channel></rss>""".encode()


class Tests(unittest.TestCase):
    def test_an_zip(self):
        z = zip_an([
            scrutin_an(1200, "2026-10-01", "l'amendement n° 4", "rejeté"),
            scrutin_an(1300, "2026-11-04", "l'ensemble du projet de loi de finances pour 2027 (première lecture)", "rejeté", "scrutin public solennel"),
            scrutin_an(1301, "2026-11-05", "l'amendement n° 87 de M. X à l'article 2", "adopté"),
        ])
        res = pp.scrutins_an_depuis_zip(z, None, dt.date(2026, 11, 4))
        self.assertEqual([s["numero"] for s in res], [1300, 1301])
        self.assertEqual(res[0]["resultat"], "rejeté")
        self.assertTrue(pp.est_important(res[0]["titre"], res[0]["type"]))
        self.assertFalse(pp.est_important(res[1]["titre"], res[1]["type"]))
        # Avec un état : seuls les numéros plus grands
        self.assertEqual([s["numero"] for s in pp.scrutins_an_depuis_zip(z, 1300, dt.date(2000, 1, 1))], [1301])

    def test_senat_html(self):
        res = pp.scrutins_senat_depuis_html(SENAT_HTML, 2026)
        self.assertEqual([s["numero"] for s in res], [50, 55, 56])
        par_num = {s["numero"]: s for s in res}
        self.assertEqual(par_num[56]["resultat"], "adopté")
        self.assertEqual(par_num[55]["resultat"], "rejeté")
        self.assertEqual(par_num[56]["date"], "2026-11-05")
        self.assertEqual(par_num[50]["date"], "2026-11-03")
        self.assertIn("ensemble du projet de loi", par_num[56]["titre"])
        self.assertTrue(par_num[56]["lien"].endswith("/2026/scr2026-56.html"))

    def test_rss(self):
        s = pp.lire_rss(SENAT_RSS)
        self.assertEqual(s[0]["date"], dt.date(2026, 11, 6))
        self.assertEqual(s[0]["type"], "proposition de résolution")
        v = pp.lire_rss(VP_RSS)
        self.assertEqual(v[0]["type"], "Proposition de loi")
        self.assertEqual(v[0]["lien"], "https://www.vie-publique.fr/loi/303397-code-noir")
        self.assertEqual(v[0]["date"], dt.date(2026, 11, 3))

    def test_groupes_an_et_noms(self):
        s = pp.lire_scrutin_an(scrutin_an(1, "2026-11-04", "l'ensemble", "adopté"))
        self.assertEqual(s["groupes"][0]["noms"]["pour"], ["PA1", "PA2"])
        self.assertEqual(s["groupes"][0]["noms"]["abstention"], ["PA3"])
        annuaire = pp.lire_deputes_zip(zip_amo())
        pp.nommer_an([s], annuaire)
        self.assertEqual(s["groupes"][0]["groupe"], "AAA")
        self.assertEqual(s["groupes"][0]["noms"]["pour"], ["Alice Martin", "Bruno Petit"])
        self.assertEqual(s["groupes"][1]["noms"]["contre"], ["(ancien député PA999)"])
        ligne = pp.ligne_vote(s, "https://x")
        self.assertIn("||🗳️ AAA ✅2 ⚪1 · BBB ❌1||", ligne)

    def test_detail_senat(self):
        d = pp.detail_senat_depuis_html(SENAT_DETAIL)
        self.assertEqual((d["pour"], d["contre"], d["abstentions"]), (157, 186, 0))
        g = {x["groupe"]: x for x in d["groupes"]}
        self.assertEqual(set(g), {"LR", "SER", "UNT", "Non-inscrits"})
        self.assertEqual(g["LR"]["membres"], 124)
        self.assertEqual((g["LR"]["pour"], g["LR"]["contre"]), (0, 123))
        self.assertEqual(g["LR"]["noms"]["contre"], ["Marie-Do Aeschlimann", "Géraldine Amouroux", "Jean-Claude Anglars", "Véronique Baude"])
        self.assertEqual(g["LR"]["noms"]["non-votant"], ["Gérard Larcher (Président du Sénat)"])
        self.assertEqual(g["SER"]["pour"], 62)
        self.assertEqual(g["SER"]["noms"]["pour"], ["Viviane Artigalas", "Audrey Bélim"])
        self.assertEqual(g["UNT"]["abstention"], 15)
        self.assertEqual(g["Non-inscrits"]["noms"]["pour"], ["Jean Untel"])
        self.assertEqual(g["Non-inscrits"]["noms"]["contre"], ["Paul A", "Jacques B"])

    def test_gzip_et_importance(self):
        import gzip
        class R(io.BytesIO):
            headers = {"Content-Encoding": "gzip"}
            def __enter__(self): return self
            def __exit__(self, *a): pass
        with mock.patch.object(pp.urllib.request, "urlopen", lambda *a, **k: R(gzip.compress(VP_RSS))):
            self.assertEqual(len(pp.lire_rss(pp.telecharger("https://x"))), 1)
        self.assertFalse(pp.est_important("l'amendement n° 939 de suppression de l'article 49 du projet de loi de finances pour 2027"))
        self.assertTrue(pp.est_important("la première partie du projet de loi de finances pour 2027 (première lecture)"))
        self.assertTrue(pp.est_important("la motion de censure déposée en application de l'article 49, alinéa 3"))

    def test_session(self):
        self.assertEqual(pp.session_parlementaire(dt.date(2026, 11, 7)), 2026)
        self.assertEqual(pp.session_parlementaire(dt.date(2027, 7, 7)), 2026)

    def test_point_complet_et_etat(self):
        z = zip_an([scrutin_an(1300, "2026-11-04", "l'ensemble du projet de loi de finances pour 2027", "rejeté", "scrutin public solennel")]
                   + [scrutin_an(1301 + i, "2026-11-05", f"l'amendement n° {i}", "adopté" if i % 3 == 0 else "rejeté") for i in range(200)])

        def faux_tel(url, timeout=60):
            if "scr2026-56.html" in url:
                return SENAT_DETAIL.encode()
            if "senat.fr/scrutin-public" in url:
                return SENAT_HTML.encode()
            if "textes.rss" in url:
                return SENAT_RSS
            if "lois-feeds" in url:
                return VP_RSS
            raise AssertionError(url)

        amo = zip_amo()

        def faux_fichier(url, timeout=300):
            source = amo if "amo" in url else z
            c = tempfile.mktemp(suffix=".zip"); Path(c).write_bytes(Path(source).read_bytes()); return c

        envoyes = []
        aujourdhui = dt.datetime(2026, 11, 7, 7, 30, tzinfo=pp.TZ)
        with mock.patch.object(pp, "telecharger", faux_tel), \
             mock.patch.object(pp, "telecharger_fichier", faux_fichier), \
             mock.patch.object(pp, "DISCORD_WEBHOOK_URL", "https://exemple.invalid/webhook"), \
             mock.patch.object(pp, "envoyer_discord", lambda t, pj=None: envoyes.append((t, pj))), \
             mock.patch.object(pp.dt, "datetime", wraps=dt.datetime) as fdt:
            fdt.now.return_value = aujourdhui
            texte = pp.un_point(envoyer=True)
            print("\n" + texte)
            self.assertIn("Point politique du samedi 7 novembre", texte)
            self.assertIn("❌ **Rejeté** (300 pour, 200 contre, 40 abst.) : l'ensemble du projet de loi de finances", texte)
            self.assertIn("200 autres scrutins", texte)
            self.assertIn("Sénat", texte)
            self.assertIn("||🗳️ AAA ✅2 ⚪1 · BBB ❌1||", texte)
            self.assertIn("||🗳️ LR ❌123 · SER ✅62 · UNT ⚪15 · Non-inscrits ✅1 ❌2||", texte)
            self.assertIn("✅ **Adopté** (157 pour, 186 contre, 0 abst.)", texte)
            nom_fichier, detail = envoyes[0][1]
            print("\n----- " + nom_fichier + "\n" + detail)
            self.assertEqual(nom_fichier, "votes-2026-11-07.txt")
            self.assertIn("Pour (2) : Alice Martin, Bruno Petit", detail)
            self.assertIn("Contre (2) : Jacques B, Paul A", detail)
            self.assertIn("code noir", texte)
            self.assertIn("Eurojust", texte)
            self.assertNotIn("Vieux texte", texte)
            self.assertTrue(all(len(m) <= 2000 for m in pp.decouper(texte)))
            etat = json.loads(pp.ETAT.read_text())
            self.assertEqual(etat["an_dernier"], 1500)
            self.assertEqual(etat["senat_dernier"], 56)
            # Deuxième passage : plus rien de nouveau
            texte2 = pp.un_point(envoyer=True)
            self.assertIn("Rien de nouveau", texte2)
        self.assertEqual(len(envoyes), 2)
        self.assertIsNone(envoyes[1][1])  # rien de nouveau : pas de fichier

    def test_source_en_panne(self):
        def panne(*a, **k):
            raise OSError("réseau coupé")
        with mock.patch.object(pp, "telecharger", panne), mock.patch.object(pp, "telecharger_fichier", panne):
            texte = pp.un_point(envoyer=False)
        self.assertIn("injoignable", texte)

    def test_decouper(self):
        morceaux = pp.decouper("\n".join("x" * 100 for _ in range(100)))
        self.assertTrue(all(len(m) <= 1900 for m in morceaux))
        self.assertEqual(sum(m.count("x") for m in morceaux), 10000)


if __name__ == "__main__":
    unittest.main()
