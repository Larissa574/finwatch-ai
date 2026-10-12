# Passation de travail — module 2 FINWATCH AI

## 1. Objet de cette passation

Ce document décrit ce qui a été livré pour le module 2 et comment l’intégrer au travail global. Il est autonome : il ne suppose pas que le lecteur a accès à la conversation d’origine.

Le périmètre de ce travail est le filtrage et l’analyse des publications par IA, la configuration des mots-clés et les contrôles de conformité. Les tableaux d’évaluation Excel/CSV et les développements de stockage/diffusion restent dans le périmètre de la personne qui les gère.

## 2. Modifications livrées

1. **`config/mots_cles.json` rempli et élargi.** Les listes du fichier de mots-clés transmis ont été fusionnées aux quatre axes financiers. Des variantes FR/EN et des expressions plus ciblées ont été ajoutées. La configuration courante contient 164 termes IA, 407 termes financiers uniques chargés par le module et 149 expressions spécialisées. Le statut est `PROPOSITION_ETENDUE_A_VALIDER` : elle est prête pour essais, mais n’est pas présentée comme validée scientifiquement par le groupe.
2. **`src/analyse.py` mis à jour.** Les champs `priorite` et `motif_rejet` sont ajoutés à la sortie sans remplacer les neuf champs de collecte. La priorité est calculée par règle explicite ; le motif de rejet n’est renseigné que pour un `non_pertinent`.
3. **Contrôles renforcés.** `tests/controle_conformite.py` vérifie maintenant les valeurs permises de `priorite` et la cohérence de `motif_rejet`.
4. **Tests mis à jour.** `tests/test_analyse.py` teste notamment la configuration élargie, les nouveaux champs et la conservation des neuf champs d’entrée.
5. **Documentation ajoutée.** `docs/rapport_technique_module2.md` contient le rapport technique, l’inventaire du dépôt, l’arborescence, les entrées/sorties et l’état des tests. `docs/guide_execution_module2.md` fournit les commandes d’exécution.
6. **Journalisation plus traçable pour les prochaines exécutions.** Le journal enregistre le nombre de termes utilisés et l’empreinte SHA-256 de la configuration des mots-clés.

## 3. Règles des nouveaux champs

- `priorite = haute` : pertinence incertaine ou analyse pertinente à relire (analyse incomplète, incertaine ou en échec).
- `priorite = moyenne` : pertinence positive et analyse terminée (`statut_analyse = effectuee`).
- `priorite = basse` : décision `non_pertinent`.
- `motif_rejet` : explication de la règle de rejet uniquement si `statut_pertinence = non_pertinent`, `null` autrement.

La priorité organise la relecture ; ce n’est ni une mesure de risque financier, ni une note de confiance validée par une évaluation scientifique. Le motif de rejet est produit à partir du signal lexical et du seuil du filtre, pas par Gemini.

Les neuf champs entrants restent : `id`, `titre`, `source`, `url`, `date_publication`, `date_collecte`, `auteur`, `resume_original`, `type_document`. Les valeurs originales sont conservées. Les nouveaux champs sont des éléments de sortie supplémentaires.

## 4. Résultats des contrôles réalisés

- Commande : `python -m unittest discover -s tests -v`
- Résultat : **26 tests passés, aucun échec**.
- Essai local du pipeline : 15 entrées, 2 invalides, 2 doublons, 11 publications traitées ; l’exécution est faite avec l’IA simulée et sans classificateur.
- Contrôle de conformité sur cet essai : **`CONFORME : aucun écart détecté.`**

Cet essai valide le code de traitement, pas la qualité d’une analyse réelle. Aucun nouvel appel à Gemini n’a été réalisé dans le cadre de ces tests.

## 5. Ce qui n’a pas été modifié

- Les scripts `src/stockage.py`, `src/diffusion.py` et `src/main.py` restent des squelettes d’intégration ; leurs fonctions lèvent encore `NotImplementedError`.
- `evaluation_filtrage.csv` et `audit_analyses.csv` n’ont pas été remplis ni regénérés. Les évaluations humaines restent du ressort de la personne responsable des tableaux.
- Le collecteur `src/collecte.py` n’a pas été modifié. Il utilise actuellement quatre flux RSS et l’API arXiv définis en dur ; le catalogue de onze sources dans `config/sources.json` n’est pas entièrement branché.
- Aucune clé API n’a été ajoutée à l’archive ou aux fichiers de code.

## 6. Attention au résultat historique inclus dans l’archive

`data/analyse/publications_analysees.json` est une ancienne sortie de 115 publications. Le journal correspondant mentionne l’utilisation des mots-clés provisoires. Les deux champs récents ont été ajoutés de façon additive pour aligner le schéma, sans modifier les statuts, scores, justifications ni champs d’analyse déjà présents. Il ne s’agit **pas** d’un nouveau filtrage avec le lexique élargi.

Cette sortie historique contient 53 publications `pertinent`, 61 `incertain` et 1 `non_pertinent`. Parmi les publications pertinentes, seules 2 analyses sont `effectuee`, 6 `incertaine` et 45 `en_echec`. Il ne faut donc pas envoyer cette ancienne sortie comme si dix analyses validées étaient disponibles. Après vérification des identifiants et quotas Gemini, il faudra lancer une nouvelle exécution contrôlée avec les mots-clés actuels, puis lire le journal et passer le contrôle de conformité avant de remplacer le fichier officiel.

## 7. Étapes de reprise recommandées

1. Lire `docs/rapport_technique_module2.md` pour comprendre les champs, fonctions et fichiers.
2. Dans un environnement Python 3.11+, installer les dépendances de `requirements.txt` et vérifier que `.env` reste ignoré par Git.
3. Lancer les tests unitaires :

   ```powershell
   python -m unittest discover -s tests -v
   ```

4. Vérifier le chemin de la clé Gemini dans `.env` sans jamais partager la clé, puis tester la configuration :

   ```powershell
   python src/analyse.py --verifier-api
   ```

5. Faire un essai sans réseau vers un chemin temporaire, sans toucher au résultat officiel :

   ```powershell
   python src/analyse.py --entree examples/nouvelles_publications_exemple.json --sortie data/analyse/essai_validation.json --ia-simulee --sans-classificateur
   python tests/controle_conformite.py examples/nouvelles_publications_exemple.json data/analyse/essai_validation.json
   ```

6. Pour l’analyse réelle, commencer par un petit lot (source choisie, limite réduite, sortie temporaire), lire les statuts et le journal, puis seulement après validation exécuter le lot complet avec Gemini et recontrôler la conformité.
7. Intégrer les deux colonnes `priorite` et `motif_rejet` dans Google Sheets uniquement après vérification du schéma de stockage. Leur ajout ne change pas les neuf colonnes entrantes.

## 8. Responsabilités liées aux étapes 9 et 10

Les étapes 9 et 10 concernent l’évaluation humaine et les tableaux ; elles ne font pas partie des modifications de code réalisées ici. Le fichier `evaluation_filtrage.csv` contient actuellement un échantillon de 50 publications dont les verdicts humains sont vides. `audit_analyses.csv` contient deux lignes d’analyse à vérifier, alors que le cahier des charges demande au moins dix analyses `effectuee`.

**Important :** ne pas relancer `python src/generer_tableaux.py` tant que les annotations humaines ne sont pas sauvegardées et que la personne responsable n’a pas demandé la génération. Le script échantillonne aléatoirement et écrase ces deux CSV.

## 9. Limite actuelle et critère avant de déclarer le travail terminé

La partie code du module 2 est testée localement et la configuration a été élargie, mais les seuils restent provisoires. Pour conclure à la conformité métier, il reste à vérifier une exécution réelle avec Gemini, évaluer les faux positifs/faux négatifs, auditer au moins dix analyses réellement `effectuee` et valider avec le groupe la configuration des mots-clés ainsi que le mapping Google Sheets.
