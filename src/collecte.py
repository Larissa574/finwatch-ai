
import requests
import feedparser
import hashlib
import json
import calendar

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import (
    urlsplit,
    urlunsplit,
    parse_qsl,
    urlencode
)


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
# 2. CONFIGURATION DU STOCKAGE
# ==========================================

dossier = Path("data/collecte")

fichier_historique = dossier / "publications.json"

fichier_nouvelles = (
    dossier / "nouvelles_publications.json"
)

dossier.mkdir(
    parents=True,
    exist_ok=True
)


# ==========================================
# 3. CHARGEMENT DE L'HISTORIQUE
# ==========================================

if fichier_historique.exists():

    with open(
        fichier_historique,
        "r",
        encoding="utf-8"
    ) as f:

        publications = json.load(f)

    if not isinstance(publications, list):
        raise ValueError(
            "L'historique doit contenir une liste JSON."
        )

else:
    publications = []


# Liste des articles nouveaux uniquement
nouvelles_publications = []
sources_en_erreur = []

print(
    "Publications déjà enregistrées :",
    len(publications)
)


# ==========================================
# 4. FONCTIONS UTILITAIRES
# ==========================================

def nettoyer_url(url):

    if not url:
        return None

    morceaux = urlsplit(url.strip())

    # Supprimer les paramètres publicitaires
    parametres = [
        (cle, valeur)
        for cle, valeur in parse_qsl(
            morceaux.query,
            keep_blank_values=True
        )
        if not cle.lower().startswith("utm_")
    ]

    return urlunsplit((
        morceaux.scheme.lower(),
        morceaux.netloc.lower(),
        morceaux.path,
        urlencode(parametres),
        ""
    ))


def generer_id(url):

    return hashlib.sha256(
        url.encode("utf-8")
    ).hexdigest()


def convertir_date(article):

    # Format particulier de la BRI
    date_bri = article.get("cb_publicationdate")

    if date_bri:
        try:
            return datetime.strptime(
                date_bri,
                "%d %b %Y"
            ).date().isoformat()

        except ValueError:
            pass

    # Dates standard des flux RSS et Atom
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


def enregistrer_json(chemin, donnees):

    # Écriture dans un fichier temporaire
    temporaire = chemin.with_suffix(
        chemin.suffix + ".tmp"
    )

    with open(
        temporaire,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            donnees,
            f,
            ensure_ascii=False,
            indent=4
        )

    # Remplacement du fichier précédent
    temporaire.replace(chemin)


# ==========================================
# 5. IDENTIFIANTS DÉJÀ ENREGISTRÉS
# ==========================================

ids_existants = {
    article["id"]
    for article in publications
    if article.get("id")
}

urls_existantes = {
    nettoyer_url(article.get("url"))
    for article in publications
    if article.get("url")
}


# ==========================================
# 6. NORMALISER UNE PUBLICATION
# ==========================================

def ajouter_publication(entree, nom_source):

    lien = nettoyer_url(entree.get("link"))
    titre = entree.get("title")

    if not lien or not titre:
        return False

    identifiant = generer_id(lien)

    # Empêcher les doublons
    if (
        identifiant in ids_existants
        or lien in urls_existantes
    ):
        return False

    date_collecte = datetime.now(
        timezone.utc
    ).isoformat()

    # Nos 9 champs contractuels
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

    # Historique complet
    publications.append(article)

    # Nouveautés de cette exécution
    nouvelles_publications.append(article)

    # Empêcher un second ajout
    ids_existants.add(identifiant)
    urls_existantes.add(lien)

    return True


# ==========================================
# 7. COLLECTE RSS
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
        raise ValueError("Format RSS / Atom non reconnu.")

    if flux.bozo:
        raise ValueError(f"Anomalie XML : {flux.get('bozo_exception')}")

    total = len(flux.entries)
    nouvelles = 0

    for entree in flux.entries:

        if ajouter_publication(
            entree,
            source["nom"]
        ):
            nouvelles += 1

    print("Publications trouvées :", total)
    print("Nouvelles publications :", nouvelles)


# ==========================================
# 8. COLLECTE API ARXIV
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
        raise ValueError("Format Atom non reconnu.")

    if flux.bozo:
        print("Anomalie XML :", flux.get("bozo_exception"))
        return

    total = len(flux.entries)
    nouvelles = 0

    for entree in flux.entries:

        if ajouter_publication(
            entree,
            "arXiv"
        ):
            nouvelles += 1

    print("Publications trouvées :", total)
    print("Nouvelles publications :", nouvelles)


# ==========================================
# 9. EXÉCUTION DES COLLECTES
# ==========================================

for source in sources_rss:

    try:
        collecter_rss(source)

    except (requests.RequestException, ValueError) as erreur:
        sources_en_erreur.append(source["nom"])
        print("Erreur pour", source["nom"], ":", type(erreur).__name__, erreur)

try:
    collecter_arxiv()

except (requests.RequestException, ValueError) as erreur:
    sources_en_erreur.append("arXiv")
    print("Erreur arXiv :", type(erreur).__name__, erreur)


# ==========================================
# 10. SAUVEGARDE DES DEUX JSON
# ==========================================

# Enregistrer toutes les publications
enregistrer_json(
    fichier_historique,
    publications
)

# Enregistrer uniquement les nouveautés
enregistrer_json(
    fichier_nouvelles,
    nouvelles_publications
)


# ==========================================
# 11. BILAN FINAL
# ==========================================

print("\n" + "=" * 55)
print("COLLECTE FINWATCH AI TERMINÉE")

print(
    "Total dans l'historique :",
    len(publications)
)

print(
    "Nouvelles publications à analyser :",
    len(nouvelles_publications)
)

print(
    "Historique :",
    fichier_historique.resolve()
)

print(
    "Nouveautés :",
    fichier_nouvelles.resolve()
)

if sources_en_erreur:
    print("COLLECTE PARTIELLE : sources en erreur :", ", ".join(sources_en_erreur))
    raise SystemExit(1)
