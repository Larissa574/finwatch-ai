
import html as _html
import os
import re
import smtplib
import ssl
from collections import OrderedDict
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Callable

AXES = OrderedDict([
    ("MARCHES_FINANCIERS", "Marchés financiers"),
    ("REGLEMENTATION_CONFORMITE", "Réglementation et conformité"),
    ("CREDIT_MICROFINANCE", "Crédit et microfinance"),
    ("BANQUE", "Banque"),
])
AUTRES = "Autres thèmes"
CHAMPS_OBLIGATOIRES = ("id", "titre", "url", "source", "resume_ia")


def _maintenant_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _e(valeur: Any) -> str:
    return _html.escape(str(valeur)) if valeur not in (None, "") else "non précisé"


def _url_sure(url: str) -> str:
    return url if str(url).startswith(("http://", "https://")) else "#"


def _est_validee(pub: dict[str, Any]) -> bool:
    """Garde-fou : VALIDE + validateur + date + champs indispensables."""
    return (
        pub.get("statut_validation") == "VALIDE"
        and bool(pub.get("valide_par"))
        and bool(pub.get("date_validation"))
        and all(pub.get(c) for c in CHAMPS_OBLIGATOIRES)
    )


def selectionner_a_envoyer(
    publications: list[dict[str, Any]], retry_erreurs: bool = False
) -> list[dict[str, Any]]:
    """Contrat C : lignes VALIDE + NON_ENVOYE (+ ERREUR_ENVOI si relance demandée)."""
    statuts_ok = {"NON_ENVOYE", None, ""}
    if retry_erreurs:
        statuts_ok.add("ERREUR_ENVOI")
    return [
        p for p in publications
        if _est_validee(p) and p.get("statut_envoi") in statuts_ok
    ]


def generer_bulletin(publications: list[dict[str, Any]]) -> str:
    """Produire le HTML à partir des seules analyses validées."""
    validees = [p for p in publications if _est_validee(p)]
    if not validees:
        raise ValueError("Aucune analyse validée : pas de bulletin à générer.")

    groupes: OrderedDict[str, list] = OrderedDict((c, []) for c in AXES)
    groupes[AUTRES] = []
    for p in validees:
        groupes.get(p.get("categorie"), groupes[AUTRES]).append(p)

    date_txt = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    h = [
        '<html><body style="font-family:Arial,sans-serif;max-width:680px;margin:auto;color:#222">',
        '<h1 style="color:#0b3d6b">FINWATCH AI — Bulletin de veille</h1>',
        f'<p style="color:#555">{date_txt} · {len(validees)} publication(s) vérifiée(s) '
        "par un membre de l'équipe.</p>",
    ]
    for code, items in groupes.items():
        if not items:
            continue
        h.append(
            f'<h2 style="color:#0b3d6b;border-bottom:2px solid #0b3d6b">'
            f"{_e(AXES.get(code, AUTRES))}</h2>"
        )
        for p in items:
            h.append(
                '<div style="margin:14px 0;padding:10px;background:#f5f8fb;border-radius:6px">'
                f'<h3 style="margin:0 0 4px"><a href="{_e(_url_sure(p["url"]))}">{_e(p["titre"])}</a></h3>'
                f'<div style="color:#666;font-size:13px">{_e(p["source"])} · '
                f'publié le {_e(p.get("date_publication"))}</div>'
                f'<p><b>Résumé vérifié :</b> {_e(p["resume_ia"])}</p>'
                f'<p><b>Innovation :</b> {_e(p.get("innovation"))}</p>'
                f'<p><b>Application financière :</b> {_e(p.get("application_financiere"))}</p>'
                f'<p><b>Intérêt potentiel :</b> {_e(p.get("impact_potentiel"))}</p>'
                f'<div style="font-size:12px;color:#888">Validé par {_e(p.get("valide_par"))} '
                f'le {_e(p.get("date_validation"))}</div></div>'
            )
    h.append(
        '<p style="font-size:12px;color:#888">Projet universitaire FINWATCH AI. '
        "Consultez la source originale avant toute décision.</p></body></html>"
    )
    return "".join(h)


def envoyer_bulletin(html: str) -> None:
    """Envoyer le bulletin et laisser tracer l'envoi seulement s'il réussit.

    Lève une exception en cas d'échec : l'appelant ne doit marquer ENVOYE
    que si cette fonction retourne normalement.
    """
    hote = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    mdp = os.environ["SMTP_PASSWORD"]
    expediteur = os.getenv("MAIL_FROM") or user
    destinataires = [d.strip() for d in os.environ["MAIL_TO"].split(",") if d.strip()]
    if not destinataires:
        raise ValueError("MAIL_TO est vide")

    sujet = os.getenv("MAIL_SUBJECT") or (
        f"FINWATCH AI – Bulletin de veille du {datetime.now(timezone.utc):%d/%m/%Y}"
    )
    texte = _html.unescape(re.sub(r"<[^>]+>", "", re.sub(r"</(p|div|h\d)>", "\n", html)))

    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = sujet, expediteur, ", ".join(destinataires)
    msg.attach(MIMEText(texte, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    ctx = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(hote, port, context=ctx, timeout=30) as s:
            s.login(user, mdp)
            s.sendmail(expediteur, destinataires, msg.as_string())
    else:
        with smtplib.SMTP(hote, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(user, mdp)
            s.sendmail(expediteur, destinataires, msg.as_string())


def diffuser(
    publications: list[dict[str, Any]],
    marquer_envoye: Callable[[list[str], str], None],
    marquer_erreur: Callable[[list[str]], None],
    retry_erreurs: bool = False,
) -> int:
    """Orchestration : sélection -> bulletin -> envoi -> traçage.

    marquer_envoye(ids, date_envoi) : à brancher sur l'écriture Sheets
        (statut_envoi=ENVOYE + date_envoi).
    marquer_erreur(ids) : statut_envoi=ERREUR_ENVOI.
    Retourne 0 (ok ou rien à envoyer), 1 (échec d'envoi).
    """
    a_envoyer = selectionner_a_envoyer(publications, retry_erreurs)
    if not a_envoyer:
        return 0
    ids = [p["id"] for p in a_envoyer]
    corps = generer_bulletin(a_envoyer)
    try:
        envoyer_bulletin(corps)
    except Exception:
        marquer_erreur(ids)
        return 1
    marquer_envoye(ids, _maintenant_utc())
    return 0
