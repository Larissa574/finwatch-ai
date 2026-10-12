# Guide d'exécution — Module 2 (filtrage et analyse IA)

Toutes les commandes se lancent dans **PowerShell**, depuis la racine du dépôt :
`C:\Users\PC\Desktop\veille\finwatch-ai`

Chaque étape donne : la commande, le résultat attendu, que faire si ça échoue, et le lien avec le cahier des charges (CDC).

**Règles à ne jamais enfreindre (pour rester conforme au CDC)**
- Les 9 champs d'entrée ne sont jamais modifiés (CDC §2.3).
- Le module ne refait aucune requête RSS/API : il lit `nouvelles_publications.json` (CDC §5).
- Une information absente vaut `null`, jamais « non précisé » ni une valeur inventée (CDC §4.4).
- Une erreur sur une publication n'arrête pas les autres, et rien n'est perdu en silence (CDC §4.6).
- Aucune clé d'API dans le code ni sur GitHub (CDC §4.3).

---

## Étape 0 — Installer les fichiers mis à jour

1. Remplace `src/analyse.py` et `tests/test_analyse.py` par les nouvelles versions.
2. Ajoute `tests/controle_conformite.py` et `docs/guide_execution_module2.md`.
3. `examples/publication_brute.json` : vérifie d'abord s'il existe déjà.
   ```powershell
   Test-Path examples\publication_brute.json
   ```
   - `True` : **ne l'écrase pas** (c'est celui de l'équipe).
   - `False` : ajoute mon fichier, il est attendu par `tests/test_contrat.py`.
4. `git status` doit montrer seulement ces fichiers. **Le fichier `.env` ne doit jamais apparaître.**

## Étape 1 — Environnement Python

```powershell
python --version
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install feedparser requests python-dotenv google-genai
```
- **Attendu** : `(.venv)` au début de la ligne de commande ; Python 3.11 ou plus.
- **Si** « l'exécution de scripts est désactivée » : `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, puis relance l'activation.
- `transformers` et `torch` (très volumineux) s'installent seulement à l'étape 6.

## Étape 2 — Tests automatiques (même commande que la CI GitHub)

```powershell
python -m unittest discover -s tests -v
```
- **Attendu** : `Ran 26 tests ... OK` (3 tests du contrat + 23 tests du module 2).
- **Si** `test_exemple_contient_les_champs_accordes` échoue : `examples/publication_brute.json` manque (étape 0).
- **Pourquoi c'est important** : avant cette mise à jour, la CI n'exécutait aucun test du module 2.

## Étape 3 — Essai sans réseau (IA simulée) + contrôle de conformité

```powershell
python src/analyse.py --entree examples/nouvelles_publications_exemple.json --sortie data/analyse/essai_exemple.json --ia-simulee --sans-classificateur
python tests/controle_conformite.py examples/nouvelles_publications_exemple.json data/analyse/essai_exemple.json
```
- **Attendu (1ʳᵉ commande)** : 15 reçus, 2 invalides, 2 doublons et 11 traités. Avec la configuration de mots-clés élargie actuelle, le résultat de référence est 7 pertinents, 1 non pertinent et 3 incertains ; les catégories peuvent changer si la configuration évolue.
- **Attendu (2ᵉ commande)** : `CONFORME : aucun écart détecté.` Les lignes « à relire » proviennent des incidents simulés ou des cas incertains.
- Le contrôle compare le fichier de sortie au fichier d'entrée et vérifie les règles du CDC (aucune perte, 9 champs intacts, statuts et catégories autorisés, priorité cohérente, motif de rejet uniquement pour les rejets, pas de « non précisé », pas de chiffre inventé). Relance-le après **chaque** exécution.
- **Protection du fichier officiel** : sans `--sortie`, un essai (IA simulée, `--limite` ou `--source`) écrit dans `data/analyse/essai_partiel_ou_simule.json`. Le fichier officiel `publications_analysees.json` n'est écrit que par une exécution complète avec la vraie IA.

## Étape 4 — Collecte réelle (le script de Larissa)

```powershell
python src/collecte.py
Copy-Item data\collecte\nouvelles_publications.json data\collecte\jeu_reference.json
python -c "import json,collections; d=json.load(open('data/collecte/jeu_reference.json',encoding='utf-8')); print(len(d),'publications'); print(collections.Counter(p['source'] for p in d)); print('sans résumé :', sum(1 for p in d if not p['resume_original']))"
```
- **Attendu** : environ une centaine de publications au premier lancement (le CDC cite 115, variable), réparties sur 5 sources.
- **La copie `jeu_reference.json` est indispensable** : au 2ᵉ lancement de `collecte.py`, `nouvelles_publications.json` peut être vide (CDC §2.2).
- **Si la liste est vide** (l'historique existe déjà) : `Rename-Item data\collecte\publications.json publications_sauvegarde.json`, puis relance `collecte.py`.
- **Si une source manque** dans le décompte : c'est côté collecte (Larissa). Signale-le-lui avec le message affiché.

## Étape 5 — Analyse sur de vraies données, règles seules

```powershell
python src/analyse.py --entree data/collecte/jeu_reference.json --sortie data/analyse/essai_regles.json --ia-simulee --sans-classificateur
python tests/controle_conformite.py data/collecte/jeu_reference.json data/analyse/essai_regles.json
```
- **Attendu** : `CONFORME`. Ouvre `essai_regles.json` dans VS Code et lis `justification_filtrage` des cas `incertain` et `non_pertinent`.
- **À noter** : combien de publications BIS/BCE/EBA sont `incertain` (souvent des publications sans lien avec l'IA) et combien d'arXiv sont `pertinent` (souvent à juste titre, car la requête arXiv filtre déjà).
- Les règles seules se trompent sur les faux positifs : c'est le rôle de l'étape 6.

## Étape 6 — Modèle zero-shot (2ᵉ couche du filtrage, CDC §3.3)

```powershell
pip install transformers torch
python src/analyse.py --entree data/collecte/jeu_reference.json --sortie data/analyse/essai_zero_shot.json --ia-simulee --limite 10
```
- **Attendu** : le 1ᵉʳ lancement télécharge le modèle (volumineux, plusieurs minutes). Un avertissement sur les « symlinks » sous Windows est sans gravité. Ensuite, `score_filtrage` contient des nombres entre 0 et 1, et `justification_filtrage` se termine par `Modèle zero-shot : score 0.xx`.
- **Puis** lance sur tout le jeu en retirant `--limite 10`, et relance le contrôle de conformité.
- **Si** `[!] Classificateur zero-shot indisponible (NomDeLErreur)` :

| Erreur affichée | Cause probable | Action |
|---|---|---|
| `ModuleNotFoundError` | transformers/torch non installés | `pip install transformers torch` |
| `OSError` / `ConnectionError` | téléchargement impossible | vérifier la connexion Internet |
| `MemoryError` | mémoire insuffisante | fermer d'autres programmes |

- Sur un PC sans carte graphique, compte quelques secondes par publication.
- **Rappel** : les seuils (0,70 pour pertinent, 0,30 pour rejet) sont provisoires. On les ajustera à l'étape 9.

## Étape 7 — Gemini (analyse approfondie, CDC §4.3)

### 7.1 Créer la clé
1. Va sur Google AI Studio (aistudio.google.com) et connecte-toi avec un compte Google.
2. « Get API key », puis « Create API key », et copie la clé.
3. Le palier gratuit a des quotas limités (d'où la pause entre appels) et ses conditions peuvent permettre à Google d'utiliser les requêtes : acceptable pour des publications publiques, mais à connaître.

### 7.2 La ranger dans `.env` (jamais dans le code)
```powershell
Copy-Item .env.example .env
notepad .env
```
Dans `.env`, écris **sans espaces ni guillemets** : `IA_API_KEY=ta_cle`

Vérifie qu'il est bien ignoré par Git :
```powershell
git check-ignore -v .env
git status
```
- **Attendu** : la 1ʳᵉ commande affiche la règle `.env` du `.gitignore`, et `git status` ne liste pas `.env`.
- **Ne colle jamais ta clé** dans un chat, un commit ou un message. Si elle fuit : supprime-la dans AI Studio et crée-en une autre.

### 7.3 Tester la clé et choisir le modèle
```powershell
python src/analyse.py --verifier-api
```
- **Attendu** : la liste des modèles Gemini disponibles avec ta clé, puis `[OK] L'API Gemini fonctionne avec ce modèle.`
- Le modèle par défaut est `gemini-3.5-flash`. S'il n'est pas dans la liste, choisis un nom affiché et ajoute dans `.env` : `GEMINI_MODEL=nom_choisi`. Le CDC demande de vérifier modèles, quotas et coûts actuels : fais-le à ce moment-là.

| Erreur | Cause probable | Action |
|---|---|---|
| `API_KEY_INVALID` ou 400 | clé mal copiée | recopier sans espace |
| `PERMISSION_DENIED` ou 403 | clé ou région non autorisée | recréer la clé dans AI Studio |
| `404` / modèle introuvable | mauvais nom de modèle | `GEMINI_MODEL=` avec un nom de la liste |
| `429` / `RESOURCE_EXHAUSTED` | quota dépassé | attendre, augmenter `--pause` |
| `503` / `UNAVAILABLE` | service occupé | le programme réessaie 3 fois tout seul |

### 7.4 Essai réel sur peu de publications
```powershell
python src/analyse.py --entree data/collecte/jeu_reference.json --source arXiv --limite 10 --sans-classificateur --sortie data/analyse/essai_gemini_arxiv.json --pause 5
python tests/controle_conformite.py data/collecte/jeu_reference.json data/analyse/essai_gemini_arxiv.json
```
- **Pourquoi `--source arXiv`** : `--limite 10` seul prend les 10 premiers éléments du fichier, qui sont tous de la BIS (peu de publications pertinentes, donc presque aucun appel à Gemini). Avec `--source`, tu choisis une source riche en publications pertinentes (`arXiv` ou `Finextra`).
- **Attendu** : les publications pertinentes ont `statut_analyse` = `effectuee` et des textes en français.
- **Lis chaque `resume_fr`** à côté du `resume_original` : y a-t-il quelque chose qui n'est pas dans la source ? C'est le critère central du CDC (« sans résultats inventés »).
- **Si** `en_echec` : lis `detail_analyse`. Une réponse « inexploitable » signifie que le modèle n'a pas rendu un JSON valide : note le cas, il servira à améliorer le prompt.

### 7.5 Exécution complète
```powershell
python src/analyse.py --entree data/collecte/jeu_reference.json --pause 5
python tests/controle_conformite.py data/collecte/jeu_reference.json data/analyse/publications_analysees.json
```
Le fichier officiel `data/analyse/publications_analysees.json` est alors produit. Le temps total dépend du nombre de publications pertinentes (compte au moins 5 secondes chacune).

## Étape 8 — Vérifier le raccordement avec la collecte (critère d'acceptation du CDC)

```powershell
python src/collecte.py
python src/analyse.py --ia-simulee --sans-classificateur
```
Sans `--entree`, le module lit directement `data/collecte/nouvelles_publications.json`. Cet essai utilise l'IA simulée : il écrit donc dans `data/analyse/essai_partiel_ou_simule.json` et ne touche pas au fichier officiel. Si la collecte ne renvoie aucune nouveauté, il écrit une liste vide `[]` : c'est normal et valide.

## Étape 9 — Évaluer le filtrage (CDC §6.1)

1. Choisis **40 à 60 publications** de `jeu_reference.json`, de plusieurs sources.
2. **Avant de regarder les décisions du modèle**, note pour chacune ton verdict (`pertinent` ou `non_pertinent`) dans un fichier CSV : `id; titre; ma_decision; commentaire`.
3. Compare ensuite avec `statut_pertinence`.
   - **Précision** = parmi les publications que le module juge pertinentes, la part qui l'est vraiment.
   - **Rappel** = parmi les publications réellement pertinentes, la part que le module retrouve.
   - Regarde en priorité les **faux négatifs** : une publication pertinente classée `non_pertinent` est perdue.
4. Ajuste les seuils et les mots-clés, puis recommence.

## Étape 10 — Vérifier au moins 10 analyses (CDC §6.2)

Pour 10 publications `effectuee`, remplis un tableau avec : `id`, technologie correcte ?, problème financier correct ?, catégorie correcte ?, information inventée ?, JSON valide ? (oui/non), commentaire.

## Étape 11 — Livrables du CDC (§7)

| Livrable | Où | Statut |
|---|---|---|
| 1. Code `src/analyse.py` | dépôt | fait, à valider sur données réelles |
| 2. Dépendances et configuration | `requirements.txt`, `.env.example`, ce guide | à compléter (modèle retenu) |
| 3. JSON enrichi | `data/analyse/publications_analysees.json` | après l'étape 7.5 |
| 4. Résultats des tests de filtrage | étape 9 | à faire |
| 5. Dix analyses revues | étape 10 | à faire par la personne en charge des tableaux ; le jeu actuel ne contient que 2 analyses `effectuee` |
| 6. Documentation courte | section du README | à écrire à la fin |

---

## Champs complémentaires `priorite` et `motif_rejet`

Le module ajoute maintenant ces deux champs en sortie uniquement ; les neuf champs d'entrée et leurs valeurs restent inchangés.

- `priorite` : `haute` pour les cas incertains ou une analyse pertinente à relire (analyse incomplète/en échec), `moyenne` pour une analyse pertinente terminée, `basse` pour un rejet `non_pertinent`.
- `motif_rejet` : texte explicatif uniquement quand `statut_pertinence` vaut `non_pertinent` ; `null` pour les autres statuts. Le motif reprend les conditions de rejet du filtre, pas une opinion générée par le LLM.

Ces règles sont opérationnelles et doivent être validées avec l'équipe. Sosthène doit les ajouter au mapping Google Sheets si son schéma le permet ; elles ne remplacent aucune colonne existante. Le journal des nouvelles exécutions conserve également les nombres de termes chargés et l'empreinte SHA-256 du fichier de configuration.
