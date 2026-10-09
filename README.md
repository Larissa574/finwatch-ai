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

