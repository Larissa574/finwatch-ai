# FINWATCH AI — Procedure d'integration (V1)

## Etat sur la branche main
- Collecte : `src/collecte.py` (5 sources) ; `data/collecte/publications.json` et `nouvelles_publications.json`.
- Filtrage et analyse : `src/analyse.py` (module de Jean-Arthur importe sans fusion destructive).
- Stockage : `src/importer_stockage.py`, `src/stockage.py`, `src/importer_analyses.py`.
- Validation / diffusion : `src/run_diffusion.py`, `src/diffusion.py`.
- Aucun workflow d'envoi programme : `.github/workflows/diffusion.yml` est manuel et son apercu est selectionne par defaut.
- Le workflow `.github/workflows/collecte.yml` reste manuel ; il ne declenche ni Gemini, ni SMTP.

## Secrets
Ne jamais committer de JSON prive Google ou de cle API.
- `GOOGLE_CREDENTIALS_JSON` : texte JSON du compte de service Google ;
- `GOOGLE_SHEET_ID` : identifiant du classeur ;
- `IA_API_KEY` : cle Gemini pour une execution reelle seulement ;
- `GEMINI_MODEL` : nom exact du modele accessible ;
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `MAIL_FROM`, `MAIL_TO` : envoi, apres validation du groupe.
Le stockage accepte aussi un fichier local `secrets/finwatch-sheets.json`, non suivi par Git.
Les noms des secrets sont coherents entre stockage et diffusion.

## Installation et tests *sans* utiliser de cle ni d'email
Depuis la racine du depot :

```powershell
python -m pip install -r requirements.txt
python -m pytest tests -v
python src/analyse.py --entree examples/nouvelles_publications_exemple.json --ia-simulee --sans-classificateur
```

L'execution du modele zero-shot reel necessite les dependances lourdes de `requirements-ia.txt` et un telechargement du modele.
Les tests Python simulant Sheets et SMTP ne remplacent pas un essai reel de connexion ou d'envoi.

## Execution manuelle des modules (apres autorisation d'utiliser les services)
1. `python src/collecte.py` : collecte reelle.
2. `python src/importer_stockage.py` : insere les nouvelles publications, controle les doublons dans Sheets.
3. `python src/analyse.py` : filtre/analyse `nouvelles_publications.json`, utilise Gemini si configure. NE PAS executer en mode reel sans avoir verifie les quotas et l'autorisation.
4. `python src/importer_analyses.py` : met a jour uniquement les lignes Sheets existantes avec les analyses de statut `effectuee` et pertinentes. Les statuts de validation/envoi ne changent pas.
5. Validation humaine dans Sheets avec `statut_validation=VALIDE`, `valide_par`, `date_validation`.
6. `python src/run_diffusion.py --dry-run` : genere un apercu sans envoi ; `python src/run_diffusion.py` peut envoyer reellement et exige une autorisation distincte.

**Attention** : le point d'entree `src/main.py` enchaine actuellement seulement la collecte et le stockage. Le systeme complet n'est PAS encore programme de bout en bout.

## Contrat analyse vers Sheets (mapping)

| Analyse Jean-Arthur | Stockage Sosthene |
|---|---|
| `id` | `id` (identique) |
| `resume_fr` | `resume_ia` |
| `categorie` | `categorie` |
| `innovation` | `innovation` |
| `probleme_financier` | `application_financiere` |
| `interet_financier` | `impact_potentiel` |

Les categories sont exactement `MARCHES_FINANCIERS`, `REGLEMENTATION_CONFORMITE`, `CREDIT_MICROFINANCE`, `BANQUE`.
Une analyse incertaine ou en echec ne doit pas etre introduite comme analyse terminee dans les colonnes destinées a la newsletter.

## Limitations a lever avant la mise en production
1. **Persistance du statut d'analyse** : les 19 colonnes actuelles ne contiennent pas les champs `statut_pertinence` et `statut_analyse`. Les publications ignorees, incertaines ou en echec sont tracées par le journal JSON local, mais ne disposent pas encore d'un cycle de reprise persistant. Il faut convenir d'une evolution de schema avec Sosthene sans ecraser le classeur.
2. **Reprise des nouveautes** : le collecteur n'utilise pas encore les identifiants Google Sheets au demarrage. Sur GitHub Actions, la liste de nouveautes peut contenir des publications deja vues. Le stockage les dedoublonne, mais le traitement Gemini doit aussi s'appuyer sur l'historique persistant pour eviter les appels redondants.
3. **Evaluation IA** : les scores et seuils ne sont pas valides scientifiquement ; tester la precision, le rappel et la fidelite des analyses avec des exemples annotes.
4. **Test externe** : verifier les secrets et les autorisations Google sur un classeur de test, sans toucher aux vraies publications ; tester les envois seulement apres accord explicite.
5. **Automatisation** : n'ajouter aucune planification avant validation complete, et garder la diffusion en mode manuel.

## Statuts de validation et d'envoi
- Nouvelle ligne : `A_VALIDER`, `NON_ENVOYE`.
- Une diffusion n'est eligibile que si la validation est `VALIDE`, avec `valide_par` et `date_validation`, et un `resume_ia` non vide.
- Apres succes d'envoi, `ENVOYE` et `date_envoi` ; en cas d'echec SMTP, `ERREUR_ENVOI`.
- Des envois SMTP peuvent avoir ete remis au serveur alors que la mise a jour Google Sheets echoue ; une prevention absolue des doubles envois exige un mecanisme supplementaire et des tests d'incident.

Ce document indique l'etat du code ; il ne certifie pas que les API reelles fonctionnent ni que les emails ont ete envoyes.
