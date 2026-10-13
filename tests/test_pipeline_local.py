"""Tests du pipeline local : ni Google Sheets ni Gemini ni SMTP."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import pipeline_local


def test_pipeline_local_bout_en_bout():
    with TemporaryDirectory() as dossier:
        # Toute tentative de contact externe doit faire echouer le test.
        with patch("smtplib.SMTP", side_effect=AssertionError("SMTP interdit")), \
             patch("smtplib.SMTP_SSL", side_effect=AssertionError("SMTP interdit")):
            bilan = pipeline_local.lancer(Path(dossier))
        assert bilan["collectees"] == 2
        assert bilan["importees"] == 1
        assert bilan["a_valider"] == 2
        assert bilan["apercu_articles"] == 1
        html = (Path(dossier) / "bulletin_apercu.html").read_text(encoding="utf-8")
        assert "FINWATCH AI" in html
        assert "DEMO" in html
        import json
        lignes = json.loads((Path(dossier) / "stockage_local.json").read_text(encoding="utf-8"))
        assert all(l["statut_validation"] == "A_VALIDER" for l in lignes)
        assert all(l["statut_envoi"] == "NON_ENVOYE" for l in lignes)
