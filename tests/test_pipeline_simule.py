"""Test d'un parcours complet SIMULE sans reseau ni envoi reel."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import analyse
import stockage
import diffusion
from importer_analyses import convertir_analyse


class FeuilleSimulee:
    def __init__(self):
        self.lignes = [stockage.HEADERS.copy()]

    def get_all_values(self):
        return [list(row) for row in self.lignes]

    def append_row(self, values, value_input_option=None):
        self.lignes.append(list(values))

    def update(self, range_name, values, value_input_option=None):
        number = int(range_name.split(":")[0][1:])
        self.lignes[number - 1] = list(values[0])


class TestPipelineSimule(unittest.TestCase):
    def test_collecte_vers_diffusion_sans_reseau(self):
        publication = {
            "id": "simulation-1",
            "titre": "Machine learning for banking fraud detection",
            "source": "arXiv",
            "url": "https://example.org/simulation-1",
            "date_publication": "2026-10-10",
            "date_collecte": "2026-10-13T00:00:00+00:00",
            "auteur": [],
            "resume_original": (
                "This research uses machine learning and artificial intelligence "
                "to detect fraud in banking transactions and card payments. "
                "The study describes a financial fraud detection approach."
            ),
            "type_document": "publication",
        }
        feuille = FeuilleSimulee()
        with patch.object(stockage, "_feuille", return_value=feuille):
            stockage.enregistrer(publication)
            resultats, journal = analyse.traiter_publications(
                [publication], classificateur=lambda texte: 0.95,
                appeler=analyse.appeler_ia_simulee,
                mots_cles=analyse.mots_cles_provisoires()
            )
            self.assertFalse(journal["sorties_non_conformes"])
            self.assertEqual(resultats[0]["statut_pertinence"], "pertinent")
            self.assertEqual(resultats[0]["statut_analyse"], "effectuee")
            changements = convertir_analyse(resultats[0])
            self.assertIsNotNone(changements)
            stockage.mettre_a_jour_analyse(changements)
            row = dict(zip(stockage.HEADERS, feuille.lignes[1]))
            self.assertEqual(row["statut_validation"], "A_VALIDER")
            self.assertEqual(diffusion.selectionner_a_envoyer([row]), [])
            row.update({"statut_validation": "VALIDE",
                        "valide_par": "Testeur",
                        "date_validation": "2026-10-13T00:00:00Z"})
            bulletin = diffusion.generer_bulletin([row])
            self.assertIn("FINWATCH AI", bulletin)
            self.assertIn("Machine learning", bulletin)
            envois = []
            with patch.object(diffusion, "envoyer_bulletin",
                              side_effect=lambda html: envois.append(html)):
                statut = diffusion.diffuser(
                    [row],
                    lambda ids, date: row.update({
                        "statut_envoi": "ENVOYE", "date_envoi": date
                    }),
                    lambda ids: self.fail("Erreur SMTP inattendue"),
                )
            self.assertEqual(statut, 0)
            self.assertEqual(len(envois), 1)
            self.assertEqual(diffusion.selectionner_a_envoyer([row]), [])


if __name__ == "__main__":
    unittest.main()
