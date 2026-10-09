"""Sosthene — Google Sheets, historique, déduplication et validation.

Les mises à jour ne doivent pas effacer une validation humaine déjà effectuée.
"""

from typing import Any


def enregistrer(publication: dict[str, Any]) -> None:
    """Insérer ou actualiser une publication selon son identifiant stable."""
    raise NotImplementedError("Connexion Google Sheets à développer par Sosthene.")


def publications_a_diffuser() -> list[dict[str, Any]]:
    """Sélectionner VALIDE et NON_ENVOYE dans Google Sheets."""
    raise NotImplementedError("Lecture des informations validées à développer.")
