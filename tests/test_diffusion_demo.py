"""Tests locaux du mode demonstration : pas de SMTP ni Google Sheets reels."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import diffusion_demo as demo


class Abonnes:
    def __init__(self, data):
        self.data = data
    def get_all_records(self):
        return self.data


def pub(id):
    return {"id": id, "titre": id, "url": "https://example.org/" + id,
            "source": "BIS", "resume_ia": "Resume relu", "statut_validation": "VALIDE",
            "valide_par": "Equipe", "date_validation": "2026-10-14",
            "statut_envoi": "NON_ENVOYE"}


def abonnes():
    return Abonnes([
        {"email": x, "statut": statut, "date_inscription": "2026-10-14",
         "source_consentement": "web"}
        for x, statut in [("a@example.org", "DESINSCRIT"), ("b@example.org", "ACTIF"),
                          ("c@example.org", "ACTIF"), ("externe@example.org", "ACTIF")]
    ])


def test_edition_respecte_articles_autorises_et_desinscriptions():
    campagne, ids, selection, dest, deja = demo.planifier(
        "edition02", "p4,p5", "a@example.org,b@example.org,c@example.org",
        [pub("p1"), pub("p4"), pub("p5")], abonnes(), [])
    assert campagne == "demo-edition02"
    assert ids == "p4,p5"
    assert [p["id"] for p in selection] == ["p4", "p5"]
    assert dest == ["b@example.org", "c@example.org"]
    assert deja == 0


def test_relance_evite_envois_deja_journalises():
    _, _, _, dest, deja = demo.planifier(
        "edition02", "p4,p5", "b@example.org,c@example.org",
        [pub("p4"), pub("p5")], abonnes(),
        [{"campagne": "demo-edition02", "email": "b@example.org",
          "statut": "ENVOYE", "articles": "p4,p5"}])
    assert dest == ["c@example.org"]
    assert deja == 1


def test_edition_immuable_si_deja_journalisee():
    with pytest.raises(ValueError, match="autre ensemble"):
        demo.planifier("edition02", "p4", "b@example.org", [pub("p4")], abonnes(),
                       [{"campagne": "demo-edition02", "email": "b@example.org",
                         "statut": "ENVOYE", "articles": "p4,p5"}])


def test_impossible_d_envoyer_article_non_valide():
    p = pub("p4")
    p["statut_validation"] = "A_VALIDER"
    with pytest.raises(ValueError, match="VALIDE"):
        demo.planifier("edition02", "p4", "b@example.org", [p], abonnes(), [])
