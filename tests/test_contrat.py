"""Tests initiaux du format partagé ; ils ne testent pas les connecteurs réels."""

import json
import unittest
from pathlib import Path


RACINE = Path(__file__).resolve().parents[1]
CHAMPS_BRUTS = {
    "id", "titre", "source", "url", "date_publication",
    "date_collecte", "auteur", "resume_original", "type_document",
}
CATEGORIES = {
    "MARCHES_FINANCIERS", "REGLEMENTATION_CONFORMITE",
    "CREDIT_MICROFINANCE", "BANQUE",
}


class TestContrat(unittest.TestCase):
    def test_exemple_contient_les_champs_accordes(self):
        publication = json.loads(
            (RACINE / "examples" / "publication_brute.json").read_text(encoding="utf-8")
        )
        self.assertTrue(CHAMPS_BRUTS.issubset(publication.keys()))
        self.assertTrue(publication["id"])
        self.assertTrue(publication["url"].startswith(("http://", "https://")))

    def test_configuration_des_quatre_axes(self):
        config = json.loads(
            (RACINE / "config" / "mots_cles.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(config["axes"]), CATEGORIES)

    def test_catalogue_cinq_sources_actives(self):
        config = json.loads(
            (RACINE / "config" / "sources.json").read_text(encoding="utf-8")
        )
        self.assertEqual(len(config["sources"]), 5)
        self.assertTrue(all(s["statut"] == "ACTIF" for s in config["sources"]))


if __name__ == "__main__":
    unittest.main()
