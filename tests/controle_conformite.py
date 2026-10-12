"""
Contrôle de conformité d'un résultat d'analyse avec le cahier des charges (v1.1).

Usage (depuis la racine du dépôt) :
    python tests/controle_conformite.py <entree.json> <sortie.json>
Exemple :
    python tests/controle_conformite.py data/collecte/jeu_reference.json data/analyse/publications_analysees.json

Le journal (journal_analyse.json) doit se trouver dans le même dossier que la sortie.
Code retour : 0 = tout est conforme, 1 = au moins un écart.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import analyse as a  # noqa: E402

ecarts = []


def verifier(libelle, condition, detail=""):
    print(("  [OK]    " if condition else "  [ECART] ") + libelle + (f" -> {detail}" if detail and not condition else ""))
    if not condition:
        ecarts.append(libelle)


def main():
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    chemin_entree, chemin_sortie = Path(sys.argv[1]), Path(sys.argv[2])
    entree = json.loads(chemin_entree.read_text(encoding="utf-8"))
    sortie = json.loads(chemin_sortie.read_text(encoding="utf-8"))
    journal = json.loads((chemin_sortie.parent / "journal_analyse.json").read_text(encoding="utf-8"))
    parametres = journal.get("parametres", {})
    # Si l'exécution était partielle (--source / --limite), on compare à la même sélection.
    entree = a.selectionner(entree, parametres.get("source"), parametres.get("limite"))
    if parametres.get("ia_simulee"):
        print("\n[ATTENTION] Ce fichier a été produit avec l'IA SIMULÉE : ses analyses sont factices,")
        print("            il ne doit JAMAIS être utilisé comme résultat officiel.")
    origines = parametres.get("mots_cles", {})
    if "provisoire" in origines.values():
        print("[INFO] Mots-clés provisoires utilisés (config/mots_cles.json non rempli ou incomplet).")
    par_id = {}  # première occurrence de chaque id (c'est celle que le module conserve)
    for p in entree:
        if isinstance(p, dict) and p.get("id"):
            par_id.setdefault(p["id"], p)

    print(f"\nEntrée : {len(entree)} éléments | Sortie : {len(sortie)} | "
          f"doublons écartés : {len(journal['doublons_ecartes'])} | "
          f"entrées invalides : {len(journal['entrees_invalides'])}\n")

    print("1. Aucune perte silencieuse")
    verifier("entrée = sortie + doublons + invalides",
             len(entree) == len(sortie) + len(journal["doublons_ecartes"]) + len(journal["entrees_invalides"]),
             f"{len(entree)} != {len(sortie)}+{len(journal['doublons_ecartes'])}+{len(journal['entrees_invalides'])}")
    verifier("aucune sortie non conforme signalée dans le journal", journal["sorties_non_conformes"] == [])

    print("2. Les neuf champs d'entrée sont conservés à l'identique")
    modifies = [o["id"][:12] for o in sortie for c in a.CHAMPS_ENTREE
                if c in par_id.get(o["id"], {}) and o.get(c) != par_id[o["id"]][c]]
    verifier("aucun champ d'entrée modifié", not modifies, str(modifies[:5]))

    print("3. Trois statuts de pertinence, champs ajoutés présents")
    verifier("statut_pertinence dans {pertinent, non_pertinent, incertain}",
             all(o.get("statut_pertinence") in a.STATUTS_PERTINENCE for o in sortie))
    verifier("tous les champs ajoutés sont présents",
             all(c in o for o in sortie for c in a.CHAMPS_AJOUTES))
    verifier("priorite dans {haute, moyenne, basse}",
             all(o.get("priorite") in a.PRIORITES for o in sortie))
    verifier("motif_rejet renseigné uniquement pour non_pertinent",
             all((isinstance(o.get("motif_rejet"), str) and bool(o["motif_rejet"].strip()))
                 if o.get("statut_pertinence") == "non_pertinent"
                 else o.get("motif_rejet") is None for o in sortie))

    print("4. Catégories et statuts d'analyse autorisés")
    verifier("categorie = un des 4 codes ou null",
             all(o["categorie"] is None or o["categorie"] in a.CATEGORIES for o in sortie))
    verifier("statut_analyse = effectuee / incertaine / en_echec (pertinents uniquement)",
             all((o["statut_analyse"] in a.STATUTS_ANALYSE) == (o["statut_pertinence"] == "pertinent")
                 for o in sortie))
    verifier("une analyse 'effectuee' a une catégorie",
             all(o["categorie"] for o in sortie if o["statut_analyse"] == "effectuee"))

    print("5. Rien d'inventé")
    verifier("non pertinent / incertain : aucun champ d'analyse rempli",
             all(o[c] is None for o in sortie if o["statut_pertinence"] != "pertinent"
                 for c in a.CHAMPS_ANALYSE + ["categorie"]))
    verifier("titre seul : aucun champ d'analyse rempli",
             all(o[c] is None for o in sortie if o["niveau_information"] in ("metadonnees_seules", "insuffisant")
                 for c in a.CHAMPS_ANALYSE))
    verifier("aucune chaîne du type 'non précisé' (null attendu)",
             all(a.normaliser(o[c]) not in ("non precise", "non precisee", "n a", "null", "none", "")
                 for o in sortie for c in a.CHAMPS_ANALYSE if isinstance(o[c], str)))
    chiffres = []
    for o in sortie:
        if o["statut_analyse"] == "effectuee":
            source = f"{o['titre']} {a.nettoyer_texte(o.get('resume_original'))} {o.get('date_publication')}"
            texte = " ".join(o[c] for c in a.CHAMPS_ANALYSE if o[c])
            if a._nombres(texte) - a._nombres(source):
                chiffres.append(o["titre"][:40])
    verifier("analyses 'effectuee' : aucun chiffre absent de la source", not chiffres, str(chiffres[:3]))

    print("\nA relire par un humain :")
    for o in sortie:
        if o["statut_pertinence"] == "incertain" or o["statut_analyse"] in ("incertaine", "en_echec"):
            print(f"  - {o['statut_pertinence']:<13} {str(o['statut_analyse']):<10} {o['titre'][:60]}")

    print("\n" + ("CONFORME : aucun écart détecté." if not ecarts else f"{len(ecarts)} ÉCART(S) À CORRIGER."))
    return 1 if ecarts else 0


if __name__ == "__main__":
    sys.exit(main())