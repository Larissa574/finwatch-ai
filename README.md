# FINWATCH AI

**Veille technologique automatisée sur les innovations de l'intelligence artificielle en finance.**

Projet universitaire — quatre axes : **marchés financiers**, **réglementation et conformité**, **crédit et microfinance**, **banque**.

## Fonctionnement

1. **Collecte :** planification, sources RSS/API/alertes, récupération et normalisation des publications.
2. **Filtrage et analyse IA :** pertinence, dédoublonnage des contenus, classification et synthèse fidèle aux sources.
3. **Stockage  :** Google Sheets, historique, doublons persistants et statuts de validation.
4. **Vérification humaine et diffusion :** contrôle collectif des analyses prioritaires, bulletin HTML et envoi e-mail.


## Organisation des fichiers

```text
.github/workflows/     Contrôles automatiques du dépôt (pas encore la collecte)
config/                Catalogue de sources et recherches à valider
src/                   Quatre modules et futur point d'intégration
tests/                 Tests de structure des données
requirements.txt       Dépendances initiales
.env.example           Noms des paramètres sensibles (sans secrets)
```

Documentation du module 2

- [`docs/rapport_technique_module2.md`](docs/rapport_technique_module2.md) : fonctionnement, entrées/sorties, inventaire des fichiers et état de conformité.
- [`docs/guide_execution_module2.md`](docs/guide_execution_module2.md) : commandes d'installation, de test et d'exécution.
- [`docs/passation_sosthene.md`](docs/passation_sosthene.md) : résumé autonome des changements et consignes de reprise/intégration.

La configuration `config/mots_cles.json` est une proposition élargie à valider après les étapes d'évaluation humaine. Les champs supplémentaires `priorite` et `motif_rejet` sont uniquement ajoutés en sortie ; les neuf champs de collecte restent inchangés.
