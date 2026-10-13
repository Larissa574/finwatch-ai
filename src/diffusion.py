
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


def _date_courte(valeur):
    """Affiche une date ISO de maniere concise, sans inventer de date."""
    if not valeur:
        return None
    try:
        return datetime.fromisoformat(str(valeur).replace("Z", "+00:00")).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return str(valeur)


def generer_bulletin(publications: list[dict[str, Any]]) -> str:
    """Bulletin V2 : une synthese editoriale unifiee par publication.

    Le texte affiche est le resume_fr deja valide, stocke dans resume_ia.
    Ne jamais assembler automatiquement innovation/impact en prose : ces
    champs peuvent contenir des hypotheses non etayees par la source.
    """
    validees = [p for p in publications if _est_validee(p)]
    if not validees:
        raise ValueError("Aucune analyse validée : pas de bulletin à générer.")

    groupes: OrderedDict[str, list] = OrderedDict((c, []) for c in AXES)
    groupes[AUTRES] = []
    for p in validees:
        groupes.get(p.get("categorie"), groupes[AUTRES]).append(p)

    date_txt = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    h = [
        '<!DOCTYPE html><html lang="fr"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>FINWATCH AI — Bulletin de veille</title></head>',
        '<body style="margin:0;padding:0;background:#eef3f7;font-family:Arial,Helvetica,sans-serif;color:#172b3a">',
        '<div style="max-width:680px;margin:0 auto;background:#ffffff">',
        '<div style="background:#103c61;padding:30px 26px">',
        '<h1 style="color:#ffffff;font-size:28px;margin:0 0 8px">FINWATCH AI</h1>',
        '<p style="color:#dcecf9;margin:0;font-size:16px">Bulletin de veille stratégique · IA et finance</p>',
        '</div>',
        '<div style="padding:22px 26px">',
        f'<p style="color:#607386;font-size:13px;margin:0 0 18px">{date_txt} · '
        f'{len(validees)} publication(s) validée(s)</p>',
        '<p style="font-size:15px;line-height:1.6;margin:0 0 25px">'
        "Les évolutions de l’intelligence artificielle dans le secteur financier, "
        "présentées sous forme de synthèses vérifiées et sourcées.</p>",
    ]
    for code, items in groupes.items():
        if not items:
            continue
        h.append(
            '<h2 style="font-size:18px;color:#103c61;margin:25px 0 14px;'
            'padding-bottom:8px;border-bottom:2px solid #103c61">'
            f'{_e(AXES.get(code, AUTRES))}</h2>'
        )
        for p in items:
            url = _e(_url_sure(p["url"]))
            titre = _e(p["titre"])
            date_pub = _date_courte(p.get("date_publication"))
            meta = _e(p["source"])
            if date_pub:
                meta += " · " + _e(date_pub)
            # Le resume_ia doit etre valide comme texte final coherent.
            synthese = _e(p["resume_ia"]).replace("\\n", "<br>")
            h.extend([
                '<div style="padding:18px 0;border-bottom:1px solid #e1e8ef">',
                f'<h3 style="font-size:18px;line-height:1.4;margin:0 0 7px;color:#172b3a">{titre}</h3>',
                f'<p style="font-size:12px;color:#697c8d;margin:0 0 13px">{meta}</p>',
                f'<p style="font-size:15px;line-height:1.7;margin:0 0 14px">{synthese}</p>',
                f'<a href="{url}" style="color:#0b578c;font-size:14px;text-decoration:underline">'
                "Consulter la source originale</a>",
                '</div>',
            ])
    h.extend([
        '<p style="font-size:12px;line-height:1.6;color:#718292;margin:27px 0 0">'
        "FINWATCH AI · Projet universitaire de veille. Les synthèses ont fait l’objet "
        "d’une validation humaine. Consultez les sources avant toute décision.</p>",
        '</div></div></body></html>',
    ])
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
