"""
Tests du module src/analyse.py (format unittest, comme tests/test_contrat.py,
donc exécutés par le workflow : python -m unittest discover -s tests -v).
Aucun appel réseau : fausse IA et faux classificateur.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "src"))
import analyse as a  # noqa: E402

# Les tests unitaires utilisent des mots-clés fixes ; un test séparé valide la configuration active.
MOTS = a.mots_cles_provisoires()

BANQUE = ("A machine learning approach to bank fraud detection on card payments, "
          "evaluated on anonymised transaction data from several retail banks.")


def pub(id_, titre, resume=BANQUE, date="2026-10-09", source="arXiv"):
    return {"id": id_, "titre": titre, "source": source, "url": f"https://x.org/{id_}",
            "date_publication": date, "date_collecte": "2026-10-11T08:00:00+00:00",
            "auteur": [], "resume_original": resume, "type_document": "publication"}


def traiter(*args, **kwargs):
    return a.traiter_publications(*args, mots_cles=MOTS, **kwargs)


def faux_classificateur(texte):
    return 0.05 if "robotics" in texte.lower() else 0.95


def ok_ia(systeme, utilisateur):
    return a.appeler_ia_simulee(systeme, utilisateur)


class TestDedoublonnage(unittest.TestCase):
    def test_id_et_titre_meme_jour_avec_formats_de_date_differents(self):
        lot = [pub("a", "Bank AI assistant", date="2026-10-10T09:15:00+00:00"),
               pub("a", "Autre titre"),                              # même id
               pub("b", "Bank  AI assistant!", date="2026-10-10"),   # même titre et même jour
               pub("c", "Titre différent")]
        uniques, doublons = a.dedoublonner(lot)
        self.assertEqual([p["id"] for p in uniques], ["a", "c"])
        self.assertEqual([d["raison"] for d in doublons],
                         ["même id", "même titre et même date de publication"])


class TestFiltrage(unittest.TestCase):
    def test_decider(self):
        self.assertEqual(a.decider("fort", 0.9, True), "pertinent")
        self.assertEqual(a.decider("fort", 0.1, True), "incertain")  # désaccord : pas de rejet silencieux
        self.assertEqual(a.decider("aucun", 0.9, True), "incertain")
        self.assertEqual(a.decider("aucun", 0.1, True), "non_pertinent")
        self.assertEqual(a.decider("faible", 0.5, True), "incertain")
        self.assertEqual(a.decider("fort", None, True), "pertinent")  # règles seules
        self.assertEqual(a.decider("aucun", None, False), "incertain")
        self.assertEqual(a.decider("aucun", None, True), "non_pertinent")

    def test_finextra_finance_sans_ia_ne_declenche_pas_gemini(self):
        cas = [
            ("FCA cracks down on finfluencers",
             "The UK's financial watchdog has stepped up enforcement of illegal finfluencer promotions.", 0.7114),
            ("Goldman Sachs appoints banking tech co-head",
             "Goldman Sachs names an executive as co-head of technology investment banking.", 0.736),
        ]
        for i, (titre, resume, score) in enumerate(cas):
            article = pub(f"finextra-{i}", titre, resume, source="Finextra AI")
            appels = []
            resultats, _ = traiter([article], lambda texte: score,
                                  lambda systeme, utilisateur: appels.append(utilisateur))
            self.assertEqual(resultats[0]["statut_pertinence"], "incertain")
            self.assertEqual(appels, [])
            self.assertIn("revue humaine", resultats[0]["justification_filtrage"])

    def test_finextra_ia_et_finance_reste_pertinent(self):
        article = pub("singapour", "Singapore central bank issues risk rules on banks' AI use",
                      "Banks in Singapore must seek an independent review of any forthcoming AI projects before implementation.",
                      source="Finextra AI")
        resultats, _ = traiter([article], lambda texte: 0.8622, ok_ia)
        self.assertEqual(resultats[0]["statut_pertinence"], "pertinent")
        self.assertEqual(resultats[0]["statut_analyse"], "effectuee")

    def test_faux_positif_credit_assignment(self):
        p = pub("r", "Credit assignment in deep reinforcement learning for robotics",
                "We propose a new credit assignment method for deep reinforcement learning "
                "agents controlling robotic arms in simulation, evaluated on robotics benchmarks.")
        self.assertEqual(a.filtrer(p, None, MOTS)["statut_pertinence"], "pertinent")
        self.assertEqual(a.filtrer(p, faux_classificateur, MOTS)["statut_pertinence"], "incertain")

    def test_rejet_et_priorite_sont_expliques(self):
        publication = pub("rj", "A gardening guide for home plants",
                          "This guide explains soil, watering, pruning and seasonal care for plants in a home garden.")
        resultat, _ = traiter([publication], lambda texte: 0.05, ok_ia)
        objet = resultat[0]
        self.assertEqual(objet["statut_pertinence"], "non_pertinent")
        self.assertEqual(objet["priorite"], "basse")
        self.assertIsInstance(objet["motif_rejet"], str)
        self.assertTrue(objet["motif_rejet"].strip())

        incertain, _ = traiter([pub("inc", "Bank AI assistant", resume=None)], lambda texte: 0.95, ok_ia)
        self.assertEqual(incertain[0]["priorite"], "haute")
        self.assertIsNone(incertain[0]["motif_rejet"])


class TestSortie(unittest.TestCase):
    def test_entree_preservee_et_schema_complet(self):
        originaux = [pub("a", "Bank fraud detection with deep learning")]
        copie = json.loads(json.dumps(originaux))
        res, journal = traiter(originaux, faux_classificateur, ok_ia)
        self.assertEqual(originaux, copie)                       # l'entrée n'est pas modifiée
        for champ in a.CHAMPS_ENTREE:
            self.assertEqual(res[0][champ], copie[0][champ])     # les 9 champs sont identiques
        for champ in a.CHAMPS_AJOUTES:
            self.assertIn(champ, res[0])
        self.assertEqual(journal["sorties_non_conformes"], [])

    def test_titre_seul_pas_d_appel_ia(self):
        appels = []

        def espion(s, u):
            appels.append(u)
            return ok_ia(s, u)
        res, _ = traiter(
            [pub("t", "Large language models for banking compliance", resume=None)],
            faux_classificateur, espion)
        self.assertEqual(appels, [])
        self.assertEqual(res[0]["statut_analyse"], "incertaine")
        self.assertEqual(res[0]["niveau_information"], "metadonnees_seules")

    def test_non_precise_devient_null_et_json_entoure_de_fences(self):
        def ia(s, u):
            return ('```json\n{"categorie":"BANQUE","technologie_ia":"non précisé",'
                    '"probleme_financier":"Fraude","innovation":null,"resultats":"",'
                    '"resume_fr":"Synthèse.","interet_financier":"N/A"}\n```')
        res, _ = traiter([pub("n", "Bank fraud detection with AI")],
                                        faux_classificateur, ia)
        self.assertIsNone(res[0]["technologie_ia"])
        self.assertIsNone(res[0]["interet_financier"])
        self.assertIsNone(res[0]["resultats"])
        self.assertEqual(res[0]["statut_analyse"], "effectuee")

    def test_categorie_hors_liste_refusee(self):
        def ia(s, u):
            return ('{"categorie":"FINANCE","technologie_ia":"x","probleme_financier":"y",'
                    '"innovation":null,"resultats":null,"resume_fr":"z","interet_financier":null}')
        res, _ = traiter([pub("c", "Bank fraud detection with AI")],
                                        faux_classificateur, ia)
        self.assertIsNone(res[0]["categorie"])
        self.assertEqual(res[0]["statut_analyse"], "incertaine")

    def test_chiffre_absent_de_la_source_signale(self):
        res, _ = traiter([pub("x", "[TEST-CHIFFRE] AI trading strategies")],
                                        faux_classificateur, ok_ia)
        self.assertEqual(res[0]["statut_analyse"], "incertaine")
        self.assertIn("99", res[0]["detail_analyse"])


class TestRobustesse(unittest.TestCase):
    def test_panne_isolee_n_arrete_pas_les_autres(self):
        def ia(s, u):
            if "PANNE" in u:
                raise RuntimeError("boom")
            return ok_ia(s, u)
        lot = [pub("1", "PANNE bank AI fraud"), pub("2", "Bank AI credit scoring")]
        res, _ = traiter(lot, faux_classificateur, ia)
        self.assertEqual([o["statut_analyse"] for o in res], ["en_echec", "effectuee"])

    def test_api_indisponible_apres_trois_echecs(self):
        appels = []

        def ia(s, u):
            appels.append(1)
            raise RuntimeError("401 clé invalide")
        lot = [pub(str(i), f"Bank AI fraud study number {i}") for i in range(5)]
        res, _ = traiter(lot, faux_classificateur, ia)
        self.assertEqual(len(appels), 3)                         # on cesse d'appeler après 3 échecs
        self.assertTrue(all(o["statut_analyse"] == "en_echec" for o in res))  # rien n'est perdu
        self.assertIn("non tentée", res[4]["detail_analyse"])

    def test_entrees_invalides_tracees(self):
        lot = ["texte", {"id": "z", "titre": "Sans url", "url": None}, pub("ok", "Bank AI fraud")]
        res, journal = traiter(lot, faux_classificateur, ok_ia)
        self.assertEqual(len(res), 1)
        self.assertEqual(len(journal["entrees_invalides"]), 2)

    def test_chargement_fichiers_vides_ou_invalides(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            (d / "vide.json").write_text("")
            (d / "casse.json").write_text("{nope")
            (d / "objet.json").write_text('{"a": 1}')
            (d / "liste.json").write_text("[]")
            for nom in ("vide.json", "casse.json", "objet.json", "absent.json"):
                with self.assertRaises(ValueError, msg=nom):
                    a.charger_publications(d / nom)
            self.assertEqual(a.charger_publications(d / "liste.json"), [])


class TestCle(unittest.TestCase):
    def test_nom_du_env_example_puis_repli(self):
        anciennes = {k: os.environ.pop(k, None) for k in ("IA_API_KEY", "GEMINI_API_KEY")}
        try:
            self.assertIsNone(a.cle_api())
            os.environ["GEMINI_API_KEY"] = "repli"
            self.assertEqual(a.cle_api(), "repli")
            os.environ["IA_API_KEY"] = "principale"
            self.assertEqual(a.cle_api(), "principale")
        finally:
            for k, v in anciennes.items():
                os.environ.pop(k, None)
                if v is not None:
                    os.environ[k] = v


class TestMotsCles(unittest.TestCase):
    def ecrire(self, d, contenu):
        chemin = Path(d) / "mots_cles.json"
        chemin.write_text(contenu if isinstance(contenu, str) else json.dumps(contenu), encoding="utf-8")
        return chemin

    def test_config_vide_ou_absente_ou_invalide_donne_les_listes_provisoires(self):
        with tempfile.TemporaryDirectory() as d:
            vide = self.ecrire(d, {"statut": "A_REMETTRE_EN_PLENIERE",
                                   "axes": {c: [] for c in a.CATEGORIES}})
            for chemin in (vide, Path(d) / "absent.json", self.ecrire(d, "{pas du json")):
                mots = a.charger_mots_cles(chemin)
                self.assertEqual(set(mots["origine"].values()), {"provisoire"})
                self.assertEqual(mots["termes_ia"], a.TERMES_IA)

    def test_config_remplie_est_utilisee_liste_par_liste(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = self.ecrire(d, {"axes": {"BANQUE": ["néobanque", " "], "CREDIT_MICROFINANCE": ["scoring"]},
                                     "termes_ia": ["agentic AI"]})
            mots = a.charger_mots_cles(chemin)
            self.assertEqual(mots["termes_finance"], ["néobanque", "scoring"])
            self.assertEqual(mots["termes_ia"], ["agentic AI"])
            self.assertEqual(mots["expressions"], a.EXPRESSIONS_SPECIALISEES)   # non renseignée : repli
            self.assertEqual(mots["origine"], {"termes_ia": "config", "termes_finance": "config",
                                               "expressions": "provisoire"})

    def test_les_mots_de_la_config_changent_le_filtrage(self):
        p = pub("k", "Neobank launches agentic AI", "A neobank introduces a new customer assistant for savers.")
        self.assertEqual(a.prefiltrer(p["titre"], p["resume_original"], MOTS)[0], "faible")
        with tempfile.TemporaryDirectory() as d:
            mots = a.charger_mots_cles(self.ecrire(d, {"axes": {"BANQUE": ["neobank"]},
                                                       "termes_ia": ["agentic ai"]}))
        self.assertEqual(a.prefiltrer(p["titre"], p["resume_original"], mots)[0], "fort")

    def test_le_journal_indique_l_origine_des_mots_cles(self):
        _, journal = traiter([pub("j", "Bank AI fraud")])
        self.assertEqual(journal["parametres"]["mots_cles"]["termes_ia"], "provisoire")

    def test_configuration_proposee_chargee_et_elargie(self):
        mots = a.charger_mots_cles()
        self.assertEqual(set(mots["origine"].values()), {"config"})
        self.assertGreaterEqual(len(mots["termes_ia"]), 100)
        self.assertGreaterEqual(len(mots["termes_finance"]), 350)
        self.assertGreaterEqual(len(mots["expressions"]), 100)


class TestSelectionEtSortie(unittest.TestCase):
    def test_selectionner_source_puis_limite(self):
        lot = [pub("1", "a", source="BRI / BIS"), pub("2", "b", source="arXiv"),
               pub("3", "c", source="arXiv"), "intrus"]
        self.assertEqual([p["id"] for p in a.selectionner(lot, "arxiv")], ["2", "3"])
        self.assertEqual([p["id"] for p in a.selectionner(lot, "arxiv", 1)], ["2"])
        self.assertEqual(len(a.selectionner(lot, None, 2)), 2)
        self.assertEqual(len(a.selectionner(lot)), 4)

    def test_le_fichier_officiel_est_reserve_a_une_execution_complete_reelle(self):
        self.assertEqual(a.choisir_sortie(None, False, None, None), (a.CHEMIN_SORTIE, False))
        for essai in ((None, True, None, None), (None, False, 5, None), (None, False, None, "arXiv")):
            self.assertEqual(a.choisir_sortie(*essai), (a.CHEMIN_SORTIE_ESSAI, True))
        self.assertEqual(a.choisir_sortie("x.json", True, 5, "arXiv"), (Path("x.json"), False))


class TestLigneDeCommande(unittest.TestCase):
    def test_limite_et_exemple_complet(self):
        exemple = RACINE / "examples" / "nouvelles_publications_exemple.json"
        if not exemple.exists():
            self.skipTest("exemple absent")
        with tempfile.TemporaryDirectory() as d:
            sortie = Path(d) / "out" / "res.json"
            cmd = [sys.executable, str(RACINE / "src" / "analyse.py"), "--entree", str(exemple),
                   "--sortie", str(sortie), "--ia-simulee", "--sans-classificateur", "--limite", "3"]
            # Sous Windows, un programme dont la sortie est capturée écrit en cp1252 :
            # on impose UTF-8 au sous-processus pour que la lecture soit fiable.
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(len(json.loads(sortie.read_text(encoding="utf-8"))), 3)
            self.assertTrue((sortie.parent / "journal_analyse.json").exists())

    def test_ia_simulee_sans_sortie_ne_touche_pas_au_fichier_officiel(self):
        exemple = RACINE / "examples" / "nouvelles_publications_exemple.json"
        if not exemple.exists():
            self.skipTest("exemple absent")
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            cmd = [sys.executable, str(RACINE / "src" / "analyse.py"), "--entree", str(exemple),
                   "--ia-simulee", "--sans-classificateur"]
            r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", env=env, cwd=d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((Path(d) / "data" / "analyse" / "essai_partiel_ou_simule.json").exists())
            self.assertFalse((Path(d) / "data" / "analyse" / "publications_analysees.json").exists())
            self.assertNotIn("mots-clés provisoires utilisés", r.stdout.lower())
            journal = json.loads((Path(d) / "data" / "analyse" / "journal_analyse.json").read_text(encoding="utf-8"))
            self.assertTrue(journal["parametres"]["ia_simulee"])
            self.assertEqual(set(journal["parametres"]["mots_cles"].values()), {"config"})


if __name__ == "__main__":
    unittest.main()
