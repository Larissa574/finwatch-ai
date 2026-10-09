# FINWATCH AI

**Veille technologique automatisée sur les innovations de l'intelligence artificielle en finance.**

Projet universitaire — quatre axes : **marchés financiers**, **réglementation et conformité**, **crédit et microfinance**, **banque**.

## Fonctionnement

1. **Collecte — Larissa :** planification, sources RSS/API/alertes, récupération et normalisation des publications.
2. **Filtrage et analyse IA — Jean-Arthur :** pertinence, dédoublonnage des contenus, classification et synthèse fidèle aux sources.
3. **Stockage — Sosthene :** Google Sheets, historique, doublons persistants et statuts de validation.
4. **Vérification humaine et diffusion — Charbel :** contrôle collectif des analyses prioritaires, bulletin HTML et envoi e-mail.

La diffusion analytique est réservée aux publications **validées humainement**. Tous les modules échangent des données conformes à [docs/contrat-echange.md](docs/contrat-echange.md).

## Organisation des fichiers

```text
.github/workflows/     Contrôles automatiques du dépôt (pas encore la collecte)
config/                Catalogue de sources et recherches à valider
src/                   Quatre modules et futur point d'intégration
docs/                  Contrat d'échange et organisation
examples/              Données fictives de test
tests/                 Tests de structure des données
requirements.txt       Dépendances initiales
.env.example           Noms des paramètres sensibles (sans secrets)
```

## État actuel

**Architecture initiale uniquement.** Les fonctions dans `src/` sont des squelettes à développer, et les sources de `config/sources.json` sont **sélectionnées, non encore connectées ni testées**. Aucun collecteur, analyse IA, accès Google Sheets ou envoi d'e-mail n'est opérationnel à ce stade.

Les **11 sources** sont un catalogue de veille ; l'automatisation démarrera avec arXiv, BRI/BIS et BCE/Supervision si les tests d'accès sont concluants. Les mots-clés et équations seront ajoutés après validation collective.

La collecte envisagée est toutes les **12 heures** et le bulletin **hebdomadaire**. Le calendrier effectif ne sera activé qu'après tests.

## Collaboration

Le groupe travaille **directement sur `main`**, sans branches supplémentaires ni Pull Requests, comme convenu. Chaque membre modifie prioritairement son fichier `src/` et se coordonne avant de changer les fichiers partagés (`README.md`, `docs/contrat-echange.md`, `config/`, `src/main.py`). Faire `git pull` avant de commencer et avant de pousser les modifications.

**Interdiction de commiter des mots de passe, clés API, jetons ou comptes de service.** Les secrets de déploiement seront configurés dans les paramètres sécurisés du dépôt.

## Premier contrôle

```bash
python -m unittest discover -s tests -v
```

Ce test vérifie seulement la forme d'un exemple de publication, **pas** le fonctionnement du système complet.
