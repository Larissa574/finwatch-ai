"""Point d'entrée de la diffusion : lit le Sheet, envoie, met à jour les statuts.

Usage :
  python src/run_diffusion.py                 # envoi réel
  python src/run_diffusion.py --dry-run       # aperçu bulletin_apercu.html, aucun envoi
  python src/run_diffusion.py --retry-erreurs # renvoie aussi les lignes ERREUR_ENVOI
  python src/run_diffusion.py --controle      # liste A_VERIFIER + anomalies

STORE=sheets (défaut) : GOOGLE_SHEET_ID + GOOGLE_CREDENTIALS_JSON
STORE=json            : fichier local JSON_PATH (tests sans Google)
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))
import diffusion  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("finwatch.run")

ONGLET_PUBLICATIONS = "Publications"
ONGLET_JOURNAL = "Journal diffusion"


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class JsonStore:
    def __init__(self, chemin):
        self.chemin = chemin

    def lire(self):
        with open(self.chemin, encoding="utf-8") as f:
            return json.load(f)

    def maj(self, pub_id, champs):
        data = self.lire()
        for p in data:
            if p["id"] == pub_id:
                p.update(champs)
        with open(self.chemin, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def journal(self, ligne):
        log.info("JOURNAL %s", ligne)


class SheetsStore:
    def __init__(self, sheet_id, credentials_json):
        import gspread
        self.sh = gspread.service_account_from_dict(json.loads(credentials_json)).open_by_key(sheet_id)
        self.ws = self.sh.worksheet(ONGLET_PUBLICATIONS)

    def lire(self):
        return [{k: (None if (isinstance(v, str) and not v.strip()) else v) for k, v in l.items()}
                for l in self.ws.get_all_records()]

    def maj(self, pub_id, champs):
        from gspread.utils import rowcol_to_a1
        entetes = self.ws.row_values(1)
        ids = self.ws.col_values(entetes.index("id") + 1)
        ligne = ids.index(pub_id) + 1
        self.ws.batch_update([
            {"range": rowcol_to_a1(ligne, entetes.index(c) + 1), "values": [["" if v is None else v]]}
            for c, v in champs.items()
        ])

    def journal(self, ligne):
        try:
            try:
                ws = self.sh.worksheet(ONGLET_JOURNAL)
            except Exception:
                ws = self.sh.add_worksheet(ONGLET_JOURNAL, rows=500, cols=5)
                ws.append_row(["date", "action", "nb_articles", "resultat", "detail"])
            ws.append_row(ligne)
        except Exception as e:
            log.warning("Journal impossible : %s", e)


def controle(pubs):
    a_verifier = [p for p in pubs if p.get("statut_validation") in ("A_VALIDER", "A_VERIFIER")]
    print(f"{len(a_verifier)} publications en attente de validation :")
    for p in a_verifier:
        print(f"  - {p['id']} | {p.get('titre')}\n    {p.get('url')}")
    anomalies = []
    for p in pubs:
        if p.get("statut_validation") in ("VALIDE", "REJETE") and not (p.get("valide_par") and p.get("date_validation")):
            anomalies.append(f"{p['id']} : décision sans valide_par/date_validation")
        if p.get("statut_validation") == "VALIDE" and not p.get("resume_ia"):
            anomalies.append(f"{p['id']} : VALIDE sans resume_ia")
        if p.get("statut_envoi") == "ENVOYE" and p.get("statut_validation") != "VALIDE":
            anomalies.append(f"{p['id']} : ENVOYE mais non VALIDE")
    print(f"{len(anomalies)} anomalie(s)")
    for a in anomalies:
        print("  !", a)
    return 1 if anomalies else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--retry-erreurs", action="store_true")
    ap.add_argument("--controle", action="store_true")
    a = ap.parse_args()

    if os.getenv("STORE", "sheets").lower() == "json":
        store = JsonStore(os.getenv("JSON_PATH", "tests/donnees_test.json"))
    else:
        store = SheetsStore(os.environ["GOOGLE_SHEET_ID"], os.environ["GOOGLE_CREDENTIALS_JSON"])

    pubs = store.lire()
    if a.controle:
        sys.exit(controle(pubs))

    if a.dry_run:
        choisies = diffusion.selectionner_a_envoyer(pubs, a.retry_erreurs)
        if not choisies:
            log.info("Rien à envoyer.")
            return
        with open("bulletin_apercu.html", "w", encoding="utf-8") as f:
            f.write(diffusion.generer_bulletin(choisies))
        log.info("DRY-RUN : %d article(s) -> bulletin_apercu.html", len(choisies))
        return

    def ok(ids, date_envoi):
        for i in ids:
            store.maj(i, {"statut_envoi": "ENVOYE", "date_envoi": date_envoi})
        store.journal([date_envoi, "diffusion", len(ids), "ENVOYE", ""])

    def erreur(ids):
        for i in ids:
            store.maj(i, {"statut_envoi": "ERREUR_ENVOI"})
        store.journal([now(), "diffusion", len(ids), "ERREUR_ENVOI", "voir logs"])

    code = diffusion.diffuser(pubs, ok, erreur, a.retry_erreurs)
    if code == 0 and not diffusion.selectionner_a_envoyer(pubs, a.retry_erreurs):
        store.journal([now(), "diffusion", 0, "RIEN_A_ENVOYER", ""])
    sys.exit(code)


if __name__ == "__main__":
    main()
