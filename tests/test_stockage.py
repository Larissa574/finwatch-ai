
"""Tests isolés du stockage FINWATCH AI.
Aucune connexion à Google Sheets n'est effectuée.
"""

import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src import stockage

class FeuilleSimulee:
    def __init__(self):
        self.lignes = [stockage.HEADERS.copy()]

    def get_all_values(self):
        return [ligne.copy() for ligne in self.lignes]

    def append_row(self, values, value_input_option=None):
        self.lignes.append(list(values))

    def update(self, range_name, values, value_input_option=None):
        numero = int(range_name.split(":")[0][1:])
        self.lignes[numero - 1] = list(values[0])


def main():
    feuille = FeuilleSimulee()

    # Remplacer la connexion réelle par la feuille simulée.
    stockage._feuille = lambda: feuille

    publication = {
        "id": "TEST-FINWATCH-001",
        "titre": "Publication de test",
        "source": "Source de test",
        "resume_original": "Résumé original conservé.",
    }

    stockage.enregistrer(publication)

    ligne = dict(zip(stockage.HEADERS, feuille.lignes[1]))

    assert ligne["statut_validation"] == "A_VALIDER"
    assert ligne["statut_envoi"] == "NON_ENVOYE"
    assert ligne["resume_original"] == "Résumé original conservé."

    # Simulation de la validation par un responsable.
    ligne["statut_validation"] = "VALIDE"
    ligne["valide_par"] = "Testeur"
    ligne["statut_envoi"] = "NON_ENVOYE"
    feuille.lignes[1] = [ligne[h] for h in stockage.HEADERS]

    # Simulation de la réception de l'analyse IA.
    analyse = {
        "id": "TEST-FINWATCH-001",
        "resume_ia": "Résumé IA de test.",
        "categorie": "Intelligence artificielle",
    }

    stockage.enregistrer(analyse)

    resultat = dict(zip(stockage.HEADERS, feuille.lignes[1]))

    assert resultat["resume_ia"] == "Résumé IA de test."
    assert resultat["categorie"] == "Intelligence artificielle"
    assert resultat["resume_original"] == "Résumé original conservé."
    assert resultat["statut_validation"] == "VALIDE"
    assert resultat["valide_par"] == "Testeur"
    assert resultat["statut_envoi"] == "NON_ENVOYE"

    print("Tous les tests de stockage sont réussis.")


if __name__ == "__main__":
    main()
