#!/usr/bin/env python3
"""Génère la cartographie des CFA (un fichier HTML autonome) à partir des
exports du Catalogue des formations en apprentissage (Carif-Oref).

Entrées (deux exports CSV du catalogue, séparateur « ; ») :
  - la liste des établissements  (etablissements_AAAA-MM-JJ….csv)
  - la liste des formations      (formation_AAAA-MM-JJ….csv)

Sortie : carte_cfa.html, à ouvrir dans un navigateur ou à publier tel quel.

Options : une table RNCP → thèmes Formacode (CSV) active le filtre par thème ;
la table des descripteurs Formacode V14 range ces thèmes en domaines.

Utilisation :
  python generer_carte.py --etablissements data/etablissements.csv \
                          --formations data/formations.csv \
                          --themes data/themes_formacode.csv \
                          --formacode data/formacode_v14.csv \
                          --sortie carte_cfa.html
"""

import argparse
import csv
import datetime as dt
import json
import re
import sys
import unicodedata
from collections import defaultdict, Counter
from pathlib import Path

# ----------------------------------------------------------------------------
# Référentiels fixes
# ----------------------------------------------------------------------------

DEPARTEMENTS = {
    "01": "Ain", "02": "Aisne", "03": "Allier", "04": "Alpes-de-Haute-Provence",
    "05": "Hautes-Alpes", "06": "Alpes-Maritimes", "07": "Ardèche", "08": "Ardennes",
    "09": "Ariège", "10": "Aube", "11": "Aude", "12": "Aveyron", "13": "Bouches-du-Rhône",
    "14": "Calvados", "15": "Cantal", "16": "Charente", "17": "Charente-Maritime",
    "18": "Cher", "19": "Corrèze", "2A": "Corse-du-Sud", "2B": "Haute-Corse",
    "21": "Côte-d'Or", "22": "Côtes-d'Armor", "23": "Creuse", "24": "Dordogne",
    "25": "Doubs", "26": "Drôme", "27": "Eure", "28": "Eure-et-Loir", "29": "Finistère",
    "30": "Gard", "31": "Haute-Garonne", "32": "Gers", "33": "Gironde", "34": "Hérault",
    "35": "Ille-et-Vilaine", "36": "Indre", "37": "Indre-et-Loire", "38": "Isère",
    "39": "Jura", "40": "Landes", "41": "Loir-et-Cher", "42": "Loire", "43": "Haute-Loire",
    "44": "Loire-Atlantique", "45": "Loiret", "46": "Lot", "47": "Lot-et-Garonne",
    "48": "Lozère", "49": "Maine-et-Loire", "50": "Manche", "51": "Marne",
    "52": "Haute-Marne", "53": "Mayenne", "54": "Meurthe-et-Moselle", "55": "Meuse",
    "56": "Morbihan", "57": "Moselle", "58": "Nièvre", "59": "Nord", "60": "Oise",
    "61": "Orne", "62": "Pas-de-Calais", "63": "Puy-de-Dôme", "64": "Pyrénées-Atlantiques",
    "65": "Hautes-Pyrénées", "66": "Pyrénées-Orientales", "67": "Bas-Rhin", "68": "Haut-Rhin",
    "69": "Rhône", "70": "Haute-Saône", "71": "Saône-et-Loire", "72": "Sarthe",
    "73": "Savoie", "74": "Haute-Savoie", "75": "Paris", "76": "Seine-Maritime",
    "77": "Seine-et-Marne", "78": "Yvelines", "79": "Deux-Sèvres", "80": "Somme",
    "81": "Tarn", "82": "Tarn-et-Garonne", "83": "Var", "84": "Vaucluse", "85": "Vendée",
    "86": "Vienne", "87": "Haute-Vienne", "88": "Vosges", "89": "Yonne",
    "90": "Territoire de Belfort", "91": "Essonne", "92": "Hauts-de-Seine",
    "93": "Seine-Saint-Denis", "94": "Val-de-Marne", "95": "Val-d'Oise",
    "971": "Guadeloupe", "972": "Martinique", "973": "Guyane", "974": "La Réunion",
    "975": "Saint-Pierre-et-Miquelon", "976": "Mayotte", "977": "Saint-Barthélemy",
    "978": "Saint-Martin", "986": "Wallis-et-Futuna", "987": "Polynésie française",
    "988": "Nouvelle-Calédonie",
}

# Les régions arrivent sans accents dans le catalogue : on rétablit l'écriture officielle.
REGIONS = {
    "Auvergne-Rhone-Alpes": "Auvergne-Rhône-Alpes",
    "Bourgogne-Franche-Comte": "Bourgogne-Franche-Comté",
    "Bretagne": "Bretagne", "Centre-Val de Loire": "Centre-Val de Loire",
    "Corse": "Corse", "Grand Est": "Grand Est", "Guadeloupe": "Guadeloupe",
    "Guyane": "Guyane", "Hauts-de-France": "Hauts-de-France",
    "Ile-de-France": "Île-de-France", "Île-de-France": "Île-de-France",
    "La Reunion": "La Réunion", "La Réunion": "La Réunion", "Martinique": "Martinique",
    "Mayotte": "Mayotte", "Normandie": "Normandie",
    "Nouvelle-Aquitaine": "Nouvelle-Aquitaine", "Occitanie": "Occitanie",
    "Pays de la Loire": "Pays de la Loire",
    "Provence-Alpes-Cote d'Azur": "Provence-Alpes-Côte d'Azur",
    "Provence-Alpes-Côte d'Azur": "Provence-Alpes-Côte d'Azur",
}

# Libellés lisibles pour les codes de type de diplôme les plus courants.
TYPES = {
    "BTS": "BTS", "BTSA": "BTS agricole", "CAP": "CAP", "CAPA": "CAP agricole",
    "TP": "Titre professionnel", "BAC PRO": "Bac pro", "BP": "Brevet professionnel",
    "CS": "Certificat de spécialisation", "MASTER": "Master", "DE": "Diplôme d'État",
    "BUT": "BUT", "Licence Professionnelle": "Licence professionnelle",
    "BPJEPS": "BPJEPS", "Titre ingenieur": "Titre d'ingénieur", "LICENCE": "Licence",
    "Grade_Licence": "Grade de licence", "Grade_Master": "Grade de master",
    "DEUST": "DEUST", "DEJEPS": "DEJEPS", "BMA": "Brevet des métiers d'art",
    "MC": "Mention complémentaire", "BAC TECHNO": "Bac technologique",
    "DipViGrM": "Diplôme visé (grade de master)", "DipViGrL": "Diplôme visé (grade de licence)",
    "DIPLOVIS": "Diplôme visé", "CA": "Certificat d'aptitude", "BPA": "Brevet professionnel agricole",
    "CPJEPS": "CPJEPS", "DESJEPS": "DESJEPS", "DNMADE": "DN MADE", "Autre": "Autre certification",
    "DNSEP": "DNSEP", "DSP": "Diplôme de spécialisation professionnelle",
    "BNMA": "Brevet national des métiers d'art", "DNSP": "DNSP",
    "DEEA": "Diplôme d'études en architecture", "DMA": "Diplôme des métiers d'art",
}

NIVEAUX = {"3": "CAP, BEP", "4": "Bac", "5": "Bac +2", "6": "Bac +3", "7": "Bac +5"}

TYPES_BCN = {
    "BAC PROFESSIONNEL": "Bac pro", "BAC PROFESSIONNEL AGRICOLE": "Bac pro",
    "LICENCE LMD": "Licence", "AUTRES DIPLOMES DE NIVEAU I": "Autre certification",
}


def sans_accent(mot):
    return unicodedata.normalize("NFD", mot).encode("ascii", "ignore").decode().lower()


_MOT = re.compile(r"[^\W\d_]+")


class Accentueur:
    """Remet les accents perdus dans les libellés RNCP (« Systemes » → « Systèmes »).

    Le dictionnaire est appris sur les libellés Carif-Oref du même export, qui
    gardent souvent leurs accents : pour chaque mot, on retient la forme accentuée
    si elle représente au moins 60 % des emplois de ce mot.
    """

    def __init__(self, textes):
        formes = defaultdict(Counter)
        for t in textes:
            for mot in _MOT.findall(t or ""):
                formes[sans_accent(mot)][mot.lower()] += 1
        self.table = {}
        for cle, c in formes.items():
            forme, n = c.most_common(1)[0]
            if forme != cle and n >= 0.6 * sum(c.values()) and n >= 2:
                self.table[cle] = forme

    def __call__(self, texte):
        def remplacer(m):
            mot = m.group(0)
            forme = self.table.get(sans_accent(mot)) if mot.isascii() else None
            if not forme:
                return mot
            if mot.isupper() and len(mot) > 1:
                return forme.upper()
            return forme[:1].upper() + forme[1:] if mot[0].isupper() else forme
        return _MOT.sub(remplacer, texte)


# ----------------------------------------------------------------------------
# Lecture des exports
# ----------------------------------------------------------------------------

# Un champ est soit vide, soit entre guillemets. Un guillemet isolé à l'intérieur
# d'un champ (fréquent dans les raisons sociales) n'est pas doublé dans l'export :
# on le garde comme un caractère normal tant qu'il n'est pas suivi de « ; ».
_CHAMP = re.compile(r'(?:^|;)("(?:[^"]|"(?!;|$))*"|[^;"]*)')


def lire_export(chemin):
    """Lit un export du catalogue et renvoie une liste de dictionnaires."""
    texte = Path(chemin).read_text(encoding="utf-8-sig")
    lignes = texte.splitlines()
    entete = next(csv.reader([lignes[0]], delimiter=";"))
    lignes_ok, ecartees = [], 0
    for ligne in lignes[1:]:
        if not ligne.strip():
            continue
        champs = [m.group(1) for m in _CHAMP.finditer(ligne)]
        if len(champs) != len(entete):
            ecartees += 1
            continue
        champs = [c[1:-1] if len(c) >= 2 and c[0] == c[-1] == '"' else c for c in champs]
        lignes_ok.append(dict(zip(entete, (c.strip() for c in champs))))
    if ecartees:
        print(f"  {Path(chemin).name} : {ecartees} lignes illisibles écartées", file=sys.stderr)
    return lignes_ok


def date_export(chemin):
    m = re.search(r"(\d{4}-\d{2}-\d{2})", Path(chemin).name)
    if m:
        return dt.date.fromisoformat(m.group(1))
    return dt.date.fromtimestamp(Path(chemin).stat().st_mtime)


def code_departement(code_commune):
    if code_commune.startswith("97") or code_commune.startswith("98"):
        return code_commune[:3]
    return code_commune[:2]


def titre(texte):
    """Met une chaîne en MAJUSCULES en forme « Titre » lisible."""
    if not texte or not texte.isupper():
        return texte
    petits = {"de", "du", "des", "la", "le", "les", "et", "en", "d", "l", "a", "au", "aux", "sur", "pour"}
    mots = re.split(r"(\s+|-|')", texte.lower())
    sortie = []
    for i, mot in enumerate(mots):
        if mot and mot not in petits or i == 0:
            mot = mot[:1].upper() + mot[1:]
        sortie.append(mot)
    return "".join(sortie)


def identifiant(url):
    return url.rstrip("/").rsplit("/", 1)[-1] if url else ""


# ----------------------------------------------------------------------------
# Construction des données de la carte
# ----------------------------------------------------------------------------

ANNEES = list(range(2021, 2031))

# Clé des fonds de carte CARTO (gratuite jusqu'à 5 millions de tuiles par mois).
# Depuis août 2026, les tuiles sans clé portent le filigrane « API KEY REQUIRED ».
CARTO_CLE = "cb1_3xt2_1_3185293106248dff757dcf73"


# Formacode® V14 (Centre Inffo) : les 65 champs sémantiques, regroupés en 14 grands domaines.
# Le regroupement reprend celui publié pour la V12 ; les deux champs créés depuis
# (314 Gestion de la qualité, 321 Encadrement, management) sont rangés avec leurs voisins.
CHAMPS = {
    "110": "Mathématiques", "114": "Physique", "115": "Chimie", "120": "Sciences naturelles",
    "122": "Sciences de la Terre", "125": "Environnement, aménagement", "130": "Science politique",
    "131": "Économie", "132": "Droit", "133": "Droit fiscal", "142": "Sciences humaines",
    "144": "Psychologie", "150": "Développement professionnel et personnel", "152": "Langues",
    "154": "Activité physique et sportive", "210": "Agriculture, production végétale",
    "213": "Pêche, aquaculture", "215": "Agroalimentaire", "216": "Textile", "217": "Habillement",
    "218": "Cuir, peau", "220": "Travaux publics", "222": "BTP : conception, organisation",
    "223": "Bâtiment gros œuvre", "224": "Bâtiment second œuvre", "226": "Génie climatique",
    "228": "Matériaux, produits chimiques", "230": "Travail des matériaux", "235": "Mécanique théorique",
    "236": "Mécanique : construction, réparation", "240": "Électricité", "241": "Énergie",
    "242": "Télécommunication", "243": "Électronique", "244": "Automatisme, informatique industrielle",
    "308": "Langages informatiques", "310": "Informatique, systèmes d'information et numérique",
    "313": "Qualité industrielle", "314": "Gestion de la qualité", "316": "Génie industriel",
    "317": "Manutention", "318": "Transport", "320": "Gestion des organisations",
    "321": "Encadrement, management", "326": "Gestion financière, comptabilité",
    "330": "Gestion des ressources humaines", "340": "Gestion commerciale, achats",
    "342": "Commerce international", "345": "Commerce", "350": "Secrétariat, assistanat",
    "410": "Banque, assurance", "420": "Services, commerces de proximité", "421": "Immobilier",
    "426": "Tourisme", "427": "Hôtellerie, restauration", "428": "Prévention, sécurité",
    "430": "Médecine", "434": "Santé", "440": "Action sociale",
    "445": "Ingénierie de formation, pédagogie", "450": "Art", "455": "Artisanat d'art",
    "460": "Industrie graphique, imprimerie", "462": "Audiovisuel",
    "463": "Information, communication numérique",
}
DOMAINES = [
    ("Formation générale, lettres et langues", ["150", "152", "142"]),
    ("Sciences humaines, économie, droit", ["131", "132", "133", "144", "130"]),
    ("Sciences", ["110", "114", "115", "120", "122", "235"]),
    ("Arts", ["450", "455", "462"]),
    ("Fonction production", ["316", "317", "313", "314"]),
    ("Agriculture", ["210", "213"]),
    ("Transformation", ["215", "216", "217", "218", "226", "228", "241"]),
    ("Génie civil, construction, bois", ["220", "222", "223", "224"]),
    ("Production mécanique", ["230", "236", "244"]),
    ("Électricité, électronique", ["240", "242", "243"]),
    ("Échange et gestion", ["320", "321", "326", "330", "340", "342", "345", "318", "410", "421"]),
    ("Information, communication", ["310", "308", "350", "460", "463"]),
    ("Services aux personnes", ["427", "426", "430", "434", "440", "445", "154"]),
    ("Services à la collectivité", ["125", "420", "428"]),
]


def cle_libelle(texte):
    texte = texte.replace("œ", "oe").replace("Œ", "OE").replace("æ", "ae").replace("’", "'")
    return re.sub(r"[^a-z0-9]+", " ", sans_accent(texte)).strip()


def lire_formacode(chemin):
    """Lit la table des descripteurs Formacode (code;libelle;champ) → {libellé normalisé: champ}."""
    champs = {}
    with open(chemin, encoding="utf-8-sig", newline="") as f:
        for ligne in csv.DictReader(f, delimiter=";"):
            champs.setdefault(cle_libelle(ligne["libelle"]), ligne["champ"])
    return champs


def lire_themes(chemin):
    """Lit la table RNCP → thèmes Formacode (export CSV du tableur « Thèmes »).

    Colonnes attendues : « RNCP » puis « Formacode 1 » à « Formacode 5 ».
    Le séparateur (virgule ou point-virgule) est détecté automatiquement.
    """
    texte = Path(chemin).read_text(encoding="utf-8-sig")
    dialecte = csv.Sniffer().sniff(texte[:5000], delimiters=",;")
    themes = defaultdict(list)
    for ligne in csv.DictReader(texte.splitlines(), dialect=dialecte):
        rncp = (ligne.get("RNCP") or "").strip()
        if not rncp:
            continue
        for cle, valeur in ligne.items():
            valeur = (valeur or "").strip()
            if cle and cle.startswith("Formacode") and valeur and valeur not in themes[rncp]:
                themes[rncp].append(valeur)
    return themes  # bits des rentrées (« Offre: Tags »)


def construire(etablissements, formations, themes_rncp=None, formacode=None):
    themes_rncp = themes_rncp or {}
    formacode = formacode or {}
    themes, index_theme, champ_theme = [], {}, []
    accentuer = Accentueur(f.get("Formation: libellé Carif-Oref") for f in formations)
    fiche_etab = {e["Siret"]: identifiant(e["Fiche catalogue"]) for e in etablissements}
    nda_etab = {e["Siret"]: e.get("Nda", "") for e in etablissements}

    dico_formations, index_formation = [], {}
    regions, index_region = [], {}
    types = Counter()
    lieux = {}

    for f in formations:
        geo = f.get("Lieu: géolocalisation", "")
        try:
            lat, lon = (round(float(x), 5) for x in geo.split(","))
        except ValueError:
            continue
        siret = f["Formateur: Siret"]
        cle_lieu = (siret, lat, lon)

        # --- la formation (dictionnaire partagé) ---
        rncp = f.get("Formation: code RNCP", "")
        cfd = f.get("Formation: code CFD", "")
        cle_f = (rncp, cfd)
        if cle_f not in index_formation:
            libelle = f.get("Formation: libellé RNCP") or titre(f.get("Formation: libellé long BCN", ""))
            libelle = accentuer(libelle[:1].upper() + libelle[1:]) if libelle else f.get("Formation: libellé Carif-Oref", "")
            code_type = f.get("Formation: code type certification RNCP", "")
            if not code_type:
                bcn = f.get("Formation: type certification BCN", "")
                if bcn.startswith("TH "):
                    code_type = "Titre RNCP"
                elif bcn.startswith("DIPLOMES CNAM"):
                    code_type = "Diplôme du Cnam"
                else:
                    code_type = TYPES_BCN.get(bcn, titre(bcn))
            type_aff = TYPES.get(code_type, code_type.replace("_", " "))
            niveau = (f.get("Formation: niveau BCN", "") or "?")[:1]
            onisep = re.search(r"FOR\.(\d+)", f.get("Formation: URL Onisep", "") or "")
            index_formation[cle_f] = len(dico_formations)
            idx_themes = []
            for t in themes_rncp.get(rncp, []):
                if t not in index_theme:
                    index_theme[t] = len(themes)
                    themes.append(t)
                    champ_theme.append(formacode.get(cle_libelle(t), ""))
                idx_themes.append(index_theme[t])
            dico_formations.append([libelle, type_aff, niveau, rncp, cfd, onisep.group(1) if onisep else "", idx_themes])
        idx_f = index_formation[cle_f]
        types[dico_formations[idx_f][1]] += 1

        # --- le lieu de formation (un point sur la carte) ---
        if cle_lieu not in lieux:
            region = REGIONS.get(f.get("Lieu: région", ""), f.get("Lieu: région", "") or "Non renseignée")
            if region not in index_region:
                index_region[region] = len(regions)
                regions.append(region)
            code_commune = f.get("Lieu: code commune", "")
            nom = f.get("Formateur: enseigne") or f.get("Formateur: raison sociale", "")
            raison = f.get("Formateur: raison sociale", "")
            resp = ""
            if f.get("Responsable: Siret") != siret:
                resp = f.get("Responsable: enseigne") or f.get("Responsable: raison sociale", "")
            lieux[cle_lieu] = {
                "nom": nom,
                "raison": raison if raison != nom else "",
                "siret": siret,
                "uai": f.get("Formateur: UAI", ""),
                "adresse": f.get("Lieu: adresse", ""),
                "cp": f.get("Lieu: code postal", ""),
                "ville": titre(f.get("Lieu: ville", "")),
                "dep": code_departement(code_commune),
                "region": index_region[region],
                "lat": lat, "lon": lon,
                "qualite": 1 if f.get("Paramètre réglementaire: Formateur certifié qualité ?") == "OUI" else 0,
                "resp": resp,
                "fiche": fiche_etab.get(siret, ""),
                "nda": nda_etab.get(siret, ""),
                "offres": {},
            }
        lieu = lieux[cle_lieu]

        # Rentrées concernées, regroupées sur une même formation du même lieu
        bits = 0
        for an in (f.get("Offre: Tags", "") or "").split(","):
            an = an.strip()
            if an.isdigit() and int(an) in ANNEES:
                bits |= 1 << ANNEES.index(int(an))
        duree = f.get("Formation: durée collectée", "")
        fiche_f = identifiant(f.get("Fiche catalogue", ""))
        if idx_f in lieu["offres"]:
            o = lieu["offres"][idx_f]
            o[1] |= bits
        else:
            lieu["offres"][idx_f] = [idx_f, bits, int(duree) if duree.isdigit() else 0, fiche_f]

    # --- sérialisation compacte ---
    points = []
    for l in lieux.values():
        offres = []
        for o in sorted(l["offres"].values(), key=lambda o: (dico_formations[o[0]][2], dico_formations[o[0]][0])):
            offres.extend(o)
        points.append([l["nom"], l["raison"], l["siret"], l["uai"], l["adresse"], l["cp"], l["ville"],
                       l["dep"], l["region"], l["lat"], l["lon"], l["qualite"], l["resp"], l["fiche"],
                       l["nda"], offres])
    points.sort(key=lambda p: (p[7], p[6], p[0]))

    # Communes (centre moyen des lieux) pour la recherche « autour de »
    communes = defaultdict(list)
    for p in points:
        communes[(p[6], p[5], p[7])].append((p[9], p[10]))
    liste_communes = [[v, cp, dep, round(sum(a for a, _ in c) / len(c), 4), round(sum(b for _, b in c) / len(c), 4)]
                      for (v, cp, dep), c in communes.items()]
    liste_communes.sort(key=lambda c: (c[0], c[1]))

    types_tries = [t for t, _ in types.most_common()]
    return {
        "formations": dico_formations,
        "points": points,
        "regions": regions,
        "communes": liste_communes,
        "types": types_tries,
        "annees": ANNEES,
        "themes": themes,
        "champTheme": champ_theme,
        "champs": {c: n for c, n in CHAMPS.items() if c in set(champ_theme)},
        "domaines": [[nom, [c for c in liste if c in set(champ_theme)]] for nom, liste in DOMAINES
                     if any(c in set(champ_theme) for c in liste)],
    }


# ----------------------------------------------------------------------------
# Écriture du HTML
# ----------------------------------------------------------------------------

def ecrire_html(donnees, sortie, date_donnees):
    gabarit = GABARIT
    donnees = dict(donnees)
    donnees["departements"] = DEPARTEMENTS
    donnees["niveaux"] = NIVEAUX
    donnees["date"] = date_donnees.strftime("%d/%m/%Y")
    donnees["carto"] = CARTO_CLE
    js = json.dumps(donnees, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    html = gabarit.replace("/*__DONNEES__*/null", js)
    Path(sortie).write_text(html, encoding="utf-8")
    return len(html.encode("utf-8"))


# Gabarit HTML de la carte : les données sont injectées à la place de /*__DONNEES__*/null.
GABARIT = r'''<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Carte des CFA et de leurs formations en apprentissage</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  :root {
    --vj: #9dbe1a;          /* vert-jaune, couleur principale */
    --vj-fonce: #55680c;
    --vj-clair: #f3f8df;
    --rv: #a1205f;          /* rouge-violet, couleur complémentaire */
    --rv-clair: #f8e6ef;
    --texte: #23271c;
    --gris: #6b7060;
    --bord: #e4e8d8;
    --fond: #ffffff;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: var(--texte); background: var(--fond); }
  #app { display: flex; height: 100vh; }
  #panneau { width: 400px; min-width: 400px; display: flex; flex-direction: column; border-right: 1px solid var(--bord); background: var(--fond); }
  #carte { flex: 1; }
  header { padding: 16px 18px 12px; border-bottom: 3px solid var(--vj); }
  header h1 { font-size: 19px; margin: 0 0 4px; font-weight: 700; letter-spacing: -0.2px; }
  header p { margin: 0; font-size: 12.5px; color: var(--gris); }
  #filtres { padding: 12px 18px 6px; border-bottom: 1px solid var(--bord); overflow-y: auto; max-height: 52vh; }
  .bloc { margin-bottom: 11px; }
  .bloc > label, .titre-bloc { display: block; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; color: var(--vj-fonce); margin-bottom: 4px; }
  input[type=text], input[type=search], select { width: 100%; padding: 7px 9px; border: 1px solid var(--bord); border-radius: 6px; font: inherit; font-size: 14px; background: #fff; color: var(--texte); }
  input:focus, select:focus { outline: 2px solid var(--vj); outline-offset: 0; border-color: var(--vj); }
  .ligne { display: flex; gap: 8px; }
  .ligne > * { flex: 1; }
  .ligne > .etroit { flex: 0 0 96px; }
  .puces { display: flex; flex-wrap: wrap; gap: 5px; }
  .puce { border: 1px solid var(--bord); border-radius: 14px; padding: 4px 10px; font-size: 12.5px; cursor: pointer; user-select: none; background: #fff; }
  .puce input { display: none; }
  .puce.actif { background: var(--vj); border-color: var(--vj); color: #1b2104; font-weight: 600; }
  .bloc > label.case { text-transform: none; letter-spacing: 0; font-weight: 400; color: var(--texte); font-size: 13.5px; margin: 0; }
  #panneau.fiche-ouverte #filtres, #panneau.fiche-ouverte #compteur { display: none; }
  .case { display: flex; align-items: center; gap: 6px; font-size: 13.5px; cursor: pointer; }
  .case input { accent-color: var(--vj-fonce); }
  .boutons { display: flex; gap: 8px; margin: 4px 0 8px; }
  button { font: inherit; font-size: 13px; padding: 7px 12px; border-radius: 6px; cursor: pointer; border: 1px solid var(--bord); background: #fff; color: var(--texte); }
  button:hover { border-color: var(--vj); }
  button.principal { background: var(--rv); border-color: var(--rv); color: #fff; }
  button.principal:hover { background: #861a4f; }
  #compteur { padding: 9px 18px; font-size: 13.5px; background: var(--vj-clair); border-bottom: 1px solid var(--bord); }
  #compteur b { color: var(--vj-fonce); }
  #liste, #fiche { flex: 1; overflow-y: auto; }
  .resultat { padding: 9px 18px; border-bottom: 1px solid var(--bord); cursor: pointer; }
  .resultat:hover { background: var(--vj-clair); }
  .resultat .nom { font-weight: 600; font-size: 14px; }
  .resultat .meta { font-size: 12.5px; color: var(--gris); margin-top: 2px; }
  .resultat .nb { color: var(--rv); font-weight: 600; }
  .plus { padding: 10px 18px; font-size: 12.5px; color: var(--gris); }
  #fiche { display: none; padding: 0 0 20px; }
  #fiche .haut { padding: 12px 18px; border-bottom: 1px solid var(--bord); }
  #fiche h2 { font-size: 17px; margin: 8px 0 2px; }
  #fiche .sous { font-size: 12.5px; color: var(--gris); }
  #fiche .adresse { font-size: 13.5px; margin-top: 8px; line-height: 1.45; }
  .retour { border: none; padding: 0; color: var(--rv); font-weight: 600; background: none; }
  .badge { display: inline-block; font-size: 11.5px; padding: 2px 8px; border-radius: 10px; background: var(--vj-clair); color: var(--vj-fonce); font-weight: 600; margin: 6px 6px 0 0; }
  .liens { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
  .liens a { font-size: 12.5px; text-decoration: none; color: var(--rv); border: 1px solid var(--rv); border-radius: 6px; padding: 5px 9px; }
  .liens a:hover { background: var(--rv-clair); }
  .liens a.google { background: var(--rv); color: #fff; }
  .infos { font-size: 12.5px; color: var(--gris); margin-top: 8px; line-height: 1.5; }
  .titre-formations { display: flex; justify-content: space-between; align-items: baseline; padding: 12px 18px 4px; }
  .titre-formations h3 { margin: 0; font-size: 14.5px; }
  .titre-formations label { font-size: 12.5px; color: var(--gris); }
  .niveau { padding: 8px 18px 2px; font-size: 11.5px; font-weight: 700; text-transform: uppercase; letter-spacing: .5px; color: var(--vj-fonce); }
  .formation { padding: 7px 18px 7px 15px; border-left: 3px solid transparent; }
  .formation.correspond { border-left-color: var(--rv); background: #fdf7fa; }
  .formation .type { display: inline-block; font-size: 11px; font-weight: 700; color: var(--rv); background: var(--rv-clair); border-radius: 4px; padding: 1px 6px; margin-right: 6px; }
  .formation .lib { font-size: 13.5px; }
  .formation .det { font-size: 12px; color: var(--gris); margin-top: 2px; }
  .formation .det a { color: var(--rv); }
  .formation .themes { font-size: 11.5px; color: var(--vj-fonce); margin-top: 2px; }
  .leaflet-popup-content { font-size: 13px; margin: 10px 12px; }
  .leaflet-popup-content b { font-size: 13.5px; }
  .leaflet-popup-content button { margin-top: 6px; padding: 4px 9px; font-size: 12.5px; }
  .note { font-size: 11.5px; color: var(--gris); padding: 8px 18px 12px; border-top: 1px solid var(--bord); }
  .note a { color: var(--gris); }
  @media (max-width: 820px) {
    #app { flex-direction: column-reverse; }
    #panneau { width: 100%; min-width: 0; height: 58vh; border-right: none; border-top: 1px solid var(--bord); }
    #carte { height: 42vh; flex: none; }
    #filtres { max-height: 30vh; }
  }
</style>
</head>
<body>
<div id="app">
  <aside id="panneau">
    <header>
      <h1>Carte des CFA</h1>
      <p id="sous-titre"></p>
    </header>

    <div id="filtres">
      <div class="bloc">
        <label for="f-formation">Formation ou code RNCP</label>
        <input id="f-formation" type="search" list="dl-formations" placeholder="ex. BTS assurance, cuisinier, RNCP38635" autocomplete="off">
        <datalist id="dl-formations"></datalist>
      </div>
      <div class="bloc" id="bloc-domaine">
        <label for="f-domaine">Domaine</label>
        <select id="f-domaine"><option value="">Tous les domaines</option></select>
      </div>
      <div class="bloc" id="bloc-theme">
        <label for="f-theme">Thème (Formacode)</label>
        <input id="f-theme" type="search" list="dl-themes" placeholder="ex. agriculture, cuisine, logistique" autocomplete="off">
        <datalist id="dl-themes"></datalist>
      </div>
      <div class="bloc">
        <span class="titre-bloc">Niveau</span>
        <div class="puces" id="f-niveaux"></div>
      </div>
      <div class="bloc ligne">
        <div>
          <label for="f-type" class="titre-bloc">Type de diplôme</label>
          <select id="f-type"><option value="">Tous</option></select>
        </div>
        <div class="etroit">
          <label for="f-annee" class="titre-bloc">Rentrée</label>
          <select id="f-annee"><option value="">Toutes</option></select>
        </div>
      </div>
      <div class="bloc">
        <label for="f-commune">Autour d'une ville</label>
        <div class="ligne">
          <input id="f-commune" type="search" list="dl-communes" placeholder="Ville ou code postal" autocomplete="off">
          <select id="f-rayon" class="etroit">
            <option value="5">5 km</option><option value="10">10 km</option><option value="20" selected>20 km</option>
            <option value="30">30 km</option><option value="50">50 km</option><option value="100">100 km</option>
          </select>
        </div>
        <datalist id="dl-communes"></datalist>
      </div>
      <div class="bloc ligne">
        <div>
          <label for="f-region" class="titre-bloc">Région</label>
          <select id="f-region"><option value="">Toutes</option></select>
        </div>
        <div>
          <label for="f-dep" class="titre-bloc">Département</label>
          <select id="f-dep"><option value="">Tous</option></select>
        </div>
      </div>
      <div class="bloc">
        <label for="f-nom">Nom du CFA, UAI ou SIRET</label>
        <input id="f-nom" type="search" placeholder="ex. MFR, CFA BTP, 0881529J" autocomplete="off">
      </div>
      <div class="bloc">
        <label class="case"><input type="checkbox" id="f-qualite"> Organismes certifiés qualité (Qualiopi) uniquement</label>
      </div>
      <div class="boutons">
        <button id="b-reinit">Réinitialiser</button>
        <button id="b-export" class="principal">Exporter en CSV</button>
      </div>
    </div>

    <div id="compteur"></div>
    <div id="liste"></div>
    <div id="fiche"></div>
    <div class="note">Source : <a href="https://catalogue-apprentissage.intercariforef.org" target="_blank" rel="noopener">Catalogue des formations en apprentissage</a> (Réseau des Carif-Oref), export du <span id="date-donnees"></span>. Fond de carte © OpenStreetMap, © CARTO.</div>
  </aside>
  <main id="carte"></main>
</div>

<script>
const D = /*__DONNEES__*/null;

// --------------------------------------------------------------------------
// Outils
// --------------------------------------------------------------------------
const $ = id => document.getElementById(id);
const norm = s => (s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const echap = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const nf = n => n.toLocaleString("fr-FR");
const URL_CAT = "https://catalogue-apprentissage.intercariforef.org";
const URL_ONISEP = "https://www.onisep.fr/http/redirection/formation/slug/FOR.";
function distanceKm(a1, o1, a2, o2) {
  const r = Math.PI / 180, dA = (a2 - a1) * r, dO = (o2 - o1) * r;
  const h = Math.sin(dA / 2) ** 2 + Math.cos(a1 * r) * Math.cos(a2 * r) * Math.sin(dO / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(h));
}
const nomDep = code => D.departements[code] || code;
const annees = bits => D.annees.filter((a, i) => bits & (1 << i));

// --------------------------------------------------------------------------
// Préparation des données
// --------------------------------------------------------------------------
const F = D.formations;                 // [libellé, type, niveau, rncp, cfd, onisep]
const P = D.points;                     // [nom, raison, siret, uai, adresse, cp, ville, dep, région, lat, lon, qualité, responsable, fiche, nda, offres]
const fTexte = F.map(f => norm(f[0] + " " + f[1] + " " + f[3] + " " + f[4]));
const T = D.themes || [];
const tTexte = T.map(norm);
if (!T.length) $("bloc-theme").style.display = "none";
const CT = D.champTheme || [];
if (!(D.domaines || []).length) $("bloc-domaine").style.display = "none";
(D.domaines || []).forEach(([nom, champs], i) => {
  $("f-domaine").insertAdjacentHTML("beforeend", `<option value="d${i}">${echap(nom)}</option>`);
  champs.map(c => [D.champs[c], c]).sort((a, b) => a[0].localeCompare(b[0], "fr"))
    .forEach(([n, c]) => $("f-domaine").insertAdjacentHTML("beforeend", `<option value="c${c}">\u2003${echap(n)}</option>`));
});
function champsChoisis() {
  const v = $("f-domaine").value;
  if (!v) return null;
  return new Set(v[0] === "d" ? D.domaines[+v.slice(1)][1] : [v.slice(1)]);
}
function remplirThemes() {
  const ch = champsChoisis();
  $("dl-themes").innerHTML = T.map((t, i) => [t, i]).filter(([, i]) => !ch || ch.has(CT[i]))
    .sort((a, b) => a[0].localeCompare(b[0], "fr")).map(([t]) => `<option value="${echap(t)}">`).join("");
}
const pTexte = P.map(p => norm(p[0] + " " + p[1] + " " + p[3] + " " + p[2] + " " + p[12]));
const depRegion = {};
P.forEach(p => { depRegion[p[7]] = p[8]; });

$("sous-titre").textContent = `${nf(P.length)} lieux de formation en apprentissage et leurs formations`;
$("date-donnees").textContent = D.date;

// Listes des filtres
Object.entries(D.niveaux).forEach(([n, lib]) => {
  const l = document.createElement("label");
  l.className = "puce"; l.dataset.niveau = n;
  l.innerHTML = `<input type="checkbox" value="${n}">${n} · ${lib}`;
  l.querySelector("input").addEventListener("change", e => { l.classList.toggle("actif", e.target.checked); filtrer(); });
  $("f-niveaux").appendChild(l);
});
D.types.forEach(t => $("f-type").insertAdjacentHTML("beforeend", `<option>${echap(t)}</option>`));
const anneesPresentes = new Set();
P.forEach(p => { const o = p[15]; for (let i = 1; i < o.length; i += 4) annees(o[i]).forEach(a => anneesPresentes.add(a)); });
[...anneesPresentes].sort().forEach(a => { if (a >= new Date().getFullYear() - 1) $("f-annee").insertAdjacentHTML("beforeend", `<option>${a}</option>`); });
D.regions.map((r, i) => [r, i]).sort((a, b) => a[0].localeCompare(b[0], "fr")).forEach(([r, i]) =>
  $("f-region").insertAdjacentHTML("beforeend", `<option value="${i}">${echap(r)}</option>`));
function remplirDeps() {
  const reg = $("f-region").value, actuel = $("f-dep").value;
  $("f-dep").innerHTML = '<option value="">Tous</option>';
  Object.keys(depRegion).sort((a, b) => a.localeCompare(b, "fr", {numeric: true}))
    .filter(d => reg === "" || String(depRegion[d]) === reg)
    .forEach(d => $("f-dep").insertAdjacentHTML("beforeend", `<option value="${d}">${d} · ${echap(nomDep(d))}</option>`));
  if ([...$("f-dep").options].some(o => o.value === actuel)) $("f-dep").value = actuel;
}
remplirDeps();
const libellesUniques = [...new Set(F.map(f => f[0]))].sort((a, b) => a.localeCompare(b, "fr"));
$("dl-formations").innerHTML = libellesUniques.map(l => `<option value="${echap(l)}">`).join("");
remplirThemes();
$("dl-communes").innerHTML = D.communes.map(c => `<option value="${echap(c[0])} (${c[1]})">`).join("");

// --------------------------------------------------------------------------
// Carte
// --------------------------------------------------------------------------
const carte = L.map("carte", {preferCanvas: true, zoomControl: true}).setView([46.6, 2.4], 6);
// Fond CARTO clair sans libellés, puis les noms de lieux à partir du zoom 8
// (aux petits zooms, CARTO affiche les noms de pays et de régions en anglais).
const CARTO = n => `https://basemaps.cartocdn.com/rastertiles/${n}/{z}/{x}/{y}.png?key=${D.carto}`;
const ATTRIBUTION = '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>';
L.tileLayer(CARTO("light_nolabels"), {attribution: ATTRIBUTION, maxZoom: 19}).addTo(carte);
carte.createPane("libelles");
carte.getPane("libelles").style.zIndex = 450;
carte.getPane("libelles").style.pointerEvents = "none";
const libelles = L.tileLayer(CARTO("light_only_labels"), {pane: "libelles", maxZoom: 19});
const majLibelles = () => carte.getZoom() >= 8 ? libelles.addTo(carte) : libelles.remove();
carte.on("zoomend", majLibelles); majLibelles();
const rendu = L.canvas({padding: 0.5});
const STYLE = {radius: 5, weight: 1, color: "#4b5c09", fillColor: "#9dbe1a", fillOpacity: 0.85, renderer: rendu};
const STYLE_SEL = {radius: 9, weight: 2, color: "#ffffff", fillColor: "#a1205f", fillOpacity: 1};
const couche = L.layerGroup().addTo(carte);
const marqueurs = P.map((p, i) => {
  const m = L.circleMarker([p[9], p[10]], STYLE);
  m.on("click", () => ouvrirFiche(i, false));
  m.bindTooltip(() => `<b>${echap(p[0])}</b><br>${echap(p[6])} (${p[7]})`, {direction: "top", offset: [0, -4]});
  return m;
});
let cercle = null, selection = null;

// --------------------------------------------------------------------------
// Filtrage
// --------------------------------------------------------------------------
let visibles = [];       // [indexPoint, nbFormationsCorrespondantes, distance]
let fOk = null, bitAnnee = 0, filtreFormationActif = false;

function communeChoisie() {
  const v = norm($("f-commune").value.trim());
  if (!v) return null;
  return D.communes.find(c => norm(`${c[0]} (${c[1]})`) === v)
      || D.communes.find(c => c[1] === v)
      || D.communes.find(c => norm(c[0]) === v) || null;
}

function filtrer(recadrer = true) {
  const mots = norm($("f-formation").value).split(/\s+/).filter(Boolean);
  const niveaux = [...document.querySelectorAll("#f-niveaux input:checked")].map(i => i.value);
  const type = $("f-type").value;
  const annee = $("f-annee").value;
  bitAnnee = annee ? 1 << D.annees.indexOf(+annee) : 0;
  // Thème : un thème choisi dans la liste, sinon tous les thèmes qui contiennent les mots saisis
  const saisieTheme = norm($("f-theme").value.trim());
  const ch = champsChoisis();
  let themesOk = null;
  if (saisieTheme || ch) {
    const exact = saisieTheme ? tTexte.indexOf(saisieTheme) : -1;
    const motsTheme = saisieTheme.split(/\s+/).filter(Boolean);
    themesOk = new Set(T.map((t, i) => i).filter(i =>
      (!ch || ch.has(CT[i])) && (exact >= 0 ? i === exact : motsTheme.every(m => tTexte[i].includes(m)))));
  }
  filtreFormationActif = mots.length > 0 || niveaux.length > 0 || type !== "" || bitAnnee !== 0 || themesOk !== null;
  fOk = F.map((f, i) => (!mots.length || mots.every(m => fTexte[i].includes(m)))
                        && (!themesOk || f[6].some(t => themesOk.has(t)))
                        && (!niveaux.length || niveaux.includes(f[2]))
                        && (!type || f[1] === type));

  const reg = $("f-region").value, dep = $("f-dep").value;
  const motsNom = norm($("f-nom").value).split(/\s+/).filter(Boolean);
  const qualite = $("f-qualite").checked;
  const commune = communeChoisie(), rayon = +$("f-rayon").value;

  visibles = [];
  P.forEach((p, i) => {
    if (reg !== "" && String(p[8]) !== reg) return;
    if (dep && p[7] !== dep) return;
    if (qualite && !p[11]) return;
    if (motsNom.length && !motsNom.every(m => pTexte[i].includes(m))) return;
    let dist = null;
    if (commune) { dist = distanceKm(commune[3], commune[4], p[9], p[10]); if (dist > rayon) return; }
    const o = p[15]; let n = 0;
    for (let k = 0; k < o.length; k += 4) if (fOk[o[k]] && (!bitAnnee || (o[k + 1] & bitAnnee))) n++;
    if (n === 0) return;
    visibles.push([i, n, dist]);
  });
  if (commune) visibles.sort((a, b) => a[2] - b[2]);

  couche.clearLayers();
  visibles.forEach(v => couche.addLayer(marqueurs[v[0]]));
  if (cercle) { carte.removeLayer(cercle); cercle = null; }
  if (commune) cercle = L.circle([commune[3], commune[4]], {radius: rayon * 1000, color: "#a1205f", weight: 1.5, fillOpacity: 0.04, dashArray: "4 4", interactive: false}).addTo(carte);

  const nbF = visibles.reduce((s, v) => s + v[1], 0);
  $("compteur").innerHTML = `<b>${nf(visibles.length)}</b> lieu${visibles.length > 1 ? "x" : ""} de formation · <b>${nf(nbF)}</b> formation${nbF > 1 ? "s" : ""}`;
  afficherListe();
  if (recadrer) recadrerCarte(commune, reg, dep, motsNom.length > 0 || filtreFormationActif);
}

function recadrerCarte(commune, reg, dep, autre) {
  if (commune) { carte.fitBounds(cercle.getBounds(), {padding: [20, 20]}); return; }
  if (!visibles.length) return;
  if (reg !== "" || dep || (autre && visibles.length < 400)) {
    const b = L.latLngBounds(visibles.map(v => [P[v[0]][9], P[v[0]][10]]));
    carte.fitBounds(b, {padding: [30, 30], maxZoom: 13});
  }
}

function afficherListe() {
  $("fiche").style.display = "none"; $("liste").style.display = "block";
  $("panneau").classList.remove("fiche-ouverte");
  if (selection) { carte.removeLayer(selection); selection = null; }
  const max = 300;
  const html = visibles.slice(0, max).map(([i, n, d]) => {
    const p = P[i];
    const dist = d !== null ? ` · ${d < 10 ? d.toFixed(1).replace(".", ",") : Math.round(d)} km` : "";
    return `<div class="resultat" data-i="${i}"><div class="nom">${echap(p[0])}</div>
      <div class="meta">${echap(p[6])} (${p[7]})${dist} · <span class="nb">${n} formation${n > 1 ? "s" : ""}</span></div></div>`;
  }).join("");
  const reste = visibles.length > max ? `<div class="plus">… et ${nf(visibles.length - max)} autres lieux : précisez la recherche ou zoomez sur la carte.</div>` : "";
  const vide = visibles.length ? "" : `<div class="plus">Aucun lieu de formation ne correspond à ces critères.</div>`;
  $("liste").innerHTML = html + reste + vide;
  $("liste").scrollTop = 0;
}
$("liste").addEventListener("click", e => {
  const r = e.target.closest(".resultat");
  if (r) ouvrirFiche(+r.dataset.i, true);
});

// --------------------------------------------------------------------------
// Fiche d'un lieu de formation
// --------------------------------------------------------------------------
let ficheOuverte = null;

function ouvrirFiche(i, zoomer) {
  const p = P[i];
  ficheOuverte = i;
  if (selection) carte.removeLayer(selection);
  selection = L.circleMarker([p[9], p[10]], STYLE_SEL).addTo(carte);
  if (zoomer) carte.setView([p[9], p[10]], Math.max(carte.getZoom(), 12));

  const recherche = `${p[0]} ${nomDep(p[7])}`;
  const liens = [
    `<a class="google" href="https://www.google.com/search?q=${encodeURIComponent(recherche)}" target="_blank" rel="noopener">Rechercher sur Google</a>`,
    p[13] ? `<a href="${URL_CAT}/etablissement/${p[13]}" target="_blank" rel="noopener">Fiche du catalogue</a>` : "",
    `<a href="https://www.google.com/maps/search/?api=1&query=${p[9]},${p[10]}" target="_blank" rel="noopener">Itinéraire</a>`,
  ].join("");
  const infos = [
    p[1] ? `Raison sociale : ${echap(p[1])}` : "",
    p[12] ? `Organisme responsable : ${echap(p[12])}` : "",
    `SIRET : ${p[2]}${p[3] ? ` · UAI : ${p[3]}` : ""}${p[14] ? ` · NDA : ${p[14]}` : ""}`,
  ].filter(Boolean).join("<br>");

  $("fiche").innerHTML = `
    <div class="haut">
      <button class="retour" id="b-retour">← Retour aux résultats</button>
      <h2>${echap(p[0])}</h2>
      <div class="sous">${echap(nomDep(p[7]))} (${p[7]}) · ${echap(D.regions[p[8]])}</div>
      <div class="adresse">${echap(p[4])}<br>${p[5]} ${echap(p[6])}</div>
      ${p[11] ? '<span class="badge">Certifié qualité (Qualiopi)</span>' : ""}
      <div class="liens">${liens}</div>
      <div class="infos">${infos}</div>
    </div>
    <div class="titre-formations">
      <h3 id="titre-liste-f"></h3>
      ${filtreFormationActif ? '<label class="case"><input type="checkbox" id="c-toutes"> toutes</label>' : ""}
    </div>
    <div id="formations-lieu"></div>`;
  $("b-retour").onclick = () => { fermerFiche(); };
  if ($("c-toutes")) $("c-toutes").onchange = () => afficherFormations(i);
  afficherFormations(i);
  $("liste").style.display = "none"; $("fiche").style.display = "block"; $("fiche").scrollTop = 0;
  $("panneau").classList.add("fiche-ouverte");
}

function afficherFormations(i) {
  const o = P[i][15];
  const toutes = !filtreFormationActif || ($("c-toutes") && $("c-toutes").checked);
  const items = [];
  for (let k = 0; k < o.length; k += 4) {
    const ok = fOk[o[k]] && (!bitAnnee || (o[k + 1] & bitAnnee));
    if (ok || toutes) items.push({f: F[o[k]], bits: o[k + 1], duree: o[k + 2], fiche: o[k + 3], ok});
  }
  const total = o.length / 4;
  $("titre-liste-f").textContent = toutes ? `${total} formation${total > 1 ? "s" : ""}` : `${items.length} formation${items.length > 1 ? "s" : ""} sur ${total}`;
  let html = "", niveauCourant = null;
  items.forEach(it => {
    const f = it.f;
    if (f[2] !== niveauCourant) {
      niveauCourant = f[2];
      html += `<div class="niveau">Niveau ${f[2]}${D.niveaux[f[2]] ? " · " + D.niveaux[f[2]] : ""}</div>`;
    }
    const det = [
      f[3] || (f[4] ? "CFD " + f[4] : ""),
      it.duree ? `${it.duree} an${it.duree > 1 ? "s" : ""}` : "",
      annees(it.bits).length ? "rentrée " + annees(it.bits).join(", ") : "",
      f[5] ? `<a href="${URL_ONISEP}${f[5]}" target="_blank" rel="noopener">Onisep</a>` : "",
      it.fiche ? `<a href="${URL_CAT}/formation/${it.fiche}" target="_blank" rel="noopener">fiche</a>` : "",
    ].filter(Boolean).join(" · ");
    const th = f[6].length ? `<div class="themes">${f[6].map(t => echap(T[t])).join(" · ")}</div>` : "";
    html += `<div class="formation${filtreFormationActif && it.ok ? " correspond" : ""}">
      <div class="lib"><span class="type">${echap(f[1])}</span>${echap(f[0])}</div>
      <div class="det">${det}</div>${th}</div>`;
  });
  $("formations-lieu").innerHTML = html;
}

function fermerFiche() {
  ficheOuverte = null;
  if (selection) { carte.removeLayer(selection); selection = null; }
  $("fiche").style.display = "none"; $("liste").style.display = "block";
  $("panneau").classList.remove("fiche-ouverte");
}

// --------------------------------------------------------------------------
// Export CSV des résultats
// --------------------------------------------------------------------------
$("b-export").onclick = () => {
  const entete = ["CFA", "Raison sociale", "SIRET", "UAI", "Qualiopi", "Adresse", "Code postal", "Ville", "Département", "Région",
                  "Formation", "Type de diplôme", "Niveau", "Code RNCP", "Code CFD", "Thèmes (Formacode)", "Durée (ans)", "Rentrées", "Fiche catalogue"];
  const lignes = [entete];
  visibles.forEach(([i]) => {
    const p = P[i], o = p[15];
    for (let k = 0; k < o.length; k += 4) {
      if (!(fOk[o[k]] && (!bitAnnee || (o[k + 1] & bitAnnee)))) continue;
      const f = F[o[k]];
      lignes.push([p[0], p[1] || p[0], p[2], p[3], p[11] ? "oui" : "non", p[4], p[5], p[6], `${p[7]} ${nomDep(p[7])}`, D.regions[p[8]],
                   f[0], f[1], f[2], f[3], f[4], f[6].map(t => T[t]).join(", "), o[k + 2] || "", annees(o[k + 1]).join(" "), o[k + 3] ? `${URL_CAT}/formation/${o[k + 3]}` : ""]);
    }
  });
  const csv = "﻿" + lignes.map(l => l.map(v => `"${String(v ?? "").replace(/"/g, '""')}"`).join(";")).join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
  a.download = "cfa_formations.csv";
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
};

// --------------------------------------------------------------------------
// Événements
// --------------------------------------------------------------------------
let minuteur = null;
const differe = () => { clearTimeout(minuteur); minuteur = setTimeout(() => filtrer(), 250); };
$("f-formation").addEventListener("input", differe);
$("f-theme").addEventListener("input", differe);
$("f-nom").addEventListener("input", differe);
$("f-commune").addEventListener("input", () => { if (!$("f-commune").value || communeChoisie()) differe(); });
["f-type", "f-annee", "f-rayon", "f-dep", "f-qualite"].forEach(id => $(id).addEventListener("change", () => filtrer()));
$("f-domaine").addEventListener("change", () => { remplirThemes(); filtrer(); });
$("f-region").addEventListener("change", () => { remplirDeps(); filtrer(); });
$("b-reinit").onclick = () => {
  ["f-formation", "f-theme", "f-nom", "f-commune"].forEach(id => $(id).value = "");
  ["f-type", "f-annee", "f-region", "f-domaine"].forEach(id => $(id).value = "");
  remplirThemes();
  $("f-rayon").value = "20"; $("f-qualite").checked = false;
  document.querySelectorAll("#f-niveaux .puce").forEach(l => { l.classList.remove("actif"); l.querySelector("input").checked = false; });
  remplirDeps(); $("f-dep").value = "";
  fermerFiche(); filtrer(false); carte.setView([46.6, 2.4], 6);
};

filtrer(false);
</script>
</body>
</html>
'''


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--etablissements", required=True, help="export CSV des établissements du catalogue")
    p.add_argument("--formations", required=True, help="export CSV des formations du catalogue")
    p.add_argument("--themes", help="table RNCP → thèmes Formacode (CSV), pour le filtre par thème")
    p.add_argument("--formacode", help="descripteurs Formacode V14 (CSV code;libelle;champ), pour le filtre par domaine")
    p.add_argument("--sortie", default="carte_cfa.html", help="fichier HTML à produire")
    args = p.parse_args()

    print("Lecture des établissements…")
    etablissements = lire_export(args.etablissements)
    print(f"  {len(etablissements)} établissements")
    print("Lecture des formations…")
    formations = lire_export(args.formations)
    print(f"  {len(formations)} offres de formation")

    themes = {}
    if args.themes:
        print("Lecture des thèmes…")
        themes = lire_themes(args.themes)
        print(f"  {len(themes)} certifications RNCP avec leurs thèmes")
    formacode = lire_formacode(args.formacode) if args.formacode else {}
    donnees = construire(etablissements, formations, themes, formacode)
    taille = ecrire_html(donnees, args.sortie, date_export(args.formations))
    nb_offres = sum(len(p[-1]) // 4 for p in donnees["points"])
    print(f"Carte écrite : {args.sortie} ({taille / 1e6:.1f} Mo)")
    print(f"  {len(donnees['points'])} lieux de formation, {nb_offres} formations par lieu, "
          f"{len(donnees['formations'])} diplômes différents")
    if args.themes:
        sans = sum(1 for p in donnees["points"] for k in range(0, len(p[-1]), 4) if not donnees["formations"][p[-1][k]][6])
        print(f"  {len(donnees['themes'])} thèmes ; {sans} formations par lieu sans thème connu")
    if args.formacode:
        orphelins = [t for t, c in zip(donnees["themes"], donnees["champTheme"]) if not c]
        print(f"  {len(donnees['themes']) - len(orphelins)} thèmes rangés dans un domaine ; sans domaine : "
              + ", ".join(orphelins[:12]) + (" …" if len(orphelins) > 12 else ""))


if __name__ == "__main__":
    main()
