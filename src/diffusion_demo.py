"""Campagnes de demonstration isolees : editions explicites et liste autorisee.

Usage en simulation :
  python src/diffusion_demo.py --edition demo01 --articles "id1,id2"
Pour envoyer : ajouter --send ; FINWATCH_DEMO_EMAILS doit lister les volontaires.
Le workflow dedie transmet cette liste via un secret GitHub.
"""
import argparse
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import diffusion
import diffusion_automatique as base
import stockage


def decouper(texte):
    return [x.strip() for x in (texte or "").split(",") if x.strip()]


def planifier(edition, articles, autorises, publications, abonnes, journal):
    if not re.fullmatch(r"[a-zA-Z0-9_-]{5,40}", edition):
        raise ValueError("Identifiant edition invalide (5 a 40 lettres/chiffres/_/-).")
    ids = decouper(articles)
    if not ids or len(ids) > 10 or len(ids) != len(set(ids)):
        raise ValueError("Choisir entre 1 et 10 identifiants d'articles DISTINCTS.")
    groupe = [s.lower() for s in decouper(autorises)]
    if not groupe or len(groupe) > 10 or len(groupe) != len(set(groupe)):
        raise ValueError("FINWATCH_DEMO_EMAILS : 1 a 10 emails distincts obligatoires.")
    from email.utils import parseaddr
    if any(parseaddr(e)[1] != e or "\n" in e or "\r" in e for e in groupe):
        raise ValueError("Adresse de demonstration invalide.")
    par_id = {str(p.get("id")): p for p in publications}
    manquants = [i for i in ids if i not in par_id]
    if manquants:
        raise ValueError("Publications introuvables : " + ", ".join(manquants))
    selection = [par_id[i] for i in ids]
    if any(not diffusion._est_validee(p) for p in selection):
        raise ValueError("Tous les articles de l'edition doivent etre VALIDE, avec validateur, date et resume.")
    campagne = "demo-" + edition
    article_ids = ",".join(sorted(ids))
    precedents = [r for r in journal if str(r.get("campagne")) == campagne]
    if any(str(r.get("articles") or "") != article_ids for r in precedents):
        raise ValueError("Edition deja utilisee avec un autre ensemble d'articles : choisir un nouvel identifiant.")
    deja = {str(r.get("email") or "").lower() for r in precedents if r.get("statut") == "ENVOYE"}
    actifs = set(base.emails_actifs(abonnes))
    destinations = [a for a in groupe if a in actifs and a not in deja]
    return campagne, article_ids, selection, destinations, len(deja)


def run(edition, articles, send=False):
    autorises = os.getenv("FINWATCH_DEMO_EMAILS", "")
    book = stockage._feuille().spreadsheet
    ws_abonnes = base.onglet(book, "Abonnes", base.HEADERS_ABONNES)
    ws_journal = base.onglet(book, "Journal envois", base.HEADERS_JOURNAL)
    campagne, ids, selection, destinataires, deja = planifier(
        edition, articles, autorises,
        stockage._lire_publications(book.worksheet("Publications")),
        ws_abonnes, ws_journal.get_all_records()
    )
    print("Edition :", campagne, "| Articles :", len(selection),
          "| Deja servis :", deja, "| Restants :", len(destinataires))
    print("Articles :", ids)
    print("Destinataires autorises et actifs restants :", ", ".join(destinataires) or "aucun")
    if not send:
        print("SIMULATION : aucun email n'a ete envoye.")
        return 0
    if os.getenv("FINWATCH_DEMO_AUTORISER_ENVOI") != "OUI":
        raise RuntimeError("Autorisation demo absente.")
    if not destinataires:
        print("Aucun nouvel envoi.")
        return 0
    bulletin = diffusion.generer_bulletin(selection)
    echecs = 0
    for adresse in destinataires:
        if adresse not in base.emails_actifs(ws_abonnes):
            print("Desinscription constatee avant envoi :", adresse)
            continue
        ancien = os.environ.get("MAIL_TO")
        try:
            os.environ["MAIL_TO"] = adresse
            diffusion.envoyer_bulletin(base.ajouter_desinscription(bulletin, adresse))
            ws_journal.append_row([campagne, adresse, datetime.now(timezone.utc).isoformat(),
                                   "ENVOYE", ids], value_input_option="RAW")
            print("ENVOYE ET JOURNALISE :", adresse)
        except Exception as erreur:
            echecs += 1
            print("ECHEC :", adresse, type(erreur).__name__)
        finally:
            if ancien is None:
                os.environ.pop("MAIL_TO", None)
            else:
                os.environ["MAIL_TO"] = ancien
    return 1 if echecs else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--edition", required=True)
    p.add_argument("--articles", required=True, help="Identifiants Google Sheets separes par virgules")
    p.add_argument("--send", action="store_true")
    args = p.parse_args()
    sys.exit(run(args.edition, args.articles, args.send))
