"""Larissa — collecte des publications (RSS, API, alertes selon faisabilité).

Contrat de sortie : une liste de dictionnaires contenant les champs décrits
dans docs/contrat-echange.md, sans analyse générée par IA.
"""

from typing import Any


def collecter(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Retourner les nouvelles publications normalisées.

    À implémenter : requêtes par source, calendrier, dates et journal d'erreurs.
    """
    raise NotImplementedError("Collecte à développer par Larissa.")
