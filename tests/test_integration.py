"""Tests de correspondance des champs IA et du stockage : aucun acces reseau."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))
import importer_analyses as ia
import stockage


class FeuilleSimulee:
    def __init__(self):
        self.lignes = [stockage.HEADERS.copy()]

    def get_all_values(self):
        return [list(l) for l in self.lignes]

    def append_row(self, valeurs, value_input_option=None):
        self.lignes.append(list(valeurs))

    def update(self, range_name, values, value_input_option=None):
        numero = int(range_name.split(":")[0][1:])
        self.lignes[numero - 1] = list(values[0])


class TestIntegrationAnalyseStockage(unittest.TestCase):
    def setUp(self):
        self.feuille = FeuilleSimulee()
        self.patcher = patch.object(stockage, "_feuille", return_value=self.feuille)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        stockage.enregistrer({"id": "pub1", "titre": "AI banking",
                              "url": "https://example.org", "source": "arXiv"})

    def resultat(self):
        return dict(zip(stockage.HEADERS, self.feuille.lignes[1]))

    def test_transfert_analyse_valide(self):
        donnees = ia.convertir_analyse({
            "id": "pub1", "statut_pertinence": "pertinent",
            "statut_analyse": "effectuee", "categorie": "BANQUE",
            "resume_fr": "Analyse en francais.", "innovation": "Systeme innovant.",
            "probleme_financier": "Fraude", "interet_financier": "Meilleur controle."
        })
        stockage.mettre_a_jour_analyse(donnees)
        resultat = self.resultat()
        self.assertEqual(resultat["resume_ia"], "Analyse en francais.")
        self.assertEqual(resultat["application_financiere"], "Fraude")
        self.assertEqual(resultat["probleme_financier"], "Fraude")
        self.assertEqual(resultat["interet_financier"], "Meilleur controle.")
        self.assertEqual(len(stockage.HEADERS), 21)
        self.assertEqual(resultat["impact_potentiel"], "Meilleur controle.")
        self.assertEqual(resultat["statut_validation"], "A_VALIDER")
        self.assertEqual(resultat["statut_envoi"], "NON_ENVOYE")

    def test_analyses_non_terminees_ignorees(self):
        for statut in ("incertaine", "en_echec"):
            self.assertIsNone(ia.convertir_analyse({
                "id": "pub1", "statut_pertinence": "pertinent",
                "statut_analyse": statut, "categorie": "BANQUE",
                "resume_fr": "Pas encore fiable."
            }))
        self.assertIsNone(self.resultat()["resume_ia"] or None)

    def test_absence_publication_ne_cree_pas_de_ligne(self):
        with self.assertRaises(KeyError):
            stockage.mettre_a_jour_analyse({"id": "inconnu", "resume_ia": "Texte"})
        self.assertEqual(len(self.feuille.lignes), 2)

    def test_validation_preservee(self):
        ligne = self.resultat()
        ligne.update({"statut_validation": "VALIDE", "valide_par": "Charbel"})
        self.feuille.lignes[1] = [ligne[h] for h in stockage.HEADERS]
        with self.assertRaises(ValueError):
            stockage.mettre_a_jour_analyse({"id": "pub1", "resume_ia": "Nouveau texte"})
        self.assertEqual(self.resultat()["statut_validation"], "VALIDE")

    def test_deuxieme_enregistrement_sans_doublon(self):
        stockage.enregistrer({"id": "pub1", "titre": "AI banking"})
        self.assertEqual(len(self.feuille.lignes), 2)


if __name__ == "__main__":
    unittest.main()
