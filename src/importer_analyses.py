"""Transfert prudent des analyses du module 2 vers le module Google Sheets.

Ne transmet que les analyses effectuees et pertinentes.
Ne valide aucune publication, ne declenche aucun email.
Usage: python src/importer_analyses.py
"""
import json
from pathlib import Path

from stockage import mettre_a_jour_analyse

RACINE = Path(__file__).resolve().parents[1]
FICHIER = RACINE / "data" / "analyse" / "publications_analysees.json"
CATEGORIES = {
    "MARCHES_FINANCIERS", "REGLEMENTATION_CONFORMITE",
    "CREDIT_MICROFINANCE", "BANQUE",
}


def convertir_analyse(publication):
    """Adapte une analyse reussie au contrat des 19 colonnes du stockage."""
    if not isinstance(publication, dict):
        return None
    identifiant = publication.get("id")
    if not isinstance(identifiant, str) or not identifiant.strip():
        return None
    if publication.get("statut_pertinence") != "pertinent":
        return None
    if publication.get("statut_analyse") != "effectuee":
        return None
    categorie = publication.get("categorie")
    resume = publication.get("resume_fr")
    if categorie not in CATEGORIES or not isinstance(resume, str) or not resume.strip():
        return None

    resultat = {
        "id": identifiant,
        "resume_ia": resume.strip(),
        "categorie": categorie,
    }
    for depart, arrivee in [
        ("innovation", "innovation"),
        ("probleme_financier", "application_financiere"),
        ("interet_financier", "impact_potentiel"),
    ]:
        texte = publication.get(depart)
        if isinstance(texte, str) and texte.strip():
            resultat[arrivee] = texte.strip()
    return resultat


def importer_analyses(chemin=FICHIER):
    publications = json.loads(Path(chemin).read_text(encoding="utf-8"))
    if not isinstance(publications, list):
        raise ValueError("Les analyses doivent etre une liste JSON.")
    importees, ignorees, erreurs = 0, 0, []
    for publication in publications:
        donnees = convertir_analyse(publication)
        if donnees is None:
            ignorees += 1
            continue
        try:
            mettre_a_jour_analyse(donnees)
            importees += 1
        except Exception as erreur:
            erreurs.append({"id": donnees["id"], "erreur": str(erreur)})
    print(f"Analyses stockees : {importees}; non eligibles : {ignorees}; erreurs : {len(erreurs)}")
    for erreur in erreurs:
        print("Erreur stockage pour", erreur["id"], ":", erreur["erreur"])
    if erreurs:
        raise RuntimeError(f"{len(erreurs)} analyses n'ont pas ete stockees.")
    return importees


if __name__ == "__main__":
    importer_analyses()
