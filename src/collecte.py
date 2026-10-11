
import requests
import feedparser
import hashlib
import json

from datetime import datetime, timezone
from pathlib import Path


#  CONFIGURATION

url = "https://www.bis.org/doclist/bis_fsi_publs.rss"

# Emplacement du fichier JSON
dossier = Path("data/collecte")
fichier = dossier / "publications.json"

# Créer le dossier s'il n'existe pas
dossier.mkdir(parents=True, exist_ok=True)


#  RÉCUPÉRATION DU FLUX RSS

try:
    response = requests.get(url, timeout=20)
    response.raise_for_status()

    flux = feedparser.parse(response.content)

    if flux.bozo:
        print("Attention : le flux RSS présente une anomalie.")

except requests.RequestException as erreur:
    print("Erreur lors de la récupération du flux :", erreur)
    raise SystemExit(1)


#  CHARGER LES ANCIENNES PUBLICATIONS

if fichier.exists():
    with open(fichier, "r", encoding="utf-8") as f:
        publications = json.load(f)
else:
    publications = []

# Récupérer les identifiants déjà enregistrés
ids_existants = {
    article["id"]
    for article in publications
}


#  DATE DE COLLECTE

date_collecte = datetime.now(
    timezone.utc
).isoformat()


#  EXTRACTION DES PUBLICATIONS

nouvelles_publications = 0

for publication in flux.entries:

    titre = publication.get("title")
    lien = publication.get("link")
    date = publication.get("cb_publicationdate")
    resume = publication.get("summary")
    auteurs = publication.get("authors", [])

    # Ignorer les entrées sans titre ou sans URL
    if not titre or not lien:
        continue

    # Identifiant stable SHA-256
    identifiant = hashlib.sha256(
        lien.encode("utf-8")
    ).hexdigest()

    # Éviter les publications déjà enregistrées
    if identifiant in ids_existants:
        continue

    # Conversion de la date de publication
    if date:
        try:
            date = datetime.strptime(
                date, "%d %b %Y"
            ).date().isoformat()

        except ValueError:
            date = None

    # Extraction des noms des auteurs
    noms_auteurs = []

    for auteur in auteurs:
        nom = auteur.get("name")

        if nom:
            noms_auteurs.append(nom)

    # Construction du dictionnaire
    article = {
        "id": identifiant,
        "titre": titre,
        "url": lien,
        "date_publication": date,
        "date_collecte": date_collecte,
        "resume_original": resume,
        "auteur": noms_auteurs,
        "source": "BRI / BIS",
        "type_document": "publication"
    }

    # Ajouter la publication
    publications.append(article)

    # Mémoriser immédiatement son identifiant
    ids_existants.add(identifiant)

    nouvelles_publications += 1


#  ENREGISTREMENT EN JSON

with open(fichier, "w", encoding="utf-8") as f:
    json.dump(
        publications,
        f,
        ensure_ascii=False,
        indent=4
    )


#  BILAN DE LA COLLECTE

print("Collecte BRI terminée !")
print("Nouvelles publications :", nouvelles_publications)
print("Total des publications :", len(publications))
print("Fichier enregistré :", fichier.resolve())
