# Organisation du groupe et responsabilités

| Responsable | Module | Livrable attendu |
|---|---|---|
| Larissa (cheffe de groupe) | `src/collecte.py` | Collecteur RSS/API/alertes, planification et extraction normalisée ; coordination de l'ensemble |
| Jean-Arthur | `src/analyse.py` | Filtrage, classification parmi quatre axes et analyses IA sourcées |
| Sosthene | `src/stockage.py` | Google Sheets, dédoublonnage, historique, gestion des statuts |
| Charbel | `src/diffusion.py` | Vérification humaine coordonnée, bulletin HTML et envoi e-mail |

## Travail commun

Chaque membre remet lors de la plénière :
- les questions de veille ;
- les mots-clés FR/EN et synonymes ;
- les équations de recherche ;
- les critères d'exclusion.

Le groupe valide ensuite les propositions et renseigne `config/mots_cles.json`.

## Collaboration sur GitHub

**Décision : tout le monde travaille sur `main` sans branche ni Pull Request.**

- Avant toute modification, synchroniser les fichiers (`git pull`).
- Modifier prioritairement le module dont on est responsable.
- Ne pas modifier les noms des champs du contrat sans accord du groupe.
- Informer le groupe avant de modifier `src/main.py`, les configurations ou le contrat.
- Faire de petits commits descriptifs ; récupérer les changements avant chaque `git push`.
- Ne jamais publier de secrets, de clés API, de listes privées de destinataires ou de credentials.
- Ne déclarer une source automatisée que lorsqu'elle a été testée en situation réelle.

## Suivi

| Étape | Statut initial |
|---|---|
| Définition du périmètre (4 axes) | Défini |
| Sélection des 11 sources | Catalogue défini |
| Questions et équations de recherche | À remettre en plénière |
| Contrat d'échange | Défini, à valider collectivement |
| Collecte opérationnelle | À développer |
| Filtrage et analyse IA | À développer |
| Google Sheets connecté | À développer |
| Bulletin HTML et e-mail | À développer |
| Tests d'intégration | À exécuter |
