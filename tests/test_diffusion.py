import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pytest
import diffusion


def pub(**kw):
    base = {
        "id": "x1", "titre": "Titre", "url": "https://example.org/a", "source": "BIS",
        "date_publication": "2026-10-09", "categorie": "BANQUE",
        "resume_ia": "Résumé", "innovation": "Inno", "application_financiere": "App",
        "impact_potentiel": "Impact", "statut_validation": "VALIDE",
        "valide_par": "Sosthene", "date_validation": "2026-10-10T10:00:00Z",
        "statut_envoi": "NON_ENVOYE", "date_envoi": None,
    }
    base.update(kw)
    return base


def test_bulletin_exclut_non_valides():
    h = diffusion.generer_bulletin([pub(id="a", titre="OK"), pub(id="b", titre="SECRET", statut_validation="A_VERIFIER")])
    assert "OK" in h and "SECRET" not in h


def test_bulletin_echappe_html():
    h = diffusion.generer_bulletin([pub(titre="<script>x</script>")])
    assert "<script>" not in h


def test_bulletin_sans_valide_leve():
    with pytest.raises(ValueError):
        diffusion.generer_bulletin([pub(statut_validation="A_VERIFIER")])


def test_validation_sans_validateur_ignoree():  # T04
    assert diffusion.selectionner_a_envoyer([pub(valide_par=None)]) == []


def test_deja_envoye_non_reselectionne():
    assert diffusion.selectionner_a_envoyer([pub(statut_envoi="ENVOYE")]) == []


def test_erreur_envoi_seulement_en_relance():
    p = pub(statut_envoi="ERREUR_ENVOI")
    assert diffusion.selectionner_a_envoyer([p]) == []
    assert diffusion.selectionner_a_envoyer([p], retry_erreurs=True) == [p]


def test_diffuser_succes(monkeypatch):  # T05
    monkeypatch.setattr(diffusion, "envoyer_bulletin", lambda h: None)
    ok, ko = [], []
    code = diffusion.diffuser([pub()], lambda ids, d: ok.append((ids, d)), ko.append)
    assert code == 0 and ok[0][0] == ["x1"] and ok[0][1].endswith("Z") and ko == []


def test_diffuser_echec_incident(monkeypatch):  # T06
    def boom(h): raise ConnectionError("smtp down")
    monkeypatch.setattr(diffusion, "envoyer_bulletin", boom)
    ok, ko = [], []
    code = diffusion.diffuser([pub()], lambda ids, d: ok.append(ids), ko.append)
    assert code == 1 and ok == [] and ko == [["x1"]]


def test_rien_a_envoyer(monkeypatch):
    monkeypatch.setattr(diffusion, "envoyer_bulletin", lambda h: pytest.fail("ne doit pas envoyer"))
    assert diffusion.diffuser([pub(statut_envoi="ENVOYE")], None, None) == 0


def test_template_v2_synthese_unifiee_source_et_date():
    h = diffusion.generer_bulletin([pub(
        titre="Nouvelles règles pour les banques",
        resume_ia="La banque centrale introduit une revue indépendante des projets d’IA.",
        date_publication="2026-10-08T12:49:00+00:00",
        innovation="AFFIRMATION NON VERIFIEE",
        application_financiere="APPLICATION A PART",
        impact_potentiel="IMPACT A PART",
    )])
    assert "Bulletin de veille stratégique" in h
    assert "08/10/2026" in h
    assert "Consulter la source originale" in h
    assert 'href="https://example.org/a"' in h
    assert "La banque centrale introduit" in h
    assert "AFFIRMATION NON VERIFIEE" not in h
    assert "APPLICATION A PART" not in h
    assert "IMPACT A PART" not in h
    assert "Résumé vérifié :" not in h


def test_template_v2_texte_echappe():
    h = diffusion.generer_bulletin([pub(resume_ia="<script>attaque</script>")])
    assert "<script>" not in h
    assert "&lt;script&gt;" in h


def test_template_v2_masquer_compteur_et_mentions_universitaires():
    html = diffusion.generer_bulletin([pub()])
    assert "publication(s) validée(s)" not in html
    assert "Projet universitaire de veille" not in html
    assert "Consultez les sources originales" in html
