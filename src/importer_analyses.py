"""Transfert prudent des analyses du module 2 vers le module Google Sheets.

Ne transmet que les analyses effectuees et pertinentes.
Ne valide aucune publication, ne declenche aucun email.
Usage: python src/importer_analyses.py
"""
import json
from pathlib import Path

import stockage

RACINE = Path(__file__).resolve().parents[1]
FICHIER = RACINE / "data" / "analyse" / "publications_analysees.json"
CATEGORIES = {
    "MARCHES_FINANCIERS", "REGLEMENTATION_CONFORMITE",
    "CREDIT_MICROFINANCE", "BANQUE",
}


def convertir_analyse(publication):
    """Adapte une analyse reussie au contrat des 21 colonnes du stockage."""
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
        ("probleme_financier", "probleme_financier"),
        ("interet_financier", "interet_financier"),
    ]:
        texte = publication.get(depart)
        if isinstance(texte, str) and texte.strip():
            resultat[arrivee] = texte.strip()
    return resultat


def importer_analyses(chemin=FICHIER):
    """Lecture unique et mises a jour groupees, sans ecraser les validations.

    Les analyses deja presentes sont ignorees : relancer apres un echec de quota
    reste sur et ne modifie pas les syntheses deja relues par l'equipe.
    """
    publications = json.loads(Path(chemin).read_text(encoding="utf-8"))
    if not isinstance(publications, list):
        raise ValueError("Les analyses doivent etre une liste JSON.")

    candidats = [c for p in publications if (c := convertir_analyse(p))]
    feuille = stockage._feuille()
    lignes = feuille.get_all_values()  # Une lecture pour l'ensemble du lot.
    if not lignes or lignes[0][:len(stockage.HEADERS)] != stockage.HEADERS:
        raise ValueError("En-tetes inattendus dans Publications.")

    indexes = {}
    for numero, valeurs in enumerate(lignes[1:], start=2):
        if valeurs and valeurs[0]:
            indexes[str(valeurs[0]).strip()] = (numero, valeurs)

    changements, ignores, proteges, deja_presents, absents = [], 0, 0, 0, []
    for donnees in candidats:
        trouve = indexes.get(donnees["id"])
        if not trouve:
            absents.append(donnees["id"])
            continue
        numero, valeurs = trouve
        valeurs = valeurs + [""] * max(0, len(stockage.HEADERS) - len(valeurs))
        ligne = dict(zip(stockage.HEADERS, valeurs[:len(stockage.HEADERS)]))
        if (ligne["statut_validation"] in ("VALIDE", "REJETE")
                or ligne["statut_envoi"] == "ENVOYE"):
            proteges += 1
            continue
        if str(ligne.get("resume_ia") or "").strip():
            deja_presents += 1
            continue
        for cle, valeur in donnees.items():
            if cle in stockage.CHAMPS_ANALYSE_SHEETS and valeur not in (None, ""):
                ligne[cle] = valeur
        changements.append({
            "range": f"A{numero}:U{numero}",
            "values": [[ligne[h] for h in stockage.HEADERS]]
        })

    # Une requete batch pour le lot courant au lieu d'une lecture et ecriture
    # Google Sheets pour chaque publication.
    if changements:
        feuille.batch_update(changements, value_input_option="RAW")

    ignores = len(publications) - len(candidats)
    print(f"Analyses stockees : {len(changements)}; non eligibles : {ignores}; "
          f"deja presentes : {deja_presents}; protegees : {proteges}; "
          f"absentes : {len(absents)}")
    if absents:
        raise RuntimeError(f"{len(absents)} publications absentes de Google Sheets.")
    return len(changements)


if __name__ == "__main__":
    importer_analyses()
