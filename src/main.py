
"""Point d'entrée du pipeline FINWATCH AI.

Étape actuelle : collecte -> stockage Google Sheets.
L'analyse IA et la diffusion seront intégrées après leurs tests.
"""

import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

COLLECTEUR = BASE_DIR / "src" / "collecte.py"
IMPORTATEUR = BASE_DIR / "src" / "importer_stockage.py"


def executer_script(chemin: Path, description: str) -> None:
    """Exécute un script Python et arrête le pipeline en cas d'erreur."""
    if not chemin.is_file():
        raise FileNotFoundError(f"Fichier introuvable : {chemin}")

    print(f"\n{'=' * 55}", flush=True)
    print(description, flush=True)
    print("=" * 55, flush=True)

    subprocess.run(
        [sys.executable, str(chemin)],
        cwd=str(BASE_DIR),
        check=True,
    )


def main() -> None:
    """Exécute la collecte puis le stockage."""
    try:
        executer_script(
            COLLECTEUR,
            "ÉTAPE 1 — COLLECTE DES PUBLICATIONS",
        )

        executer_script(
            IMPORTATEUR,
            "ÉTAPE 2 — STOCKAGE DANS GOOGLE SHEETS",
        )

        print("\nPipeline FINWATCH AI terminé avec succès.", flush=True)
        print(
            "Les publications restent soumises à la validation humaine.",
            flush=True,
        )

    except subprocess.CalledProcessError as erreur:
        print(
            f"\nPipeline interrompu : code de sortie {erreur.returncode}.",
            flush=True,
        )
        raise SystemExit(erreur.returncode)

    except (FileNotFoundError, OSError) as erreur:
        print(f"\nErreur du pipeline : {erreur}", flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
