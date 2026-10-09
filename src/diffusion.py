"""Charbel — vérification humaine coordonnée, bulletin HTML et diffusion.

La sélection doit être validée humainement avant la création du bulletin.
"""

from typing import Any


def generer_bulletin(publications: list[dict[str, Any]]) -> str:
    """Produire le HTML à partir des seules analyses validées."""
    raise NotImplementedError("Bulletin HTML à développer par Charbel.")


def envoyer_bulletin(html: str) -> None:
    """Envoyer le bulletin et laisser tracer l'envoi seulement s'il réussit."""
    raise NotImplementedError("Envoi d'e-mails à développer par Charbel.")
