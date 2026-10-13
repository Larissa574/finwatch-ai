
"""Importe l'historique JSON dans Google Sheets sans doublons."""
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import gspread

BASE_DIR = Path(__file__).resolve().parent.parent
JSON_FILE = BASE_DIR / "data" / "collecte" / "publications.json"
CREDENTIALS = BASE_DIR / "secrets" / "finwatch-sheets.json"

SPREADSHEET_NAME = "FINWATCH_AI_BDD"

PUBLICATION_HEADERS = [
    "id", "titre", "source", "url", "date_publication",
    "date_collecte", "auteur", "resume_original", "type_document",
    "resume_ia", "categorie", "innovation", "application_financiere",
    "impact_potentiel", "probleme_financier", "interet_financier",
    "statut_validation", "valide_par", "date_validation",
    "statut_envoi", "date_envoi",
]

SOURCE_HEADERS = ["nom_source", "url_source", "type_source", "actif"]

JOURNAL_HEADERS = [
    "horodatage", "source", "trouvees", "nouvelles",
    "enregistrees", "doublons", "erreurs", "statut",
]

SOURCES = [
    {
        "nom_source": "BRI / BIS",
        "url_source": "https://www.bis.org/doclist/bis_fsi_publs.rss",
        "type_source": "RSS",
        "actif": "TRUE",
    },
    {
        "nom_source": "BCE - Supervision",
        "url_source": "https://www.bankingsupervision.europa.eu/rss/pub.html",
        "type_source": "RSS",
        "actif": "TRUE",
    },
    {
        "nom_source": "EBA - Actualites",
        "url_source": "https://www.eba.europa.eu/news-press/news/rss.xml",
        "type_source": "RSS",
        "actif": "TRUE",
    },
    {
        "nom_source": "Finextra AI",
        "url_source": "https://www.finextra.com/rss/channel.aspx?channel=ai",
        "type_source": "RSS",
        "actif": "TRUE",
    },
    {
        "nom_source": "arXiv",
        "url_source": "https://export.arxiv.org/api/query",
        "type_source": "API Atom",
        "actif": "TRUE",
    },
]


def verifier_entetes(feuille, attendus):
    actuels = feuille.row_values(1)
    if actuels != attendus:
        raise ValueError(
            f"En-têtes inattendus dans {feuille.title}: {actuels}"
        )


def texte_cellule(valeur):
    """Convertit une valeur JSON en représentation adaptée à Sheets."""
    if valeur is None:
        return ""
    if isinstance(valeur, list):
        return json.dumps(valeur, ensure_ascii=False)
    if isinstance(valeur, dict):
        return json.dumps(valeur, ensure_ascii=False)
    return str(valeur)


def enregistrer_sources(feuille):
    verifier_entetes(feuille, SOURCE_HEADERS)
    lignes = feuille.get_all_values()
    index = {
        ligne[0].strip(): numero
        for numero, ligne in enumerate(lignes[1:], start=2)
        if ligne and ligne[0].strip()
    }

    for source in SOURCES:
        nom = source["nom_source"]
        valeurs = [source[h] for h in SOURCE_HEADERS]

        if nom in index:
            # Met à jour uniquement la source portant le même nom.
            numero = index[nom]
            feuille.update(
                range_name=f"A{numero}:D{numero}",
                values=[valeurs],
                value_input_option="RAW",
            )
        else:
            feuille.append_row(valeurs, value_input_option="RAW")


def importer():
    if not JSON_FILE.is_file():
        raise FileNotFoundError(f"JSON introuvable : {JSON_FILE}")

    with JSON_FILE.open("r", encoding="utf-8") as fichier:
        publications = json.load(fichier)

    if not isinstance(publications, list):
        raise ValueError("Le fichier JSON doit contenir une liste.")

    json_secret = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if json_secret:
        client = gspread.service_account_from_dict(json.loads(json_secret))
    elif CREDENTIALS.is_file():
        client = gspread.service_account(filename=str(CREDENTIALS))
    else:
        raise FileNotFoundError("Identifiants Google Sheets absents.")
    sheet_id = os.getenv("GOOGLE_SHEET_ID") or os.getenv("GOOGLE_SHEETS_ID")
    classeur = client.open_by_key(sheet_id) if sheet_id else client.open(SPREADSHEET_NAME)
    feuille_pub = classeur.worksheet("Publications")
    feuille_sources = classeur.worksheet("Sources")
    feuille_journal = classeur.worksheet("Journal de collecte")

    verifier_entetes(feuille_pub, PUBLICATION_HEADERS)
    verifier_entetes(feuille_journal, JOURNAL_HEADERS)
    enregistrer_sources(feuille_sources)

    # Identifiants déjà présents dans Google Sheets.
    ids_feuille = {
        ligne[0].strip()
        for ligne in feuille_pub.get_all_values()[1:]
        if ligne and ligne[0].strip()
    }

    ids_lot = set()
    a_inserer = []
    erreurs_par_source = Counter()
    compteurs = {}

    def compteur(source):
        if source not in compteurs:
            compteurs[source] = {
                "trouvees": 0,
                "nouvelles": 0,
                "enregistrees": 0,
                "doublons": 0,
                "erreurs": 0,
            }
        return compteurs[source]

    for publication in publications:
        if not isinstance(publication, dict):
            stats = compteur("Entree invalide")
            stats["trouvees"] += 1
            stats["erreurs"] += 1
            continue

        source = str(publication.get("source") or "Source inconnue")
        stats = compteur(source)
        stats["trouvees"] += 1

        identifiant = publication.get("id")
        if not isinstance(identifiant, str) or not identifiant.strip():
            stats["erreurs"] += 1
            continue

        champs_obligatoires = ("titre", "url", "source")
        if any(
            not isinstance(publication.get(champ), str)
            or not publication.get(champ).strip()
            for champ in champs_obligatoires
        ):
            stats["erreurs"] += 1
            continue

        if identifiant in ids_feuille or identifiant in ids_lot:
            stats["doublons"] += 1
            continue

        auteur = publication.get("auteur")
        if auteur is not None and not isinstance(auteur, list):
            stats["erreurs"] += 1
            continue

        ids_lot.add(identifiant)
        stats["nouvelles"] += 1

        # Les 9 champs d'origine sont conservés.
        record = {h: "" for h in PUBLICATION_HEADERS}
        for champ in (
            "id", "titre", "source", "url", "date_publication",
            "date_collecte", "auteur", "resume_original", "type_document",
        ):
            record[champ] = texte_cellule(publication.get(champ))

        # Statuts initiaux : l'analyse et la validation restent distinctes.
        record["statut_validation"] = "A_VALIDER"
        record["statut_envoi"] = "NON_ENVOYE"

        a_inserer.append((source, [record[h] for h in PUBLICATION_HEADERS]))

    # Insertion par lots. Aucune ligne existante n'est réécrite.
    lignes = [ligne for _, ligne in a_inserer]
    if lignes:
        for debut in range(0, len(lignes), 100):
            lot = lignes[debut:debut + 100]
            feuille_pub.append_rows(lot, value_input_option="RAW")

        for source, _ in a_inserer:
            compteur(source)["enregistrees"] += 1

    # Une entrée de journal par source, y compris sans publication.
    sources_journal = list(dict.fromkeys(
        [s["nom_source"] for s in SOURCES] + list(compteurs.keys())
    ))
    horodatage = datetime.now(timezone.utc).isoformat()
    journal = []

    for source in sources_journal:
        stats = compteur(source)
        statut = "OK" if stats["erreurs"] == 0 else "AVEC_ERREURS"
        journal.append([
            horodatage,
            source,
            stats["trouvees"],
            stats["nouvelles"],
            stats["enregistrees"],
            stats["doublons"],
            stats["erreurs"],
            statut,
        ])

    if journal:
        feuille_journal.append_rows(journal, value_input_option="RAW")

    print("Import terminé.")
    print("Publications reçues :", len(publications))
    print("Nouvelles publications :", len(a_inserer))
    print("Publications insérées :", len(lignes))
    print(
        "Doublons ou identifiants déjà présents :",
        sum(v["doublons"] for v in compteurs.values()),
    )
    print(
        "Erreurs de validation :",
        sum(v["erreurs"] for v in compteurs.values()),
    )
    print("Journal ajouté :", len(journal), "lignes")


if __name__ == "__main__":
    importer()
