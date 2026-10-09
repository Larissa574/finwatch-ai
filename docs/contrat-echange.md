# FINWATCH AI — Contrat d'échange des données (V1)

**Objectif :** rendre compatibles les quatre modules développés en parallèle. Les noms des champs et les codes de statut sont identiques dans tous les programmes. Format d'échange : dictionnaires Python sérialisables en JSON (et JSON pour les exemples/exports).

## 1. Larissa → Jean-Arthur : publication collectée

| Clé JSON | Type | Règle |
|---|---|---|
| `id` | string | Unique et stable (DOI, identifiant arXiv ou URL normalisée) |
| `titre` | string | Titre de la source, non inventé |
| `source` | string | Organisme ou plateforme d'origine |
| `url` | string | Lien original vérifiable |
| `date_publication` | string ou null | Date au format ISO 8601, si disponible |
| `date_collecte` | string | Horodatage ISO 8601 de collecte |
| `auteur` | string ou null | Auteur si connu |
| `resume_original` | string ou null | Texte disponible dans la source |
| `type_document` | string ou null | Article scientifique, rapport, annonce... |

**Obligatoire :** toutes les clés doivent exister. Quand une valeur n'est pas disponible, utiliser `null` (sans invention).

## 2. Jean-Arthur → Sosthene : publication analysée

**Conserver les neuf clés initiales**, puis ajouter :

| Clé JSON | Type / valeurs |
|---|---|
| `pertinent` | booléen (`true` / `false`) |
| `categorie` | un code des quatre axes, ou null |
| `priorite` | `HAUTE`, `NORMALE` ou null |
| `resume_ia` | texte ou null |
| `innovation` | texte ou null |
| `application_financiere` | texte ou null |
| `impact_potentiel` | texte ou null |
| `motif_rejet` | texte ou null |

Catégories autorisées :
- `MARCHES_FINANCIERS`
- `REGLEMENTATION_CONFORMITE`
- `CREDIT_MICROFINANCE`
- `BANQUE`

L'IA fournit une proposition sourcée, **pas une validation**. Les analyses importantes seront contrôlées par une personne.

## 3. Sosthene → Charbel : publications stockées et vérifiées

Google Sheets conserve les champs précédents et les compléments suivants :

| Clé | Valeurs |
|---|---|
| `statut_validation` | `A_VERIFIER`, `VALIDE`, `REJETE`, `NON_PRIORITAIRE`, `ECARTE` |
| `valide_par` | nom du vérificateur ou null |
| `date_validation` | date ISO 8601 ou null |
| `statut_envoi` | `NON_ENVOYE`, `ENVOYE`, `ERREUR_ENVOI` |
| `date_envoi` | date ISO 8601 ou null |

Les analyses prioritaires sont marquées `A_VERIFIER` tant qu'aucun membre ne les a validées. **Ne jamais effacer ou réinitialiser une validation humaine à cause d'une nouvelle collecte.**

## 4. Charbel : règles de diffusion

Le bulletin analytique n'inclut que les publications pour lesquelles :
- `statut_validation == "VALIDE"`
- `statut_envoi == "NON_ENVOYE"`

Après un envoi confirmé, passer à `ENVOYE` et renseigner `date_envoi`. Si l'envoi échoue, laisser la publication disponible pour un nouvel essai et enregistrer l'erreur.

## 5. Règles collectives

1. Aucun membre ne renomme seul les clés du contrat.
2. Les identifiants et URLs restent inchangés pendant les transmissions.
3. Les dates sont en ISO 8601 ; les horodatages UTC portent le suffixe `Z`.
4. La déduplication métier lors du filtrage et la déduplication persistante dans Sheets sont complémentaires.
5. Une publication rejetée n'est pas envoyée dans un bulletin analytique.
6. Les contenus générés par IA sont vérifiés à partir de la source originale avant validation.
7. Les mots-clés et équations booléennes ne sont pas encore validés : ils seront remis en plénière.

## 6. Test collectif de bout en bout

- [ ] Larissa fournit plusieurs publications avec les neuf champs convenus.
- [ ] Jean-Arthur conserve ces champs et ajoute ses résultats.
- [ ] Sosthene enregistre puis relance l'opération sans générer de doublons.
- [ ] Le groupe vérifie et valide une publication à partir de la source.
- [ ] Charbel envoie uniquement les éléments `VALIDE` et `NON_ENVOYE`.
- [ ] Un nouvel envoi ne rediffuse pas la publication déjà envoyée.

**État :** contrat défini, intégration technique non encore testée.
