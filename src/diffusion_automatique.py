"""Diffusion FINWATCH AI avec abonnements, desinscription et journal individuel.

Par defaut le script simule; --send et FINWATCH_AUTORISER_ENVOI=OUI
sont tous deux necessaires pour envoyer.
"""
import argparse
import hashlib
import hmac
import html
import os
import re
import sys
from datetime import datetime, timezone
from email.utils import parseaddr
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(__file__))
import diffusion
import stockage

HEADERS_ABONNES = ["email", "statut", "date_inscription", "date_desinscription", "source_consentement"]
HEADERS_JOURNAL = ["campagne", "email", "date", "statut", "articles"]


def onglet(book, name, headers):
    import gspread
    try:
        ws = book.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=name, rows=1000, cols=len(headers))
        ws.append_row(headers)
    if ws.row_values(1) != headers:
        raise RuntimeError("Structure inattendue : " + name)
    return ws


def emails_actifs(ws):
    """Exclure les desinscrits meme en presence d'anciens doublons."""
    lignes = ws.get_all_records()
    exclus = {str(p.get("email") or "").strip().lower() for p in lignes
              if p.get("statut") == "DESINSCRIT"}
    resultat, deja = [], set()
    for p in lignes:
        adresse = str(p.get("email") or "").strip().lower()
        if (p.get("statut") == "ACTIF" and p.get("date_inscription") and
                p.get("source_consentement") and adresse and
                parseaddr(adresse)[1] == adresse and adresse not in exclus and
                adresse not in deja and "\n" not in adresse and "\r" not in adresse):
            resultat.append(adresse)
            deja.add(adresse)
    return resultat


def lien_desinscription(email):
    base = os.environ["FINWATCH_WEBAPP_URL"]
    if not base.startswith("https://"):
        raise ValueError("FINWATCH_WEBAPP_URL doit etre HTTPS")
    cle = os.environ["FINWATCH_HMAC_SECRET"].encode("utf-8")
    token = hmac.new(cle, email.encode("utf-8"), hashlib.sha256).hexdigest()
    return base + "?" + urlencode({"action": "unsubscribe", "email": email, "token": token})


def ajouter_desinscription(bulletin, email):
    lien = html.escape(lien_desinscription(email), quote=True)
    bloc = ('<div style="padding:24px 26px;text-align:center;'
            'font:12px Arial;color:#607386;background:#f2f6fa">'
            '<p>Vous recevez cet email parce que vous êtes abonné à FINWATCH AI.</p>'
            f'<a href="{lien}" style="display:inline-block;padding:12px 20px;'
            'border-radius:8px;background:#e2e8ef;color:#103c61;'
            'text-decoration:none;font-weight:bold;font-size:14px">'
            'Se désabonner</a></div>')
    return bulletin.replace("</body>", bloc + "</body>")


def run(send=False, campagne_test=None, test_email=None):
    book = stockage._feuille().spreadsheet
    abonnes = onglet(book, "Abonnes", HEADERS_ABONNES)
    journal = onglet(book, "Journal envois", HEADERS_JOURNAL)
    pubs = diffusion.selectionner_a_envoyer(
        stockage._lire_publications(book.worksheet("Publications")))
    if not pubs:
        print("Aucune publication validée non envoyée.")
        return 0
    ids = sorted(str(p["id"]) for p in pubs)
    campagne = hashlib.sha256("\n".join(ids).encode()).hexdigest()[:20]
    if test_email:
        test_email = str(test_email).strip().lower()
        if test_email != os.environ.get("FINWATCH_TEST_EMAIL", "").strip().lower():
            raise ValueError("Adresse privee non autorisee.")
        if not campagne_test:
            raise ValueError("Campagne de test obligatoire.")
    if campagne_test:
        if not re.fullmatch(r"[a-zA-Z0-9_-]{5,50}", campagne_test):
            raise ValueError("Identifiant de campagne invalide.")
        campagne = "test-" + campagne_test
    deja = {(str(r["campagne"]), str(r["email"]).lower()) for r in journal.get_all_records()
            if r.get("statut") == "ENVOYE"}
    destinataires = [a for a in emails_actifs(abonnes) if (campagne, a) not in deja]
    if test_email:
        destinataires = [a for a in destinataires if a == test_email]
    print("Campagne :", campagne, "Articles :", len(pubs),
          "Destinataires restants :", len(destinataires))
    if not send:
        print("SIMULATION : aucun email envoyé.")
        return 0
    if not destinataires:
        print("Aucun destinataire à servir.")
        return 0
    if os.getenv("FINWATCH_AUTORISER_ENVOI") != "OUI":
        raise RuntimeError("Envoi bloqué : FINWATCH_AUTORISER_ENVOI=OUI requis.")
    if len(destinataires) > int(os.getenv("FINWATCH_MAX_DESTINATAIRES", "50")):
        raise RuntimeError("Trop de destinataires pour cette campagne.")
    if not destinataires:
        return 0
    bulletin = diffusion.generer_bulletin(pubs)
    erreurs = 0
    for adresse in destinataires:
        if adresse not in emails_actifs(abonnes):
            continue
        ancien = os.environ.get("MAIL_TO")
        try:
            os.environ["MAIL_TO"] = adresse
            diffusion.envoyer_bulletin(ajouter_desinscription(bulletin, adresse))
            journal.append_row(
                [campagne, adresse, datetime.now(timezone.utc).isoformat(), "ENVOYE", ",".join(ids)],
                value_input_option="RAW")
            print("Transmis et journalisé :", adresse)
        except Exception as erreur:
            erreurs += 1
            print("ECHEC :", adresse, type(erreur).__name__)
        finally:
            if ancien is None:
                os.environ.pop("MAIL_TO", None)
            else:
                os.environ["MAIL_TO"] = ancien
    # Le journal individuel fait foi. Ne pas marquer tous les articles ENVOYE
    # lorsqu'une campagne a pu etre seulement partiellement livree.
    return 1 if erreurs else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--campagne-test", help="Identifiant de nouvelle campagne de test")
    parser.add_argument("--test-email")
    args = parser.parse_args()
    sys.exit(run(args.send, args.campagne_test, args.test_email))
