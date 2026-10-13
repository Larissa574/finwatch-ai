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
