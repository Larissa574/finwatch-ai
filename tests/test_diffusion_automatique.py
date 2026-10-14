"""Tests de non-regression de la diffusion abonnes (sans reseau ni SMTP)."""
import os
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import diffusion_automatique as da


class FakeWorksheet:
    def __init__(self, rows):
        self.rows = rows
    def get_all_records(self):
        return list(self.rows)


def test_desabonne_exclu_et_doublons_ignores():
    feuille = FakeWorksheet([
        {"email": "a@example.org", "statut": "ACTIF", "date_inscription": "2026-10-14", "source_consentement": "web"},
        {"email": "a@example.org", "statut": "DESINSCRIT", "date_inscription": "2026-10-14", "source_consentement": "web"},
        {"email": "b@example.org", "statut": "ACTIF", "date_inscription": "2026-10-14", "source_consentement": "web"},
        {"email": "b@example.org", "statut": "ACTIF", "date_inscription": "2026-10-14", "source_consentement": "web"},
        {"email": "c@example.org", "statut": "ACTIF", "date_inscription": "", "source_consentement": "web"},
    ])
    assert da.emails_actifs(feuille) == ["b@example.org"]


def test_lien_desinscription_personnalise_et_signe():
    with patch.dict(os.environ, {
        "FINWATCH_WEBAPP_URL": "https://script.google.com/macros/s/test/exec",
        "FINWATCH_HMAC_SECRET": "un-secret-de-test-sans-usage-reel"
    }):
        lien = da.lien_desinscription("b@example.org")
        assert "action=unsubscribe" in lien
        assert "b%40example.org" in lien
        assert "token=" in lien
        html = da.ajouter_desinscription("<html><body>Bulletin</body></html>", "b@example.org")
        assert "Se désabonner" in html
        assert "Bulletin" in html


def test_aucun_envoi_si_campagne_deja_servie(monkeypatch):
    class Workbook:
        def worksheet(self, name):
            return object()
    class Sheet:
        spreadsheet = Workbook()
    monkeypatch.setattr(da.stockage, "_feuille", lambda: Sheet())
    monkeypatch.setattr(da.stockage, "_lire_publications", lambda ws: [{"id":"i1","titre":"Publication","url":"https://example.org","source":"BIS","resume_ia":"Résumé","statut_validation":"VALIDE","valide_par":"Equipe","date_validation":"2026-10-14","statut_envoi":"NON_ENVOYE"}])
    def fake_onglet(book, name, headers):
        if name == "Abonnes":
            return FakeWorksheet([{"email":"b@example.org","statut":"ACTIF","date_inscription":"2026-10-14","source_consentement":"web"}])
        import hashlib
        campaign = hashlib.sha256(b"i1").hexdigest()[:20]
        return FakeWorksheet([{"campagne":campaign,"email":"b@example.org","statut":"ENVOYE"}])
    monkeypatch.setattr(da, "onglet", fake_onglet)
    monkeypatch.setattr(da.diffusion, "envoyer_bulletin", lambda html: (_ for _ in ()).throw(AssertionError("SMTP ne doit pas etre appele")))
    assert da.run(send=True) == 0


def test_mode_prive_exclut_les_autres_destinataires(monkeypatch):
    class Workbook:
        def worksheet(self, name):
            return object()
    class Sheet:
        spreadsheet = Workbook()
    class Journal(FakeWorksheet):
        def __init__(self):
            super().__init__([])
            self.records = []
        def append_row(self, values, value_input_option=None):
            self.records.append(values)
    journal = Journal()
    abonnes = FakeWorksheet([
        {"email": adresse, "statut": "ACTIF", "date_inscription": "2026-10-14", "source_consentement": "web"}
        for adresse in ("test@example.org", "autre@example.org")
    ])
    monkeypatch.setattr(da.stockage, "_feuille", lambda: Sheet())
    monkeypatch.setattr(da.stockage, "_lire_publications", lambda ws: [{"id": "i1"}])
    monkeypatch.setattr(da.diffusion, "selectionner_a_envoyer", lambda pubs: pubs)
    monkeypatch.setattr(da.diffusion, "generer_bulletin", lambda pubs: "<body>Bulletin</body>")
    monkeypatch.setattr(da, "ajouter_desinscription", lambda bulletin, adresse: bulletin)
    monkeypatch.setattr(da, "onglet", lambda book, name, headers: abonnes if name == "Abonnes" else journal)
    envoyes = []
    monkeypatch.setattr(da.diffusion, "envoyer_bulletin", lambda bulletin: envoyes.append(os.environ["MAIL_TO"]))
    monkeypatch.setenv("FINWATCH_TEST_EMAIL", "test@example.org")
    monkeypatch.setenv("FINWATCH_AUTORISER_ENVOI", "NON")
    assert da.run(send=True, campagne_test="prive-01", test_email="test@example.org") == 0
    assert envoyes == ["test@example.org"]
    assert len(journal.records) == 1


def test_mode_prive_refuse_adresse_non_autorisee(monkeypatch):
    monkeypatch.setenv("FINWATCH_TEST_EMAIL", "test@example.org")
    with patch.object(da.stockage, "_feuille") as feuille:
        classeur = feuille.return_value.spreadsheet
        with patch.object(da, "onglet", return_value=FakeWorksheet([])):
            with patch.object(da.stockage, "_lire_publications", return_value=[{"id": "i1"}]):
                with patch.object(da.diffusion, "selectionner_a_envoyer", return_value=[{"id": "i1"}]):
                    import pytest
                    with pytest.raises(ValueError, match="non autorisee"):
                        da.run(send=True, campagne_test="prive-01", test_email="intrus@example.org")
