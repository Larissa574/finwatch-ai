# Rapport technique — FINWATCH AI, module 2

**Périmètre :** filtrage de pertinence et analyse des publications par IA.
**Version documentée :** configuration de mots-clés élargie, champs de sortie `priorite` et `motif_rejet` ajoutés.
**Statut de la configuration :** proposition technique à valider par le groupe ; ce document ne prétend pas que les mots-clés ou les seuils ont déjà été validés scientifiquement.

## 1. Objectif du module

Le module 2 reçoit la liste JSON produite par le collecteur. Le cahier des charges complet n’étant pas joint aux fichiers examinés, l’audit ci-dessous porte sur les règles explicites du guide d’exécution, du code et des tests fournis ; il ne constitue pas une certification exhaustive clause par clause du CDC v1.1. Il conserve sans modification les neuf champs contractuels de chaque publication, écarte les entrées invalides et les doublons en les traçant dans un journal, estime la pertinence de chaque publication pour le thème « applications de l’intelligence artificielle en finance », puis analyse en français les publications retenues. Il produit une liste JSON enrichie et un journal séparé.

Le module ne collecte pas lui-même de données RSS/API. Il ne doit pas inventer les détails absents du titre et du résumé. Une information qui n’est pas fournie doit rester `null`. Les cas incertains, les échecs et les sorties non conformes doivent rester visibles pour une vérification humaine.

## 2. Flux de traitement

1. **Lecture :** charge le fichier donné par `--entree`, par défaut `data/collecte/nouvelles_publications.json`.
2. **Validation :** vérifie que chaque élément est un objet exploitable et que `id`, `titre` et `url` sont des chaînes non vides. Les éléments invalides sont placés dans `journal_analyse.json` ; les autres continuent.
3. **Dédoublonnage :** conserve la première occurrence d’un même `id`, ou d’un même titre normalisé publié le même jour. Les doublons écartés sont journalisés.
4. **Filtrage :** combine les mots-clés et, sauf option `--sans-classificateur`, un classificateur zero-shot. Les décisions sont `pertinent`, `non_pertinent` ou `incertain`.
5. **Analyse approfondie :** les publications `pertinent` disposant d’un résumé suffisamment long sont envoyées à Gemini. Les publications sans contenu suffisant ne sont pas envoyées au LLM ; leur statut d’analyse est `incertaine`.
6. **Contrôles :** les champs d’analyse, les catégories, les valeurs `null` et les chiffres produits sont vérifiés. Une erreur sur un article n’arrête pas le lot.
7. **Export :** le module écrit le résultat dans un JSON et les incidents/paramètres dans un journal JSON distinct.

## 3. Entrée et contrat à préserver

Les neuf champs d’entrée, qui doivent demeurer identiques dans les résultats, sont :

- `id`
- `titre`
- `source`
- `url`
- `date_publication`
- `date_collecte`
- `auteur`
- `resume_original`
- `type_document`

Le module ne modifie pas ces valeurs. Il ajoute quinze champs de sortie :

- `statut_pertinence`
- `score_filtrage`
- `justification_filtrage`
- `motif_rejet`
- `priorite`
- `categorie`
- `technologie_ia`
- `probleme_financier`
- `innovation`
- `resultats`
- `resume_fr`
- `interet_financier`
- `niveau_information`
- `statut_analyse`
- `detail_analyse`

Les catégories autorisées sont `MARCHES_FINANCIERS`, `REGLEMENTATION_CONFORMITE`, `CREDIT_MICROFINANCE` et `BANQUE`. La catégorie reste `null` quand le rattachement n’est pas clair.

### 3.1 Règles des champs complémentaires

`priorite` est une règle opérationnelle destinée à organiser la relecture, pas un score scientifique ni une prédiction produite par Gemini :

- `haute` : publication `incertain`, ou publication pertinente dont l’analyse reste incertaine, incomplète ou en échec ;
- `moyenne` : publication pertinente dont l’analyse est `effectuee` ;
- `basse` : publication classée `non_pertinent`.

`motif_rejet` est une explication technique du rejet du filtre. Il contient une chaîne uniquement si `statut_pertinence = non_pertinent` ; il vaut `null` dans les autres cas. Il résume les règles réellement appliquées : seuil zero-shot et signal lexical, ou absence de signal lexical suffisant lorsque le classificateur n’est pas disponible. Il ne doit pas être compris comme un jugement humain ni comme une conclusion du LLM.

Ces deux champs sont des ajouts à la sortie. Ils ne remplacent aucun champ d’entrée et n’obligent pas à changer le format d’entrée du collecteur. Leur correspondance avec les colonnes Google Sheets reste à intégrer/valider par la personne qui gère le stockage.

## 4. Mots-clés et limites de leur usage

Le fichier actif est `config/mots_cles.json`. Il rassemble les mots du JSON transmis, issus des chaînes de veille générales et institutionnelles, puis ajoute des synonymes et variantes français/anglais dans les quatre axes prioritaires.

| Liste chargée par le module | Nombre d’entrées dans la configuration courante | Usage |
|---|---:|---|
| `termes_ia` | 164 | Repérage des technologies et méthodes IA |
| `termes_finance` | 407 | Vocabulaire financier fusionné à partir des quatre axes |
| `expressions_specialisees` | 149 | Expressions composées IA-finance, fraude, crédit, trading, conformité, etc. |

Les listes par axe dans le fichier de configuration contiennent : 91 termes pour `MARCHES_FINANCIERS`, 93 pour `REGLEMENTATION_CONFORMITE`, 109 pour `CREDIT_MICROFINANCE` et 115 pour `BANQUE`. Les doublons fonctionnellement identiques à l’intérieur de chaque liste ont été nettoyés ; les variantes utiles et les termes d’origine sont conservés.

`contexte_geographique` est conservé pour guider la veille documentaire, mais n’est pas utilisé dans le score lexical de `src/analyse.py`. La présence d’un pays, d’une institution ou d’une région ne doit pas suffire à elle seule à déclarer une publication pertinente pour l’IA en finance.

Le chargeur utilise les listes d’axes comme vocabulaire financier, puis `termes_ia` et `expressions_specialisees`. Si une de ces listes est vide ou absente, il conserve la liste de repli intégrée au code pour cette liste. Le journal d’une nouvelle exécution enregistre l’origine et le nombre de termes chargés ainsi que l’empreinte SHA-256 du fichier de configuration. Cela facilite la comparaison de deux exécutions.

**Limite importante :** un lexique plus large peut augmenter les faux positifs et les cas `incertain`. L’extension améliore la couverture, mais ne prouve pas à elle seule que le filtre est plus performant. Il faut réaliser l’évaluation humaine de l’étape 9 et recalibrer les seuils uniquement après cette évaluation.

## 5. Fichiers du module et fonctions principales

### `src/analyse.py`

C’est le cœur du module 2.

| Fonction / bloc | Rôle et résultat |
|---|---|
| Constantes et catégories | Définit les neuf champs d’entrée, les champs ajoutés, les statuts, les quatre catégories, les seuils et les chemins. |
| `mots_cles_provisoires()` | Retourne les listes de repli et leur origine (`provisoire`). |
| `charger_mots_cles()` | Lit `config/mots_cles.json` et retourne `termes_ia`, `termes_finance`, `expressions` et leur origine. |
| `nettoyer_texte()` | Supprime les balises HTML et espaces superflus sans modifier la valeur d’origine stockée. Retourne une chaîne de travail. |
| `normaliser()` / `compter()` | Normalisent les textes pour chercher les termes et renvoient les occurrences lexicales distinctes détectées. |
| `charger_publications()` | Retourne une liste JSON ; lève `ValueError` si le fichier est absent, vide, invalide ou si la racine n’est pas une liste. `[]` est accepté. |
| `valider_publication()` | Retourne une liste d’erreurs d’entrée ; une liste vide signifie que la publication possède les champs essentiels. |
| `cle_titre()` / `dedoublonner()` | Construisent la clé titre-date et renvoient `(publications_uniques, doublons)`. |
| `prefiltrer()` | Retourne un signal (`fort`, `faible`, `aucun`) et les nombres de termes IA/finance/expressions détectés. |
| `charger_classificateur()` | Retourne une fonction qui calcule un score zero-shot, ou `None` si le modèle ne peut pas être chargé. |
| `decider()` | Combine le signal lexical, le score et la suffisance du résumé ; retourne un des trois statuts de pertinence. |
| `filtrer()` | Retourne `statut_pertinence`, `score_filtrage`, `justification_filtrage` et `motif_rejet`. |
| `niveau_information()` | Retourne le niveau documentaire, notamment `resume_seul`, `metadonnees_seules` ou `insuffisant`. |
| `construire_prompt()` | Construit le texte envoyé à Gemini à partir du titre, de la source, de la date et du résumé. |
| `charger_env()`, `cle_api()`, `nom_modele()` | Chargent les paramètres locaux et retrouvent la clé/le nom du modèle sans écrire de secret dans le code. |
| `appeler_gemini()` / `verifier_api()` | Appellent Gemini avec reprises limitées, ou vérifient la disponibilité de l’API et du modèle. |
| `appeler_ia_simulee()` | Retourne une fausse réponse uniquement pour les essais locaux ; elle ne fournit pas une vraie analyse scientifique. |
| `extraire_json()` / `_valeur_texte()` | Valident la forme JSON de la réponse et transforment les valeurs absentes ou « non précisé » en `null`. |
| `_nombres()` / `analyser()` | Vérifient certains chiffres cités, analysent une publication et retournent `(champs_analyse, panne_api_detectee)`. |
| `champs_vides()` | Retourne les quinze champs ajoutés initialisés à `null`. |
| `determiner_priorite()` | Calcule la priorité de revue à partir des statuts de pertinence et d’analyse. |
| `verifier_sortie()` | Retourne les écarts de schéma, de types ou de valeurs. |
| `traiter_une()` | Retourne une publication originale enrichie et l’état de panne API. |
| `traiter_publications()` | Retourne `(résultats, journal)` pour tout le lot ; les erreurs individuelles sont journalisées. |
| `exporter()` | Écrit un JSON avec remplacement atomique via un fichier temporaire. |
| `afficher_bilan()` | Affiche les compteurs des résultats dans la console. |
| `selectionner()` / `choisir_sortie()` | Filtrent par source/limite et protègent le fichier officiel durant les essais. |
| `main()` | Gère les options de ligne de commande, l’exécution du pipeline et les deux exports. |

Le script ne doit pas écrire les essais simulés ou partiels dans `data/analyse/publications_analysees.json`. Il utilise `data/analyse/essai_partiel_ou_simule.json` sauf si un chemin `--sortie` explicite est donné.

### 5.1 Sorties produites par le module

**`publications_analysees.json`** : liste de publications ; chaque élément contient les neuf champs originaux plus quinze champs d’analyse/filtrage. Le fichier officiel ne doit être remplacé que par une exécution complète avec la vraie IA.

**`journal_analyse.json`** : objet JSON, pas une liste de publications. Il contient :

- `entrees_invalides` : position, erreurs et contenu brut des éléments rejetés en validation ;
- `doublons_ecartes` : identité/titre, raison du doublon et identifiant de l’élément conservé ;
- `sorties_non_conformes` : erreurs détectées dans les résultats ;
- `parametres` : origine/nombre des mots-clés, mode simulé ou réel, nom du classificateur, nom du modèle LLM, seuils, filtre par source/limite et empreinte de la configuration lors d’une nouvelle exécution.

## 6. Arborescence du projet livré

```text
finwatch-ai/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── audit_analyses.csv
├── evaluation_filtrage.csv
├── .github/
│   └── workflows/
│       ├── collecte.yml
│       └── tests.yml
├── config/
│   ├── mots_cles.json
│   └── sources.json
├── data/
│   ├── collecte/
│   │   ├── jeu_reference.json
│   │   ├── nouvelles_publications.json
│   │   └── publications.json
│   └── analyse/
│       ├── essai_exemple.json
│       ├── essai_gemini.json
│       ├── essai_gemini_arxiv.json
│       ├── essai_zero_shot.json
│       ├── journal_analyse.json
│       └── publications_analysees.json
├── docs/
│   ├── guide_execution_module2.md
│   ├── rapport_technique_module2.md
│   └── passation_sosthene.md
├── examples/
│   ├── nouvelles_publications_exemple.json
│   └── publication_brute.json
├── src/
│   ├── analyse.py
│   ├── collecte.py
│   ├── diffusion.py
│   ├── generer_tableaux.py
│   ├── main.py
│   └── stockage.py
└── tests/
    ├── controle_conformite.py
    ├── test_analyse.py
    └── test_contrat.py
```

## 7. Inventaire des autres fichiers

### Configuration, exemples et tests

- **`config/sources.json`** : catalogue descriptif de onze sources prévues et de leur statut. Il indique `A_TESTER` pour chaque source ; il ne constitue pas la preuve que les onze sources sont branchées au collecteur.
- **`examples/publication_brute.json`** : exemple d’une publication brute et de ses neuf champs. Il sert au test du contrat.
- **`examples/nouvelles_publications_exemple.json`** : jeu de démonstration avec cas valides, entrées invalides, doublons et incidents de test. Il permet de tester le pipeline sans API réelle.
- **`tests/test_analyse.py`** : tests unitaires du filtrage, de l’analyse, du traitement des erreurs, de la CLI, de la configuration et des nouveaux champs. Les appels IA sont simulés.
- **`tests/test_contrat.py`** : vérifie les neuf champs d’entrée de l’exemple, les quatre axes et le catalogue de onze sources.
- **`tests/controle_conformite.py`** : compare les données d’entrée et de sortie et vérifie le contrat et les gardes-fous. C’est un contrôle de structure et de cohérence, pas une validation scientifique des conclusions.
- **`requirements.txt`** : dépendances Python, notamment Requests, feedparser, dotenv, gspread, Google GenAI, Transformers et PyTorch.
- **`.env.example`** : noms des paramètres locaux attendus, sans valeurs secrètes.
- **`.gitignore`** : exclut entre autres `.env`, clés, caches et données locales.
- **`.github/workflows/tests.yml`** : exécute les tests du contrat manuellement.
- **`.github/workflows/collecte.yml`** : scénario manuel de collecte/artefact ; ne lance pas le module 2.

### Modules appartenant à l’intégration globale

- **`src/collecte.py`** : collecte des publications depuis les sources câblées, normalise les données et produit les neuf champs d’entrée. Dans cette version, les sources sont définies directement dans le code (quatre flux RSS et l’API arXiv). Le catalogue `config/sources.json` de onze sources n’est donc pas encore entièrement relié au collecteur.
- **`src/stockage.py`** : interface prévue pour Google Sheets et la validation humaine. Les fonctions sont encore des `NotImplementedError` ; aucun stockage Google Sheets opérationnel ne peut être affirmé.
- **`src/diffusion.py`** : interface prévue pour générer le bulletin HTML et envoyer les e-mails. Les fonctions sont encore des `NotImplementedError`.
- **`src/main.py`** : point d’orchestration du pipeline global, encore en attente de l’implémentation des modules d’intégration.
- **`src/generer_tableaux.py`** : lit `data/analyse/publications_analysees.json` et génère les CSV d’évaluation. Il choisit un échantillon aléatoire de 50 publications et prend jusqu’aux 10 premières analyses `effectuee`. **Il écrase les deux CSV lorsqu’il est relancé** : ne pas l’exécuter si des évaluations humaines doivent être conservées.
- **`README.md`** : aperçu général du projet et de son architecture.

### Données déjà présentes dans l’archive

- `data/collecte/jeu_reference.json` : 115 publications conservées comme jeu de référence.
- `data/collecte/nouvelles_publications.json` : 9 publications nouvelles au moment de la capture de l’archive ; ce nombre change après une collecte.
- `data/collecte/publications.json` : historique de 124 publications au moment de la capture.
- `data/analyse/publications_analysees.json` : 115 publications issues d’une exécution antérieure.
- Les fichiers `essai_*.json` sont des sorties d’essais antérieurs. Ils ne doivent pas être interprétés comme le résultat actuel du filtre élargi.
- `evaluation_filtrage.csv` contient un échantillon de 50 lignes, sans verdict humain rempli dans les colonnes de validation.
- `audit_analyses.csv` contient actuellement deux analyses auditées, car le résultat historique n’a que deux publications dont `statut_analyse = effectuee`. Il ne satisfait donc pas, à lui seul, la demande d’auditer dix analyses.

## 8. État de conformité et tests réalisés

### Vérifié dans l’environnement de travail

- `python -m unittest discover -s tests -v` : **26 tests réussis**.
- Exécution locale sur `examples/nouvelles_publications_exemple.json` avec `--ia-simulee --sans-classificateur` : 15 éléments reçus, 2 invalides, 2 doublons écartés et 11 résultats conservés.
- `tests/controle_conformite.py` sur cette sortie simulée : **aucun écart détecté**.
- Les neuf champs d’entrée sont comparés à leurs valeurs d’origine.
- Les nouveaux champs sont vérifiés : priorité autorisée et motif de rejet uniquement pour `non_pertinent`.
- L’exemple et les tests ne nécessitent pas de clé API ; aucune analyse de test ne doit être présentée comme une vraie analyse Gemini.

### Données historiques : limites à lire avant usage

Le fichier historique `data/analyse/publications_analysees.json` contient 115 éléments : 53 `pertinent`, 61 `incertain` et 1 `non_pertinent`. Parmi les 53 publications pertinentes, seules 2 sont `effectuee`, 6 sont `incertaine` et 45 sont `en_echec`. Ce constat interdit de conclure que la partie analyse réelle est prête pour diffusion.

Le journal historique indique que les mots-clés utilisés étaient les listes `provisoire`. Les nouveaux champs `priorite` et `motif_rejet` ont été ajoutés **de façon additive** aux JSON déjà présents, à partir des statuts et justifications existants ; aucun filtre ou appel Gemini n’a été relancé pour réécrire ces décisions. Les champs d’origine et toutes les valeurs d’analyse antérieures ont été préservés. Ces sorties historiques ne reflètent donc pas encore les décisions qui seront prises par la nouvelle configuration de mots-clés.

Un contrôle de conformité qui passe garantit seulement que la structure et les gardes-fous vérifiés sont cohérents. Il ne signifie ni que les analyses sont toutes terminées, ni que la précision/rappel ont été évalués, ni que le rendu Google Sheets a été validé.

## 9. Points restant à réaliser par les personnes responsables

1. Rejouer l’analyse sur un jeu de référence avec la configuration élargie, après vérification de la clé, du nom de modèle et des quotas Gemini ; contrôler les résultats avant de remplacer le JSON officiel.
2. Faire l’évaluation humaine de 40 à 60 publications (étape 9) et l’audit d’au moins dix analyses `effectuee` (étape 10). Ces tableaux sont gérés par la personne en charge de cette partie ; ils n’ont pas été modifiés dans ce travail.
3. Faire valider les seuils et les listes élargies par l’évaluation humaine, en regardant particulièrement les faux négatifs et l’augmentation éventuelle des faux positifs.
4. Intégrer `priorite` et `motif_rejet` au schéma de stockage/Google Sheets si le responsable du stockage valide ces colonnes.
5. Compléter ultérieurement `src/stockage.py`, `src/diffusion.py` et `src/main.py` pour rendre le pipeline global opérationnel.

## 10. Règles de manipulation sûres

- Ne jamais ajouter la clé d’API dans le code, les fichiers suivis par Git, les rapports ou les messages.
- Ne pas écraser `examples/publication_brute.json` s’il a été remplacé par la version de référence de l’équipe.
- Ne pas utiliser les sorties simulées comme résultats scientifiques.
- Ne pas exécuter `src/generer_tableaux.py` avant d’avoir coordonné la sauvegarde des évaluations humaines : il écrase les CSV.
- Conserver le journal associé à chaque sortie pour savoir quels mots-clés, seuils, modèle et options ont été utilisés.
