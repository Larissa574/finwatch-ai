# FINWATCH AI

**Système intelligent de veille technologique sur les innovations de l'intelligence artificielle dans le secteur financier.**

Projet universitaire développé par une équipe de quatre personnes. FINWATCH AI collecte des publications, détecte celles qui concernent l'IA appliquée à la finance, génère des synthèses en français, les enregistre dans Google Sheets et permet leur **validation humaine avant diffusion** aux abonnés.

> **État :** prototype fonctionnel avec collecte/analyse planifiées et diffusion hebdomadaire. La qualité scientifique des classifications et des synthèses nécessite encore une évaluation sur un corpus annoté. N'utilisez pas ce système comme conseil financier.

## Sommaire

- [Fonctionnement](#fonctionnement)
- [Sources et thèmes](#sources-et-thèmes)
- [Prérequis et installation](#prérequis-et-installation)
- [Configuration de Google Sheets et Gemini](#configuration-de-google-sheets-et-gemini)
- [Utilisation en local](#utilisation-en-local)
- [Validation des articles et bulletins](#validation-des-articles-et-bulletins)
- [Automatisation GitHub Actions](#automatisation-github-actions)
- [Structure du dépôt](#structure-du-dépôt)
- [Tests et limites](#tests-et-limites)

## Fonctionnement

```text
BRI/BIS ─┐
BCE ─────┤
EBA ─────┼──► Collecte RSS/API (Python) ──► JSON / déduplication
Finextra ┤                                      │
arXiv ───┘                                      ▼
                               Filtrage lexical + mDeBERTa (zero-shot)
                                                │
                                                ▼
                                  Gemini : synthèse structurée
                                                │
                                                ▼
                                 Google Sheets : Publications
                                                │
                                     Validation humaine
                                                │
                                                ▼
                         Newsletter HTML + abonnés + journal d'envois
```

1. `src/collecte.py` interroge quatre flux RSS et l'API arXiv, nettoie les URL, harmonise les dates et produit des fichiers JSON.
2. `src/importer_stockage.py` centralise les données brutes dans Google Sheets, sans réinsérer les identifiants déjà présents.
3. `src/analyse.py` combine des mots-clés thématiques et le modèle **mDeBERTa** pour juger de la pertinence ; Gemini enrichit les publications retenues quand les informations disponibles sont suffisantes.
4. `src/importer_analyses.py` importe uniquement les analyses pertinentes et terminées. Les lignes déjà validées ou diffusées sont protégées.
5. Une personne examine les synthèses et renseigne la validation dans Google Sheets.
6. `src/diffusion_automatique.py` prépare le bulletin, sélectionne les abonnés consentants et actifs, ajoute un lien de désinscription et journalise les envois par campagne et destinataire.

**Important :** le code ne garantit pas la véracité des informations résumées. La vérification humaine est obligatoire avant toute diffusion.

## Sources et thèmes

| Source | Mode | Utilité |
|---|---|---|
| BRI / BIS — Banque des règlements internationaux | RSS | Supervision, stabilité financière, recherche bancaire |
| BCE — Banque centrale européenne (supervision) | RSS | Supervision bancaire et risques |
| EBA — Autorité bancaire européenne | RSS | Réglementation et conformité |
| Finextra AI | RSS | Actualités et usages professionnels de la fintech et de l'IA |
| arXiv | API Atom | Prépublications scientifiques, non nécessairement évaluées par les pairs |

**Axes de veille :** `MARCHES_FINANCIERS`, `REGLEMENTATION_CONFORMITE`, `CREDIT_MICROFINANCE`, `BANQUE`.

Les termes français/anglais et expressions spécialisées se trouvent dans `config/mots_cles.json`. La collecte arXiv applique une requête combinant des concepts d'IA et de finance. Les quatre RSS sont filtrés après récupération.

## Prérequis et installation

- **Python 3.11 recommandé** (version des workflows principaux).
- Git et un accès Internet pour la collecte.
- Pour le pipeline complet : accès Google Sheets via **compte de service**, clé API Gemini, et accès SMTP pour la diffusion.
- Le modèle mDeBERTa nécessite `transformers`, `torch` et son téléchargement initial.

```bash
git clone https://github.com/Larissa574/finwatch-ai.git
cd finwatch-ai
python -m venv .venv
```

Activation : Linux/macOS `source .venv/bin/activate` ; Windows PowerShell `.venv\Scripts\Activate.ps1`.

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements-ia.txt
python -m pip install sentencepiece
python -m pytest tests -q
```

Pour exécuter uniquement les tests ou la collecte, `requirements.txt` suffit. Les modèles IA peuvent demander un téléchargement volumineux.

## Configuration de Google Sheets et Gemini

1. Copier `.env.example` vers `.env`, sans jamais versionner `.env`.
2. Créer un compte de service Google ayant accès à l'API Google Sheets ; partager le classeur avec son adresse.
3. Renseigner `GOOGLE_SHEET_ID` et **soit** `GOOGLE_CREDENTIALS_JSON` (JSON complet) **soit**, en local, déposer la clé dans `secrets/finwatch-sheets.json`.
4. Renseigner `IA_API_KEY` et, si nécessaire, `GEMINI_MODEL`. Vérifier l'accès aux modèles disponibles avec `python src/analyse.py --verifier-api`.
5. En exécution locale, charger les variables du fichier `.env` dans l'environnement du terminal si votre commande ne les charge pas automatiquement.

Le classeur attendu, intitulé habituellement `FINWATCH_AI_BDD`, comporte ces onglets avec les en-têtes exacts : **Publications**, **Sources**, **Journal de collecte**, **Abonnes**, **Journal envois**. Le code vérifie la structure des en-têtes ; ne pas les renommer.

Dans `Publications`, le schéma comporte **21 colonnes** : les 9 champs collectés, les résultats de synthèse, les champs de validation et les informations d'envoi. Le programme n'initialise pas automatiquement l'intégralité d'un classeur vierge : préparez les onglets et leurs en-têtes avant les premiers imports.

### Secrets GitHub Actions

Dans **Settings → Secrets and variables → Actions**, créer les secrets :

| Secret | Rôle |
|---|---|
| `GOOGLE_SHEET_ID` | Identifiant du classeur |
| `GOOGLE_CREDENTIALS_JSON` | JSON du compte de service |
| `IA_API_KEY` | Clé Gemini |
| `SMTP_USER`, `SMTP_PASSWORD` | Authentification SMTP |
| `FINWATCH_WEBAPP_URL` | URL HTTPS de l'application Apps Script de désinscription |
| `FINWATCH_HMAC_SECRET` | Clé secrète pour signer les liens de désinscription |
| `FINWATCH_TEST_EMAIL` | Adresse autorisée pour le test privé |

Variables de dépôt utiles : `GEMINI_MODEL` (si besoin) et `FINWATCH_AUTORISER_ENVOI`.

**Sécurité :** ne jamais placer une clé Google, Gemini, un mot de passe SMTP ou `FINWATCH_HMAC_SECRET` dans Git. Le fichier `.gitignore` exclut déjà `.env`, `secrets/` et `data/`.

## Utilisation en local

Exécuter les commandes depuis la **racine du dépôt**, dans l'ordre.

### 1. Collecter les publications

```bash
python src/collecte.py
```

Fichiers créés : `data/collecte/publications.json` (historique local du cycle) et `data/collecte/nouvelles_publications.json` (nouveautés du cycle).

### 2. Enregistrer les publications dans Google Sheets

```bash
python src/importer_stockage.py
```

### 3. Analyser les nouvelles publications

```bash
python src/analyse.py --entree data/collecte/nouvelles_publications.json --sortie data/analyse/publications_analysees.json
```

Cette étape peut télécharger mDeBERTa et utiliser l'API Gemini. Pour **tester sans service IA réel** :

```bash
python src/analyse.py --entree examples/nouvelles_publications_exemple.json --ia-simulee --sans-classificateur
```

Le mode simulé n'est **pas** une évaluation de la qualité de l'IA.

### 4. Importer les synthèses

```bash
python src/importer_analyses.py
```

Seules les analyses `pertinent` + `effectuee` sont importées. Les validations ne sont jamais effectuées automatiquement.

### 5. Vérifier les publications avant diffusion

Dans l'onglet `Publications`, vérifier la source et la synthèse. Pour autoriser une publication, renseigner **ensemble** :

- `statut_validation = VALIDE`
- `valide_par = <identifiant du validateur>`
- `date_validation = <date de validation>`

L'article doit avoir un `resume_ia` exploitable et un `statut_envoi` vide ou `NON_ENVOYE`. Pour écarter une publication, utiliser `A_VALIDER` ou `REJETE`. Ne pas supprimer les lignes : conserver l'historique.

### 6. Simuler un bulletin (aucun email)

```bash
python src/diffusion_automatique.py
```

Le script indique la campagne, le nombre d'articles éligibles et les destinataires restants ; **aucun mail n'est envoyé sans `--send`**.

### 7. Diffuser, uniquement après autorisation

**Méthode recommandée : GitHub Actions**, présentée ci-dessous. En local, la commande `python src/diffusion_automatique.py --send` ne peut envoyer au public que si `FINWATCH_AUTORISER_ENVOI=OUI` et si tous les paramètres SMTP/Google sont configurés.

Le système conserve un **journal par couple campagne + email** dans `Journal envois`, pour ne pas renvoyer une campagne enregistrée comme envoyée au même destinataire. Il ne marque **pas automatiquement toutes les publications `ENVOYE`**, car une campagne pourrait n'avoir été distribuée qu'en partie.

## Automatisation GitHub Actions

Depuis l'onglet **Actions** du dépôt :

| Workflow | Déclenchement | Comportement |
|---|---|---|
| `veille-automatique.yml` | Quotidien, 06:00 UTC (07:00 au Bénin) ; aussi manuel | Tests, collecte, stockage, analyse des nouveautés et import |
| `diffusion-hebdomadaire.yml` | Samedi, 11:00 UTC (12:00 au Bénin) ; aussi manuel | Simulation par défaut ; envoi public seulement si explicitement autorisé |
| `collecte.yml` | Manuel | Diagnostic de collecte sans Gemini ni email |
| `tests.yml` | Manuel | Exécution de la suite de tests |

Les exécutions GitHub Actions planifiées peuvent commencer avec du retard.

### Tester la newsletter sur une seule adresse

1. Vérifier que `FINWATCH_TEST_EMAIL` correspond à une adresse **ACTIF** et consentante dans `Abonnes`.
2. Préparer au moins une publication validée et éligible.
3. Ouvrir **Actions → FINWATCH AI - diffusion abonnés → Run workflow**.
4. Cocher **Envoyer uniquement à FINWATCH_TEST_EMAIL**.
5. Saisir une valeur inédite pour `campagne_test` à chaque nouveau test, puis lancer.

Le mode privé cible uniquement cette adresse, même si l'autorisation générale d'envoi vaut `NON`. **Ne décochez pas** cette option en pensant lancer un test privé. Sans cette option, le workflow suit le mode de diffusion publique/simulation selon `FINWATCH_AUTORISER_ENVOI`.

### Activer les envois réels aux abonnés

La variable GitHub `FINWATCH_AUTORISER_ENVOI` vaut **`OUI` uniquement après vérification** des articles, abonnements, consentements, paramètres SMTP et lien de désinscription. Toute autre valeur laisse le workflow habituel en simulation. Le code limite également le nombre de destinataires par campagne.

Le lien de désinscription repose sur une **application Google Apps Script** déployée séparément : la configuration de `FINWATCH_WEBAPP_URL` et la cohérence de la clé HMAC sont nécessaires au fonctionnement des désinscriptions.

## Structure du dépôt

```text
.github/workflows/               Automatisations et workflows de diagnostic
config/mots_cles.json             Dictionnaire bilingue et 4 axes de veille
config/sources.json               Inventaire des 5 sources actives
src/collecte.py                   Flux RSS, API arXiv, normalisation, déduplication
src/analyse.py                    Filtrage lexical, mDeBERTa, synthèse Gemini
src/importer_stockage.py          Import de publications brutes dans Google Sheets
src/importer_analyses.py          Import des synthèses validables
src/stockage.py                   Accès et schéma du classeur
src/diffusion.py                  Construction du bulletin HTML et envoi SMTP
src/diffusion_automatique.py      Abonnés, consentement, journal et désinscription
src/run_diffusion.py              Point d'entrée historique de diffusion
src/main.py                       Point d'entrée historique collecte + stockage
tests/                            Tests du projet
examples/                         Jeux d'exemples pour essais
requirements.txt                  Dépendances de base
requirements-ia.txt               Dépendances du classificateur
.env.example                      Modèle de configuration sans secrets
```

**Attention :** `src/main.py` n'exécute que la collecte et le stockage ; ce n'est pas le pipeline complet. Utiliser les commandes ci-dessus ou `veille-automatique.yml`.

## Tests et limites

```bash
python -m pytest tests -q
```

Limites connues :

- Cinq sources seulement, avec une couverture institutionnelle principalement européenne.
- Prépublications arXiv non systématiquement validées par les pairs.
- Score zero-shot de mDeBERTa et seuils `0.70` / `0.30` non étalonnés scientifiquement.
- Erreurs possibles des modèles génératifs : contrôler toutes les synthèses.
- Dépendance aux API, au réseau et aux quotas Google Sheets / Gemini.
- Historique local `data/` non conservé entre les exécutions GitHub Actions ; la déduplication persistante repose sur Google Sheets.
- Une campagne partiellement envoyée exige une vérification du journal avant toute nouvelle diffusion.



Le projet met en pratique une chaîne de **veille technologique assistée par IA**, où l'automatisation facilite le suivi de l'information sans remplacer l'analyse critique et la validation humaine.
