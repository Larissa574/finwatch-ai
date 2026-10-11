
import requests
import feedparser
import hashlib
import json
import calendar

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode


# ==========================================
# 1. CONFIGURATION DES SOURCES
# ==========================================

sources_rss = [
    {
        "nom": "BRI / BIS",
        "url": "https://www.bis.org/doclist/bis_fsi_publs.rss"
    },
    {
        "nom": "BCE - Supervision",
        "url": "https://www.bankingsupervision.europa.eu/rss/pub.html"
    },
    {
        "nom": "EBA - Actualites",
        "url": "https://www.eba.europa.eu/news-press/news/rss.xml"
    },
    {
        "nom": "Finextra AI",
        "url": "https://www.finextra.com/rss/channel.aspx?channel=ai"
    }
]

url_arxiv = "https://export.arxiv.org/api/query"

params_arxiv = {
    "search_query": (
        '(all:"machine learning" OR '
        'all:"artificial intelligence" OR '
        'all:"deep learning")'
        ' AND '
        '(ti:finance OR ti:financial OR '
        'ti:banking OR ti:credit OR '
        'ti:fraud OR ti:trading)'
    ),
    "start": 0,
    "max_results": 20,
    "sortBy": "submittedDate",
    "sortOrder": "descending"
}


# ==========================================
# 2. FICHIER DE STOCKAGE
# ==========================================

dossier = Path("data/collecte")
fichier = dossier / "publications.json"

dossier.mkdir(parents=True, exist_ok=True)

if fichier.exists():
    with open(fichier, "r", encoding="utf-8") as f:
        publications = json.load(f)

    if not isinstance(publications, list):
        raise ValueError(
            "Le fichier JSON doit contenir une liste."
        )
else:
    publications = []

print("Publications deja enregistrees :", len(publications))


# ==========================================
# 3. FONCTIONS COMMUNES
# ==========================================

def nettoyer_url(url):

    if not url:
        return None

    morceaux = urlsplit(url)

    # Supprimer les parametres de suivi publicitaire
    parametres = [
        (cle, valeur)
        for cle, valeur in parse_qsl(
            morceaux.query,
            keep_blank_values=True
        )
        if not cle.lower().startswith("utm_")
    ]

    return urlunsplit((
        morceaux.scheme,
        morceaux.netloc,
        morceaux.path,
        urlencode(parametres),
        ""
    ))


def generer_id(url):

    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()


def convertir_date(article):

    # Cas particulier de la BRI
    date_bri = article.get("cb_publicationdate")

    if date_bri:
        try:
            return datetime.strptime(
                date_bri,
                "%d %b %Y"
            ).date().isoformat()

        except ValueError:
            pass

    # Dates deja analysees par feedparser
    date_parsee = (
        article.get("published_parsed")
        or article.get("updated_parsed")
    )

    if date_parsee:
        timestamp = calendar.timegm(date_parsee)

        return datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc
        ).isoformat()

    return None


def extraire_auteurs(article):

    noms = []

    for auteur in article.get("authors", []):
        nom = auteur.get("name")

        if nom:
            noms.append(nom)

    return noms


# Identifiants des articles deja enregistres
ids_existants = {
    article["id"]
    for article in publications
    if article.get("id")
}

# Pour reconnaitre aussi les anciennes URL
urls_existantes = {
    nettoyer_url(article.get("url"))
    for article in publications
    if article.get("url")
}


# ==========================================
# 4. TRANSFORMER UNE PUBLICATION
# ==========================================

def ajouter_publication(entree, nom_source):

    lien = nettoyer_url(entree.get("link"))
    titre = entree.get("title")

    if not lien or not titre:
        return False

    identifiant = generer_id(lien)

    # Verification des doublons
    if (
        identifiant in ids_existants
        or lien in urls_existantes
    ):
        return False

    date_collecte = datetime.now(
        timezone.utc
    ).isoformat()

    article = {
        "id": identifiant,
        "titre": titre.strip(),
        "source": nom_source,
        "url": lien,
        "date_publication": convertir_date(entree),
        "date_collecte": date_collecte,
        "auteur": extraire_auteurs(entree),
        "resume_original": entree.get("summary"),
        "type_document": "publication"
    }

    publications.append(article)

    ids_existants.add(identifiant)
    urls_existantes.add(lien)

    return True


# ==========================================
# 5. COLLECTE DES FLUX RSS
# ==========================================

def collecter_rss(source):

    print("\n" + "=" * 55)
    print("SOURCE :", source["nom"])

    response = requests.get(
        source["url"],
        timeout=30,
        headers={
            "User-Agent": "FINWATCH-AI/0.1 (academic research)"
        }
    )

    response.raise_for_status()

    flux = feedparser.parse(response.content)

    if not flux.get("version"):
        print("Format RSS ou Atom non reconnu.")
        return

    if flux.bozo:
        print("Attention : anomalie XML.")
        print("Detail :", flux.get("bozo_exception"))
        return

    total = len(flux.entries)
    nouvelles = 0

    for entree in flux.entries:
        if ajouter_publication(
            entree,
            source["nom"]
        ):
            nouvelles += 1

    print("Publications trouvees :", total)
    print("Nouvelles publications :", nouvelles)


# ==========================================
# 6. COLLECTE ARXIV
# ==========================================

def collecter_arxiv():

    print("\n" + "=" * 55)
    print("SOURCE : arXiv")

    response = requests.get(
        url_arxiv,
        params=params_arxiv,
        timeout=45,
        headers={
            "User-Agent": "FINWATCH-AI/0.1 (academic research)"
        }
    )

    response.raise_for_status()

    flux = feedparser.parse(response.content)

    if flux.get("version") != "atom10":
        print("Reponse arXiv non reconnue.")
        return

    if flux.bozo:
        print("Anomalie XML arXiv.")
        return

    total = len(flux.entries)
    nouvelles = 0

    for entree in flux.entries:
        if ajouter_publication(entree, "arXiv"):
            nouvelles += 1

    print("Publications trouvees :", total)
    print("Nouvelles publications :", nouvelles)


# ==========================================
# 7. LANCEMENT DE LA COLLECTE
# ==========================================

for source in sources_rss:

    try:
        collecter_rss(source)

    except requests.RequestException as erreur:
        print(
            "Erreur de connexion :",
            type(erreur).__name__
        )

try:
    collecter_arxiv()

except requests.RequestException as erreur:
    print(
        "Erreur arXiv :",
        type(erreur).__name__
    )


# ==========================================
# 8. SAUVEGARDE JSON
# ==========================================

# Ecriture dans un fichier temporaire
temporaire = fichier.with_suffix(".json.tmp")

with open(
    temporaire,
    "w",
    encoding="utf-8"
) as f:

    json.dump(
        publications,
        f,
        ensure_ascii=False,
        indent=4
    )

# Remplacer le fichier principal
temporaire.replace(fichier)


# ==========================================
# 9. BILAN FINAL
# ==========================================

print("\n" + "=" * 55)

print("COLLECTE FINWATCH AI TERMINEE")

print(
    "Total de publications enregistrees :",
    len(publications)
)

print("Fichier JSON :", fichier.resolve())
