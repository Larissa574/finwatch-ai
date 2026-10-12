
"""Google Sheets storage for FINWATCH AI."""
from pathlib import Path
from typing import Any

import gspread

BASE_DIR = Path(__file__).resolve().parent.parent
CREDENTIALS = BASE_DIR / "secrets" / "finwatch-sheets.json"
SPREADSHEET_NAME = "FINWATCH_AI_BDD"
WORKSHEET_NAME = "Publications"

HEADERS = [
    "id", "titre", "source", "url", "date_publication",
    "date_collecte", "auteur", "resume_original", "type_document",
    "resume_ia", "categorie", "innovation", "application_financiere",
    "impact_potentiel", "statut_validation", "valide_par",
    "date_validation", "statut_envoi", "date_envoi",
]

PROTECTED_FIELDS = {
    "statut_validation", "valide_par", "date_validation",
    "statut_envoi", "date_envoi",
}


def _feuille():
    if not CREDENTIALS.is_file():
        raise FileNotFoundError(
            f"Fichier d'identifiants introuvable : {CREDENTIALS}"
        )

    client = gspread.service_account(filename=str(CREDENTIALS))
    workbook = client.open(SPREADSHEET_NAME)
    worksheet = workbook.worksheet(WORKSHEET_NAME)

    if worksheet.row_values(1)[:len(HEADERS)] != HEADERS:
        raise ValueError(
            "Les en-têtes Google Sheets ne correspondent pas aux 19 colonnes attendues."
        )

    return worksheet


def _lire_publications(feuille) -> list[dict[str, Any]]:
    rows = feuille.get_all_values()
    if not rows:
        return []

    headers = rows[0]
    publications = []

    for values in rows[1:]:
        values = values + [""] * max(0, len(headers) - len(values))
        publication = dict(zip(headers, values))

        if publication.get("id"):
            publications.append(publication)

    return publications


def enregistrer(publication: dict[str, Any]) -> None:
    identifiant = str(publication.get("id", "")).strip()
    if not identifiant:
        raise ValueError("Impossible d'enregistrer une publication sans id.")

    feuille = _feuille()
    rows = feuille.get_all_values()

    ligne_existante = None
    for numero, values in enumerate(rows[1:], start=2):
        if values and str(values[0]).strip() == identifiant:
            ligne_existante = numero
            break

    if ligne_existante is None:
        record = {header: "" for header in HEADERS}

        for key, value in publication.items():
            if key in HEADERS and key not in PROTECTED_FIELDS:
                if value not in (None, ""):
                    record[key] = value

        record["id"] = identifiant
        record["statut_validation"] = "A_VALIDER"
        record["statut_envoi"] = "NON_ENVOYE"

        feuille.append_row(
            [record[h] for h in HEADERS],
            value_input_option="RAW",
        )
        return

    old_values = rows[ligne_existante - 1]
    old_values = old_values + [""] * max(0, len(HEADERS) - len(old_values))
    record = dict(zip(HEADERS, old_values[:len(HEADERS)]))

    for key, value in publication.items():
        if key in HEADERS and key not in PROTECTED_FIELDS:
            if value not in (None, ""):
                record[key] = value

    record["id"] = identifiant

    feuille.update(
        range_name=f"A{ligne_existante}:S{ligne_existante}",
        values=[[record[h] for h in HEADERS]],
        value_input_option="RAW",
    )


def publications_a_diffuser() -> list[dict[str, Any]]:
    feuille = _feuille()
    publications = _lire_publications(feuille)

    return [
        publication
        for publication in publications
        if publication.get("statut_validation") == "VALIDE"
        and publication.get("statut_envoi") in ("NON_ENVOYE", "", None)
    ]
