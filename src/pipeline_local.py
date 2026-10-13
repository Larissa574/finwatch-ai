"""Demonstration locale FINWATCH AI : aucune API, aucun Google Sheets, aucun SMTP.

Usage : python src/pipeline_local.py
Produit des fichiers dans data/demo_locale/ ; ne modifie aucune donnee officielle.
"""
import json
from pathlib import Path
from unittest.mock import patch

import analyse
import diffusion
import stockage
from importer_analyses import convertir_analyse

ROOT = Path(__file__).resolve().parents[1]
SORTIE = ROOT / "data" / "demo_locale"


class FeuilleLocale:
    """Substitut minimal a Google Sheets, compatible avec stockage.py."""

    def __init__(self):
        self.lignes = [stockage.HEADERS.copy()]

    def get_all_values(self):
        return [ligne.copy() for ligne in self.lignes]

    def append_row(self, values, value_input_option=None):
        self.lignes.append(list(values))

    def update(self, range_name, values, value_input_option=None):
        numero = int(range_name.split(":")[0][1:])
        self.lignes[numero - 1] = list(values[0])


def exemple():
    """Publications fictives pour ne pas confondre demonstration et actualites."""
    return [
        {
            "id": "demo-finwatch-001",
            "titre": "DEMO : Machine learning for bank fraud detection",
            "source": "DEMONSTRATION",
            "url": "https://example.org/finwatch-demo-001",
            "date_publication": "2026-10-13",
            "date_collecte": "2026-10-13T00:00:00Z",
            "auteur": ["Equipe FINWATCH AI"],
            "resume_original": (
                "A bank uses machine learning and artificial intelligence to detect "
                "fraud in card payments and financial transactions. The demonstration "
                "describes how AI supports banking fraud detection."
            ),
            "type_document": "demonstration",
        },
        {
            "id": "demo-finwatch-002",
            "titre": "DEMO : International gardening trends",
            "source": "DEMONSTRATION",
            "url": "https://example.org/finwatch-demo-002",
            "date_publication": "2026-10-13",
            "date_collecte": "2026-10-13T00:00:00Z",
            "auteur": [],
            "resume_original": (
                "This article reviews plant care, seasonal watering and garden design "
                "in public parks. It provides advice for maintaining healthy flowers."
            ),
            "type_document": "demonstration",
        },
    ]


def lancer(sortie=SORTIE):
    sortie = Path(sortie)
    sortie.mkdir(parents=True, exist_ok=True)
    publications = exemple()
    feuille = FeuilleLocale()
    with patch.object(stockage, "_feuille", return_value=feuille):
        for publication in publications:
            stockage.enregistrer(publication)
        # On teste le passage des donnees, jamais la qualite d'un vrai modele.
        resultats, journal = analyse.traiter_publications(
            publications,
            classificateur=lambda texte: 0.95 if "fraud" in texte.lower() else 0.05,
            appeler=analyse.appeler_ia_simulee,
            mots_cles=analyse.mots_cles_provisoires(),
        )
        importees = 0
        for resultat in resultats:
            conversion = convertir_analyse(resultat)
            if conversion:
                stockage.mettre_a_jour_analyse(conversion)
                importees += 1

    lignes = [dict(zip(stockage.HEADERS, ligne)) for ligne in feuille.lignes[1:]]
    # L'apercu suivant est explicitement une validation fictive EN MEMOIRE.
    candidats = [dict(ligne) for ligne in lignes if ligne.get("resume_ia")]
    for publication in candidats:
        publication.update({
            "statut_validation": "VALIDE",
            "valide_par": "DEMONSTRATION UNIQUEMENT",
            "date_validation": "2026-10-13T00:00:00Z",
        })
    if not candidats:
        raise RuntimeError("Aucune publication de demonstration exploitable.")

    apercu = diffusion.generer_bulletin(candidats)
    (sortie / "publications_collectees.json").write_text(
        json.dumps(publications, indent=2, ensure_ascii=False), encoding="utf-8")
    (sortie / "publications_analysees.json").write_text(
        json.dumps(resultats, indent=2, ensure_ascii=False), encoding="utf-8")
    (sortie / "stockage_local.json").write_text(
        json.dumps(lignes, indent=2, ensure_ascii=False), encoding="utf-8")
    (sortie / "journal.json").write_text(
        json.dumps(journal, indent=2, ensure_ascii=False), encoding="utf-8")
    (sortie / "bulletin_apercu.html").write_text(apercu, encoding="utf-8")
    return {"collectees": len(publications), "importees": importees,
            "a_valider": sum(l["statut_validation"] == "A_VALIDER" for l in lignes),
            "apercu_articles": len(candidats), "sortie": str(sortie.resolve())}


if __name__ == "__main__":
    print("FINWATCH AI - demonstration 100 % locale et fictive")
    for cle, valeur in lancer().items():
        print(f"{cle}: {valeur}")
