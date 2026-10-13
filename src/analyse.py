"""
FINWATCH AI - Module 2 : filtrage et analyse des publications par IA.
Implémentation du module 2 selon les règles documentées du projet.

Lit    : data/collecte/nouvelles_publications.json   (produit par src/collecte.py)
Écrit  : data/analyse/publications_analysees.json    (publications enrichies)
         data/analyse/journal_analyse.json           (doublons écartés, entrées invalides,
                                                      paramètres utilisés)
Le fichier officiel n'est écrit QUE par une exécution complète avec la vraie IA. Un essai
(IA simulée, --limite ou --source) écrit dans data/analyse/essai_partiel_ou_simule.json,
sauf si --sortie est précisé.

Exécution (après la collecte) :
    python src/collecte.py
    python src/analyse.py

Options utiles pour les essais :
    --ia-simulee            fausse IA, aucun appel réseau (teste toute la chaîne)
    --sans-classificateur   saute le modèle zero-shot (règles Python seules)
    --entree / --sortie     autres chemins de fichiers
    --pause 4               secondes entre deux appels à l'API (quota gratuit limité)
    --limite 3              ne traite que les 3 premiers éléments (essai peu coûteux)
    --source arXiv          ne traite que les publications dont la source contient ce texte
    --verifier-api          teste la clé Gemini et liste les modèles disponibles, puis s'arrête

Secrets : la clé d'API se lit dans la variable d'environnement IA_API_KEY (nom prévu
dans .env.example ; GEMINI_API_KEY est aussi acceptée). En local, elle peut être écrite
dans le fichier .env (ignoré par Git, voir .gitignore) ; sur GitHub Actions, dans un
secret. Jamais dans le code.
"""

import argparse
import html
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

# Paramètres

RACINE = Path(__file__).resolve().parents[1]
CHEMIN_ENTREE = Path("data/collecte/nouvelles_publications.json")
CHEMIN_SORTIE = Path("data/analyse/publications_analysees.json")
CHEMIN_SORTIE_ESSAI = Path("data/analyse/essai_partiel_ou_simule.json")
CHEMIN_MOTS_CLES = RACINE / "config" / "mots_cles.json"

CHAMPS_ENTREE = ["id", "titre", "source", "url", "date_publication",
                 "date_collecte", "auteur", "resume_original", "type_document"]
CHAMPS_ESSENTIELS = ["id", "titre", "url"]

STATUTS_PERTINENCE = ("pertinent", "non_pertinent", "incertain")
STATUTS_ANALYSE = ("effectuee", "incertaine", "en_echec")
NIVEAUX_INFORMATION = ("resume_seul", "contenu_complet", "metadonnees_seules", "insuffisant")

CHAMPS_ANALYSE = ["technologie_ia", "probleme_financier", "innovation",
                  "resultats", "resume_fr", "interet_financier"]
CHAMPS_AJOUTES = (["statut_pertinence", "score_filtrage", "justification_filtrage",
                   "motif_rejet", "priorite", "categorie"] + CHAMPS_ANALYSE +
                  ["niveau_information", "statut_analyse", "detail_analyse"])
PRIORITES = ("haute", "moyenne", "basse")

CATEGORIES = {
    "MARCHES_FINANCIERS": "marchés financiers (trading, gestion de portefeuille, prévision de marché...)",
    "REGLEMENTATION_CONFORMITE": "réglementation et conformité (supervision, LCB-FT, RegTech, conformité...)",
    "CREDIT_MICROFINANCE": "crédit et microfinance (scoring, octroi de prêts, inclusion financière...)",
    "BANQUE": "banque et services financiers (services bancaires, paiements, assurance, fraude...)",
}

# Seuils PROVISOIRES du classificateur : à ajuster après l'évaluation humaine.
SEUIL_PERTINENT = 0.70
SEUIL_REJET = 0.30
MIN_CARACTERES_RESUME = 80      # en dessous : résumé jugé insuffisant
MAX_CARACTERES_CLASSIF = 1500   # le modèle zero-shot lit ~512 tokens
MAX_CARACTERES_LLM = 6000       # troncature pour le LLM (les données restent intactes)

MODELE_ZERO_SHOT = "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
ETIQUETTES = ["AI applications in finance", "Not about AI applications in finance"]
# Les noms de modèles Gemini changent vite : vérifier avec  python src/analyse.py --verifier-api
# puis, si besoin, écrire GEMINI_MODEL=nom_du_modele dans le fichier .env.
MODELE_GEMINI_DEFAUT = "gemini-3.5-flash"

# Listes de repli si la configuration est absente, vide ou incomplète.
# La recherche reconnaît les termes au début d'un mot, pas au milieu d'un mot.
TERMES_IA = [
    "artificial intelligence", "machine learning", "deep learning", "llm",
    "large language model", "nlp", "natural language processing",
    "generative ai", "genai", "neural network", "reinforcement learning",
    "ai agent", "intelligence artificielle", "apprentissage automatique",
    "apprentissage profond", "reseau de neurones", "ia generative",
]
IA_ACRONYMES = r"\b(AI|IA)\b"  # sensible à la casse, pour ne pas matcher "j'ai"

TERMES_FINANCE = [
    "bank", "banking", "banque", "credit", "loan", "lending", "pret bancaire",
    "trading", "fraud", "fraude", "compliance", "conformite", "payment",
    "paiement", "risk management", "financial market", "marche financier",
    "microfinance", "financ", "insurance", "assurance", "fintech",
    "asset management", "securities", "portfolio", "portefeuille",
    "investment", "investor", "investissement", "liquidity", "aml", "kyc",
    "regulatory", "reglementation", "supervisory", "central bank",
]
EXPRESSIONS_SPECIALISEES = [
    "credit scoring", "credit risk", "algorithmic trading", "regtech", "suptech",
    "anti money laundering", "money laundering", "financial forecasting",
    "fraud detection", "robo advisor", "high frequency trading",
    "portfolio optimization", "know your customer", "open banking",
    "blanchiment", "lcb ft",
]

def mots_cles_provisoires():
    """Listes intégrées au code, utilisées tant que la configuration de l'équipe est vide."""
    return {"termes_ia": TERMES_IA, "termes_finance": TERMES_FINANCE,
            "expressions": EXPRESSIONS_SPECIALISEES,
            "origine": {"termes_ia": "provisoire", "termes_finance": "provisoire",
                        "expressions": "provisoire"}}


def empreinte_config_mots_cles(chemin=CHEMIN_MOTS_CLES):
    """Retourne l'empreinte SHA-256 de la configuration, ou None si elle est illisible."""
    try:
        return hashlib.sha256(Path(chemin).read_bytes()).hexdigest()
    except OSError:
        return None


def charger_mots_cles(chemin=CHEMIN_MOTS_CLES):
    """Charge les quatre axes et les termes IA ; utilise les listes de repli si nécessaire."""
    try:
        config = json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        config = {}
    if not isinstance(config, dict):
        config = {}

    def textes(valeur):
        return [t.strip() for t in valeur if isinstance(t, str) and t.strip()] \
            if isinstance(valeur, list) else []

    axes = config.get("axes") if isinstance(config.get("axes"), dict) else {}
    finance = sorted({t for liste in axes.values() for t in textes(liste)})
    mots = mots_cles_provisoires()
    for cle, valeurs in (("termes_finance", finance),
                         ("termes_ia", textes(config.get("termes_ia"))),
                         ("expressions", textes(config.get("expressions_specialisees")))):
        if valeurs:
            mots[cle] = valeurs
            mots["origine"][cle] = "config"
    return mots


# Outils de texte


def nettoyer_texte(texte):
    """Supprime balises HTML, entités et espaces superflus (sans toucher aux champs d'origine)."""
    if not isinstance(texte, str):
        return ""
    texte = re.sub(r"<[^>]+>", " ", html.unescape(texte))
    return re.sub(r"\s+", " ", texte).strip()


def normaliser(texte):
    """Minuscules, sans accents ni ponctuation : 'Crédit !' -> 'credit'."""
    texte = unicodedata.normalize("NFD", texte or "")
    texte = "".join(c for c in texte if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", texte.lower()).strip()


def compter(texte_normalise, termes):
    """Nombre de termes différents trouvés (au début d'un mot)."""
    return sum(1 for t in termes
               if re.search(r"\b" + re.escape(normaliser(t)), texte_normalise))


# Chargement, validation et dédoublonnage


def charger_publications(chemin):
    """Lit la liste JSON. Lève ValueError si le fichier est absent, vide, invalide ou n'est pas une liste."""
    if not chemin.exists():
        raise ValueError(f"fichier d'entrée introuvable : {chemin}")
    contenu = chemin.read_text(encoding="utf-8").strip()
    if not contenu:
        raise ValueError(f"fichier d'entrée vide (0 octet) : {chemin}")
    try:
        donnees = json.loads(contenu)
    except json.JSONDecodeError as erreur:
        raise ValueError(f"JSON invalide dans {chemin} : {erreur}") from erreur
    if not isinstance(donnees, list):
        raise ValueError("le JSON d'entrée doit être une liste de publications")
    return donnees  # [] est valide : aucune nouveauté à analyser


def valider_publication(pub):
    """Renvoie la liste des problèmes essentiels (liste vide = publication exploitable)."""
    if not isinstance(pub, dict):
        return ["l'élément n'est pas un objet JSON"]
    return [f"champ essentiel absent ou invalide : {champ}"
            for champ in CHAMPS_ESSENTIELS
            if not isinstance(pub.get(champ), str) or not pub[champ].strip()]


def cle_titre(pub):
    """Titre normalisé + jour de publication (les dates ISO sont coupées à 10 caractères)."""
    return f"{normaliser(pub['titre'])}|{str(pub.get('date_publication') or '')[:10]}"


def dedoublonner(publications):
    """
    Retire les doublons du lot (on garde la PREMIÈRE occurrence) :
      1. même `id` ;
      2. même titre normalisé ET même jour de publication (même publication reprise
         par deux sources avec deux id différents).
    Renvoie (uniques, doublons) ; chaque doublon est tracé avec la raison.
    """
    par_id, par_titre = {}, {}
    uniques, doublons = [], []
    for pub in publications:
        if pub["id"] in par_id:
            garde, raison = par_id[pub["id"]], "même id"
        elif cle_titre(pub) in par_titre:
            garde, raison = par_titre[cle_titre(pub)], "même titre et même date de publication"
        else:
            par_id[pub["id"]] = pub["id"]
            par_titre[cle_titre(pub)] = pub["id"]
            uniques.append(pub)
            continue
        doublons.append({"id": pub["id"], "titre": pub["titre"],
                         "raison": raison, "doublon_de": garde})
    return uniques, doublons


# Filtrage de pertinence


def prefiltrer(titre, resume, mots=None):
    """Couche 1 (règles Python). Renvoie (signal, détails) ; signal = fort / faible / aucun."""
    mots = mots or mots_cles_provisoires()
    original = f"{titre} {resume}"
    texte = normaliser(original)
    ia = compter(texte, mots["termes_ia"]) + (1 if re.search(IA_ACRONYMES, original) else 0)
    finance = compter(texte, mots["termes_finance"])
    expressions = compter(texte, mots["expressions"])
    if ia > 0 and (finance > 0 or expressions > 0):
        signal = "fort"
    elif ia > 0 or finance > 0 or expressions > 0:
        signal = "faible"
    else:
        signal = "aucun"
    return signal, {"termes_ia": ia, "termes_finance": finance, "expressions": expressions}


def charger_classificateur():
    """
    Couche 2 : modèle zero-shot (Hugging Face). Renvoie une fonction texte -> score
    (probabilité relative de l'étiquette « AI applications in finance »), ou None si
    transformers/torch ne sont pas installés ou si le modèle est inaccessible.
    """
    try:
        from transformers import pipeline
        modele = pipeline("zero-shot-classification", model=MODELE_ZERO_SHOT)
    except Exception as erreur:
        print(f"[!] Classificateur zero-shot indisponible ({type(erreur).__name__}) : "
              "filtrage par règles seules.")
        return None

    def score(texte):
        resultat = modele(texte[:MAX_CARACTERES_CLASSIF], candidate_labels=ETIQUETTES)
        return round(dict(zip(resultat["labels"], resultat["scores"]))[ETIQUETTES[0]], 4)
    return score


def decider(signal, score, resume_suffisant):
    """
    Combine règles et score. Jamais de rejet silencieux : en cas de désaccord ou de
    doute, la publication reste 'incertain' et sera relue par un humain.
    """
    if score is None:  # modèle indisponible : règles seules
        if signal == "fort":
            return "pertinent"
        if signal == "aucun" and resume_suffisant:
            return "non_pertinent"
        return "incertain"
    if score >= SEUIL_PERTINENT and signal == "fort":
        return "pertinent"
    if score <= SEUIL_REJET and signal != "fort":
        return "non_pertinent"
    return "incertain"


def filtrer(pub, classificateur, mots=None):
    resume = nettoyer_texte(pub.get("resume_original"))
    signal, details = prefiltrer(pub["titre"], resume, mots)

    score = None
    if classificateur is not None:
        try:
            score = classificateur(f"{pub['titre']}. {resume}")
        except Exception as erreur:
            print(f"[!] Classificateur en échec pour {pub['id'][:12]} : {erreur}")

    statut = decider(signal, score, len(resume) >= MIN_CARACTERES_RESUME)
    justification = (f"Règles : signal {signal} (termes IA : {details['termes_ia']}, "
                     f"termes finance : {details['termes_finance']}, "
                     f"expressions : {details['expressions']}). ")
    justification += (f"Modèle zero-shot : score {score:.2f}." if score is not None
                      else "Modèle zero-shot non utilisé.")
    if statut == "incertain" and score is not None and score >= SEUIL_PERTINENT and signal != "fort":
        justification += " Score eleve sans indices conjoints IA et finance : revue humaine requise."
    motif_rejet = None
    if statut == "non_pertinent":
        if score is not None:
            motif_rejet = (
                f"Score zero-shot {score:.2f} inférieur ou égal au seuil de rejet "
                f"{SEUIL_REJET:.2f} ; signal lexical {signal}, sans signal fort combinant IA et finance."
            )
        else:
            motif_rejet = (
                "Aucun signal lexical combinant IA et finance détecté ; "
                "le résumé est suffisamment renseigné pour appliquer les règles seules."
            )
    return {"statut_pertinence": statut, "score_filtrage": score,
            "justification_filtrage": justification, "motif_rejet": motif_rejet}


def determiner_priorite(objet):
    """Priorité de revue : incertitudes/échecs en premier, analyses terminées ensuite."""
    pertinence = objet.get("statut_pertinence")
    if pertinence == "non_pertinent":
        return "basse"
    if pertinence == "incertain":
        return "haute"
    if pertinence == "pertinent" and objet.get("statut_analyse") == "effectuee":
        return "moyenne"
    return "haute"


# Analyse approfondie par LLM

PROMPT_SYSTEME = """Tu es un assistant de veille sur l'intelligence artificielle appliquée à la finance.
Tu analyses UNE publication à partir UNIQUEMENT du titre et du résumé fournis.

Règles strictes :
1. N'utilise aucune connaissance extérieure : tout doit venir du texte fourni.
2. Si une information est absente du texte, mets null (le mot JSON null,
   jamais une phrase comme "non précisé").
3. N'invente aucun chiffre, aucun nom, aucun résultat. "resultats" ne contient que
   des résultats explicitement cités dans le texte, sinon null.
4. Reste fidèle au texte. "interet_financier" reste prudent (conditionnel).
5. Classe la publication dans UNE de ces catégories (code exact) :
{categories}
   Si aucune ne convient clairement, mets null.
6. Rédige en français. "resume_fr" : 2 à 3 phrases, 80 mots maximum.
7. Réponds UNIQUEMENT par un objet JSON valide, sans texte autour, avec exactement
   ces clés : categorie, technologie_ia, probleme_financier, innovation, resultats,
   resume_fr, interet_financier.""".format(
    categories="\n".join(f"   - {code} : {desc}" for code, desc in CATEGORIES.items()))


def niveau_information(pub):
    """Quelle matière documentaire avons-nous ? (jamais d'analyse détaillée sur un titre seul)."""
    resume = nettoyer_texte(pub.get("resume_original"))
    if len(resume) >= MIN_CARACTERES_RESUME:
        return "resume_seul"
    if len(pub["titre"].strip()) >= 15:
        return "metadonnees_seules"
    return "insuffisant"


def construire_prompt(pub, resume, niveau):
    return (f"Titre : {pub['titre'].strip()}\n"
            f"Source : {pub.get('source')}\n"
            f"Date de publication : {pub.get('date_publication')}\n"
            f"Niveau d'information : {niveau}\n"
            f"Résumé : {resume[:MAX_CARACTERES_LLM] or 'null'}")


def charger_env():
    """Charge le fichier .env (s'il existe et si python-dotenv est installé)."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def nom_modele():
    """Modèle Gemini : variable GEMINI_MODEL (lue au moment de l'appel, donc après le .env)."""
    return os.environ.get("GEMINI_MODEL") or MODELE_GEMINI_DEFAUT


def cle_api():
    """Clé d'API de l'IA : IA_API_KEY (nom du .env.example), sinon GEMINI_API_KEY."""
    return os.environ.get("IA_API_KEY") or os.environ.get("GEMINI_API_KEY")


_client_gemini = None


def appeler_gemini(systeme, utilisateur):
    """Appelle l'API Gemini (SDK google-genai) et renvoie le texte brut de la réponse."""
    global _client_gemini
    from google import genai
    from google.genai import types

    if _client_gemini is None:
        cle = cle_api()
        if not cle:
            raise RuntimeError("clé d'API absente (variable IA_API_KEY)")
        # Le SDK ne doit pas ajouter ses propres relances aux notres.
        _client_gemini = genai.Client(
            api_key=cle,
            http_options=types.HttpOptions(
                timeout=30000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )

    for tentative in range(1, 3):
        try:
            reponse = _client_gemini.models.generate_content(
                model=nom_modele(),
                contents=utilisateur,
                config=types.GenerateContentConfig(
                    system_instruction=systeme,
                    response_mime_type="application/json",
                    temperature=0.1,
                ),
            )
            return reponse.text
        except Exception as erreur:
            code = getattr(erreur, "code", None)
            temporaire = (code in (408, 429, 500, 502, 503, 504)
                          or any(c in str(erreur) for c in
                                 ("Timeout", "ConnectError", "UNAVAILABLE", "RESOURCE_EXHAUSTED")))
            if not temporaire or tentative == 2:
                raise
            attente = 5
            print(f"[!] Gemini indisponible temporairement (tentative {tentative}/2) : pause de {attente} s")
            time.sleep(attente)


def verifier_api():
    """Teste la clé et le modèle Gemini sans toucher aux données. Renvoie 0 si tout va bien."""
    if not cle_api():
        print("[ERREUR] IA_API_KEY absente de l'environnement et du fichier .env.")
        return 2
    print(f"Clé trouvée. Modèle configuré : {nom_modele()}")
    try:
        from google import genai
        client = genai.Client(api_key=cle_api())
        print("\nModèles Gemini disponibles avec cette clé (génération de texte) :")
        trouves = []
        for modele in client.models.list():
            actions = getattr(modele, "supported_actions", None) or []
            nom = (modele.name or "").replace("models/", "")
            if "gemini" in nom and (not actions or "generateContent" in actions):
                trouves.append(nom)
        for nom in sorted(trouves):
            print("  -", nom + ("   <-- modèle configuré" if nom == nom_modele() else ""))
        if nom_modele() not in trouves:
            print(f"\n[!] '{nom_modele()}' n'est pas dans la liste : choisis un nom ci-dessus et "
                  "écris-le dans .env (GEMINI_MODEL=...).")
    except Exception as erreur:
        print(f"[ERREUR] Impossible de lister les modèles : {type(erreur).__name__} : {erreur}")
        return 3

    print("\nEssai d'un appel minimal...")
    try:
        reponse = appeler_gemini("Réponds uniquement par un objet JSON.", 'Renvoie {"ok": true}')
        print("Réponse reçue :", (reponse or "")[:200])
        print("\n[OK] L'API Gemini fonctionne avec ce modèle.")
        return 0
    except Exception as erreur:
        print(f"[ERREUR] Appel impossible : {type(erreur).__name__} : {erreur}")
        return 4


# Mots-clés utilisés SEULEMENT par la fausse IA pour proposer une catégorie.
_MOTS_SIMULATION = {
    "CREDIT_MICROFINANCE": ["credit", "loan", "microfinance", "scoring"],
    "REGLEMENTATION_CONFORMITE": ["compliance", "regulat", "supervis", "aml"],
    "MARCHES_FINANCIERS": ["trading", "market", "portfolio"],
    "BANQUE": ["bank", "fraud", "payment"],
}


def appeler_ia_simulee(systeme, utilisateur):
    """Fausse IA pour tester la chaîne sans réseau. Les déclencheurs [TEST-...] simulent des incidents."""
    if "[TEST-PANNE]" in utilisateur:
        raise RuntimeError("panne simulée de l'API")
    if "[TEST-JSON]" in utilisateur:
        return "Désolé, je ne peux pas répondre au format JSON."
    texte = normaliser(utilisateur)
    scores = {c: compter(texte, mots) for c, mots in _MOTS_SIMULATION.items()}
    categorie = max(scores, key=scores.get) if max(scores.values()) > 0 else None
    resultats = "Amélioration de 99 % (simulée)." if "[TEST-CHIFFRE]" in utilisateur else None
    return json.dumps({
        "categorie": categorie,
        "technologie_ia": "Technologie d'IA (simulée)",
        "probleme_financier": "Problème financier (simulé)",
        "innovation": None,
        "resultats": resultats,
        "resume_fr": "Synthèse de test (simulée).",
        "interet_financier": "Intérêt à confirmer (simulé).",
    }, ensure_ascii=False)


def extraire_json(brut):
    """Extrait l'objet JSON d'une réponse (tolère les ```json ... ``` autour)."""
    texte = re.sub(r"```(?:json)?", "", brut or "")
    debut, fin = texte.find("{"), texte.rfind("}")
    if debut == -1 or fin <= debut:
        raise ValueError("aucun objet JSON dans la réponse du modèle")
    donnees = json.loads(texte[debut:fin + 1])
    if not isinstance(donnees, dict):
        raise ValueError("la réponse JSON n'est pas un objet")
    return donnees


def _valeur_texte(valeur):
    """Le contrat interdit les chaînes du type 'non précisé' : elles deviennent null."""
    if not isinstance(valeur, str):
        return None
    if normaliser(valeur) in ("", "non precise", "non precisee", "n a", "null", "none"):
        return None
    return valeur.strip()


def _nombres(texte):
    return {m.replace(",", ".") for m in re.findall(r"\d+(?:[.,]\d+)?", texte or "")}


def analyser(pub, appeler, panne_api=False):
    """
    Analyse approfondie d'UNE publication pertinente.
    Renvoie (champs_analyse, panne_api_detectee).
    """
    champs = {c: None for c in CHAMPS_ANALYSE}
    champs.update({"categorie": None, "niveau_information": None,
                   "statut_analyse": None, "detail_analyse": None})

    resume = nettoyer_texte(pub.get("resume_original"))
    niveau = niveau_information(pub)
    champs["niveau_information"] = niveau

    if niveau in ("metadonnees_seules", "insuffisant"):
        champs["statut_analyse"] = "incertaine"
        champs["detail_analyse"] = ("Information insuffisante (titre seul) : analyse non lancée "
                                    "pour ne rien inventer.")
        return champs, False
    if panne_api:
        champs["statut_analyse"] = "en_echec"
        champs["detail_analyse"] = "API indisponible : analyse non tentée (échecs consécutifs)."
        return champs, True

    prompt = construire_prompt(pub, resume, niveau)
    try:
        brut = appeler(PROMPT_SYSTEME, prompt)
    except Exception as erreur:
        champs["statut_analyse"] = "en_echec"
        champs["detail_analyse"] = f"Appel à l'IA impossible : {type(erreur).__name__} : {erreur}"[:300]
        return champs, True

    try:
        donnees = extraire_json(brut)
    except Exception as erreur:
        champs["statut_analyse"] = "en_echec"
        champs["detail_analyse"] = f"Réponse du modèle inexploitable : {erreur}"[:300]
        return champs, False

    for cle in CHAMPS_ANALYSE:
        champs[cle] = _valeur_texte(donnees.get(cle))
    categorie = donnees.get("categorie")
    champs["categorie"] = categorie if categorie in CATEGORIES else None

    # Garde-fou : tout chiffre de la sortie doit figurer dans le texte fourni.
    sortie = " ".join(v for k, v in champs.items() if k in CHAMPS_ANALYSE and v)
    inventes = sorted(_nombres(sortie) - _nombres(prompt))
    if inventes:
        champs["statut_analyse"] = "incertaine"
        champs["detail_analyse"] = f"Chiffres absents de la source : {inventes}. À vérifier."
    elif champs["categorie"] is None or (champs["technologie_ia"] is None
                                          and champs["probleme_financier"] is None):
        champs["statut_analyse"] = "incertaine"
        champs["detail_analyse"] = "Catégorie ou éléments essentiels non identifiés."
    else:
        champs["statut_analyse"] = "effectuee"
    return champs, False


# Assemblage, validation et export


def champs_vides():
    return {c: None for c in CHAMPS_AJOUTES}


def verifier_sortie(objet, original):
    """Renvoie la liste des écarts au schéma (liste vide = conforme)."""
    erreurs = [f"champ d'entrée modifié : {c}" for c in CHAMPS_ENTREE
               if c in original and objet.get(c) != original[c]]
    erreurs += [f"champ ajouté manquant : {c}" for c in CHAMPS_AJOUTES if c not in objet]
    if erreurs:
        return erreurs
    if objet["statut_pertinence"] not in STATUTS_PERTINENCE:
        erreurs.append(f"statut_pertinence invalide : {objet['statut_pertinence']}")
    if objet["categorie"] is not None and objet["categorie"] not in CATEGORIES:
        erreurs.append(f"categorie invalide : {objet['categorie']}")
    if objet["statut_analyse"] is not None and objet["statut_analyse"] not in STATUTS_ANALYSE:
        erreurs.append(f"statut_analyse invalide : {objet['statut_analyse']}")
    if objet["niveau_information"] is not None and objet["niveau_information"] not in NIVEAUX_INFORMATION:
        erreurs.append(f"niveau_information invalide : {objet['niveau_information']}")
    if objet["priorite"] not in PRIORITES:
        erreurs.append(f"priorite invalide : {objet['priorite']}")
    if objet["statut_pertinence"] == "non_pertinent":
        if not isinstance(objet["motif_rejet"], str) or not objet["motif_rejet"].strip():
            erreurs.append("motif_rejet doit expliquer un rejet non_pertinent")
    elif objet["motif_rejet"] is not None:
        erreurs.append("motif_rejet doit être null hors statut non_pertinent")
    if objet["score_filtrage"] is not None and not isinstance(objet["score_filtrage"], (float, int)):
        erreurs.append("score_filtrage doit être un nombre ou null")
    try:
        json.dumps(objet)
    except TypeError as erreur:
        erreurs.append(f"objet non sérialisable en JSON : {erreur}")
    return erreurs


def traiter_une(pub, classificateur, appeler, panne_api, mots=None):
    """Enrichit UNE publication : copie intacte de l'entrée + champs ajoutés."""
    objet = {**pub, **champs_vides(), **filtrer(pub, classificateur, mots)}
    if objet["statut_pertinence"] == "pertinent":
        analyse, panne_api = analyser(pub, appeler, panne_api)
        objet.update(analyse)
    objet["priorite"] = determiner_priorite(objet)
    return objet, panne_api


def traiter_publications(publications, classificateur=None, appeler=appeler_gemini,
                         pause=0.0, mots_cles=None, progression=None, precedents=None):
    """
    Fonction principale (utilisable aussi depuis un autre script) :
    liste du collecteur -> (liste enrichie, journal).
    Une erreur sur une publication n'arrête jamais les autres.
    """
    mots = mots_cles or charger_mots_cles()
    journal = {
        "entrees_invalides": [],
        "doublons_ecartes": [],
        "sorties_non_conformes": [],
        "parametres": {
            "mots_cles": mots["origine"],
            "nombre_termes_mots_cles": {
                "termes_ia": len(mots["termes_ia"]),
                "termes_finance": len(mots["termes_finance"]),
                "expressions_specialisees": len(mots["expressions"]),
            },
        },
    }

    valides = []
    for position, pub in enumerate(publications):
        erreurs = valider_publication(pub)
        if erreurs:
            journal["entrees_invalides"].append(
                {"position": position, "erreurs": erreurs, "contenu": pub})
        else:
            valides.append(pub)

    uniques, journal["doublons_ecartes"] = dedoublonner(valides)

    resultats, echecs_api_consecutifs = [], 0
    precedents = precedents or {}
    for pub in uniques:
        deja = precedents.get(pub["id"])
        if (deja is not None and deja.get("statut_analyse") == "effectuee"
                and all(deja.get(c) == pub.get(c) for c in CHAMPS_ENTREE)
                and not verifier_sortie(deja, pub)):
            resultat = deja
            resultats.append(resultat)
            if progression:
                progression(resultats, journal)
            continue
        try:
            objet, panne = traiter_une(pub, classificateur, appeler, echecs_api_consecutifs >= 3, mots)
        except Exception as erreur:  # filet de sécurité : jamais de perte silencieuse
            objet = {**pub, **champs_vides(), "statut_pertinence": "incertain",
                     "justification_filtrage": f"Erreur interne : {type(erreur).__name__} : {erreur}"[:300],
                     "statut_analyse": "en_echec", "detail_analyse": "Traitement interrompu pour cette publication."}
            objet["priorite"] = determiner_priorite(objet)
            panne = False

        # Compte des pannes d'API consécutives (3 d'affilée : on cesse d'appeler l'API).
        if objet.get("statut_analyse") is not None and objet.get("niveau_information") == "resume_seul":
            echecs_api_consecutifs = echecs_api_consecutifs + 1 if panne else 0
            if pause:
                time.sleep(pause)

        erreurs = verifier_sortie(objet, pub)
        if erreurs:
            journal["sorties_non_conformes"].append({"id": pub["id"], "erreurs": erreurs})
        resultats.append(objet)
        if progression:
            progression(resultats, journal)
    return resultats, journal


def exporter(chemin, donnees):
    """Écriture atomique (fichier temporaire puis remplacement), comme collecte.py."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    temporaire = chemin.with_suffix(chemin.suffix + ".tmp")
    temporaire.write_text(json.dumps(donnees, ensure_ascii=False, indent=4), encoding="utf-8")
    temporaire.replace(chemin)


def afficher_bilan(recus, resultats, journal):
    def compte(champ, valeur):
        return sum(1 for o in resultats if o.get(champ) == valeur)
    print("\n" + "=" * 55)
    print("ANALYSE FINWATCH AI TERMINÉE")
    print(f"Éléments reçus            : {recus}")
    print(f"Entrées invalides         : {len(journal['entrees_invalides'])}")
    print(f"Doublons écartés          : {len(journal['doublons_ecartes'])}")
    print(f"Publications traitées     : {len(resultats)}")
    for statut in STATUTS_PERTINENCE:
        print(f"  - {statut:<14}      : {compte('statut_pertinence', statut)}")
    for statut in STATUTS_ANALYSE:
        print(f"  analyse {statut:<10}    : {compte('statut_analyse', statut)}")
    if journal["sorties_non_conformes"]:
        print(f"[!] Sorties non conformes : {len(journal['sorties_non_conformes'])} (voir le journal)")


# Lancement


def selectionner(publications, source=None, limite=None):
    """Applique --source puis --limite (même logique pour le module et pour le contrôle)."""
    if source:
        publications = [p for p in publications
                        if isinstance(p, dict) and source.lower() in str(p.get("source", "")).lower()]
    if limite is not None:
        publications = publications[:max(limite, 0)]
    return publications


def choisir_sortie(sortie_demandee, ia_simulee, limite, source):
    """Le fichier officiel n'est écrit que par une exécution complète avec la vraie IA."""
    if sortie_demandee:
        return Path(sortie_demandee), False
    if ia_simulee or limite is not None or source:
        return CHEMIN_SORTIE_ESSAI, True
    return CHEMIN_SORTIE, False


def main():
    parser = argparse.ArgumentParser(description="FINWATCH AI - filtrage et analyse IA")
    parser.add_argument("--entree", default=str(CHEMIN_ENTREE))
    parser.add_argument("--sortie", default=None,
                        help="par défaut : fichier officiel (exécution complète) ou fichier d'essai")
    parser.add_argument("--ia-simulee", action="store_true")
    parser.add_argument("--sans-classificateur", action="store_true")
    parser.add_argument("--pause", type=float, default=4.0)
    parser.add_argument("--limite", type=int, default=None,
                        help="ne traiter que les N premiers éléments")
    parser.add_argument("--source", default=None,
                        help="ne traiter que les publications dont la source contient ce texte")
    parser.add_argument("--verifier-api", action="store_true")
    parser.add_argument("--reprendre", action="store_true",
                        help="reutiliser les analyses terminees du fichier de sortie et reprendre le lot")
    args = parser.parse_args()

    if args.verifier_api:
        charger_env()
        sys.exit(verifier_api())

    entree = Path(args.entree)
    sortie, est_essai = choisir_sortie(args.sortie, args.ia_simulee, args.limite, args.source)
    journal_chemin = sortie.parent / "journal_analyse.json"

    try:
        publications = charger_publications(entree)
    except ValueError as erreur:
        print(f"[ERREUR] {erreur}")
        sys.exit(1)  # on ne touche pas aux anciens résultats

    if args.source or args.limite is not None:
        publications = selectionner(publications, args.source, args.limite)
        print(f"[SÉLECTION] {len(publications)} élément(s) traité(s) "
              f"(source : {args.source or 'toutes'}, limite : {args.limite}).")

    charger_env()
    if not args.ia_simulee and not cle_api():
        print("[ERREUR] IA_API_KEY absente de l'environnement et du fichier .env "
              "(ou utiliser --ia-simulee pour tester).")
        sys.exit(2)

    mots = charger_mots_cles()
    if "provisoire" in mots["origine"].values():
        print("[!] Mots-clés PROVISOIRES utilisés pour : "
              + ", ".join(k for k, v in mots["origine"].items() if v == "provisoire")
              + " (config/mots_cles.json non rempli ou incomplet).")

    classificateur = None if args.sans_classificateur else charger_classificateur()
    appeler = appeler_ia_simulee if args.ia_simulee else appeler_gemini
    if args.ia_simulee:
        print("[MODE TEST] IA simulée : aucun appel réseau, analyses factices.")
    if est_essai and not args.sortie:
        print(f"[ESSAI] Résultat écrit dans {sortie} : le fichier officiel n'est pas modifié.")

    precedents = {}
    if args.reprendre and sortie.exists():
        try:
            anciens = charger_publications(sortie)
            precedents = {p["id"]: p for p in anciens
                          if isinstance(p, dict) and isinstance(p.get("id"), str)}
            print(f"[REPRISE] {len(precedents)} anciennes publications disponibles.")
        except ValueError as erreur:
            print(f"[ERREUR] Reprise impossible : {erreur}")
            sys.exit(1)

    parametres_execution = {
        "ia_simulee": args.ia_simulee,
        "classificateur": MODELE_ZERO_SHOT if classificateur else None,
        "modele_llm": "simulee" if args.ia_simulee else nom_modele(),
        "seuil_pertinent": SEUIL_PERTINENT, "seuil_rejet": SEUIL_REJET,
        "source": args.source, "limite": args.limite,
        "empreinte_mots_cles_sha256": empreinte_config_mots_cles(),
    }

    def sauvegarder_progression(partiel, etat_journal):
        etat_journal["parametres"].update(parametres_execution)
        exporter(sortie, partiel)
        exporter(journal_chemin, etat_journal)

    try:
        resultats, journal = traiter_publications(
            publications, classificateur, appeler,
            pause=0.0 if args.ia_simulee else args.pause, mots_cles=mots,
            progression=sauvegarder_progression, precedents=precedents)
    except KeyboardInterrupt:
        print("\n[INTERRUPTION] Les publications deja traitees sont sauvegardees ; relancer avec --reprendre.")
        sys.exit(130)
    journal["parametres"].update(parametres_execution)

    exporter(sortie, resultats)
    exporter(journal_chemin, journal)
    afficher_bilan(len(publications), resultats, journal)
    print(f"Résultats : {sortie.resolve()}")
    print(f"Journal   : {journal_chemin.resolve()}")


if __name__ == "__main__":
    main()
