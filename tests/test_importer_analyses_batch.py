"""Tests de l'import groupé : quota Sheets et respect des validations."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import importer_analyses as importer
import stockage


def test_import_groupe_protege_validations_et_evite_lectures_repetitives(tmp_path, monkeypatch):
    def article(id):
        return {"id": id, "statut_pertinence": "pertinent", "statut_analyse": "effectuee",
                "categorie": "BANQUE", "resume_fr": "Résumé de test"}
    entree = tmp_path / "analyse.json"
    entree.write_text(json.dumps([article("a"), article("b"), article("c")]), encoding="utf-8")
    headers = stockage.HEADERS
    def ligne(id, statut="A_VALIDER", resume=""):
        record = dict.fromkeys(headers, "")
        record.update(id=id, statut_validation=statut, statut_envoi="NON_ENVOYE", resume_ia=resume)
        return [record[h] for h in headers]
    class Feuille:
        reads = 0
        batches = []
        def get_all_values(self):
            self.reads += 1
            return [headers, ligne("a"), ligne("b", "VALIDE"), ligne("c", resume="Analyse existante")]
        def batch_update(self, changements, value_input_option):
            self.batches.append(changements)
    feuille = Feuille()
    monkeypatch.setattr(importer.stockage, "_feuille", lambda: feuille)
    assert importer.importer_analyses(entree) == 1
    assert feuille.reads == 1
    assert len(feuille.batches) == 1
    assert len(feuille.batches[0]) == 1
    assert feuille.batches[0][0]["range"] == "A2:U2"
