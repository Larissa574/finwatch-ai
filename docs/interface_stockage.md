# FINWATCH AI — Module 3 : Stockage et organisation

## 1. Présentation

Le module 3 est chargé de stocker et d'organiser les publications collectées par FINWATCH AI.

Il utilise Google Sheets pour conserver les informations et permettre aux membres de l'équipe de les consulter.

**Mon travail consiste à :**
- enregistrer les publications collectées ;
- éviter les doublons ;
- conserver les informations originales ;
- recevoir les résultats de l'analyse IA ;
- préparer les publications pour la validation et la diffusion.

La collecte des informations est gérée par un autre module. L'analyse IA et l'envoi des newsletters ne sont pas réalisés par mon module de stockage.

## 2. Les fichiers du module

| Fichier | Rôle |
|---|---|
| `src/stockage.py` | Contient les fonctions qui enregistrent et mettent à jour les données |
| `src/importer_stockage.py` | Transfère les publications collectées vers Google Sheets |
| `src/test_stockage.py` | Vérifie le fonctionnement du stockage sans modifier la vraie base |
| `src/main.py` | Lance la collecte puis l'importation |
| `docs/interface_stockage.md` | Présente le fonctionnement du module |

Le fichier `.gitignore` protège notamment les identifiants Google en empêchant leur ajout normal au dépôt Git.

## 3. Organisation de Google Sheets

Le classeur utilisé s'appelle `FINWATCH_AI_BDD`. La feuille principale s'appelle `Publications`.

Elle contient 19 colonnes, réparties en quatre groupes :

- **Informations originales :** identifiant, titre, source, lien, dates, auteur, résumé original et type de document.
- **Analyse IA :** résumé IA, catégorie, innovation, application financière et impact potentiel.
- **Validation :** statut de validation, personne ayant validé et date de validation.
- **Diffusion :** statut d'envoi et date d'envoi.

Chaque publication possède un identifiant `id`. Cet identifiant permet de retrouver la bonne publication et d'éviter les doublons.

Les 19 colonnes doivent conserver les noms et l'ordre attendus par le programme.

## 4. Comment fonctionne le stockage ?

### A. Enregistrer une publication

La fonction `enregistrer(publication)` reçoit les informations d'une publication.

- Si son identifiant n'existe pas encore, elle crée une nouvelle ligne.
- Si son identifiant existe déjà, elle met à jour la ligne correspondante.
- Les champs vides ne remplacent pas les informations déjà enregistrées.
- Les statuts de validation et de diffusion sont protégés contre les modifications par cette fonction.

Une nouvelle publication reçoit deux statuts par défaut :

- `A_VALIDER` : une personne doit encore vérifier la publication.
- `NON_ENVOYE` : la publication n'a pas encore été diffusée.

### B. Recevoir l'analyse IA

La fonction `mettre_a_jour_analyse(analyse)` permet d'enregistrer les résultats fournis par le module d'analyse IA.

Elle peut mettre à jour cinq champs :

- `resume_ia`
- `categorie`
- `innovation`
- `application_financiere`
- `impact_potentiel`

Elle a besoin de l'identifiant exact d'une publication déjà présente dans Google Sheets.

**Important :** si l'identifiant n'existe pas, la fonction refuse la mise à jour au lieu de créer une nouvelle ligne. Elle ne doit pas modifier le titre, le résumé original ou les statuts de validation et de diffusion.

Le format exact des données échangées doit être confirmé avec le responsable du module IA.

### C. Trouver les publications à diffuser

La fonction `publications_a_diffuser()` recherche les publications qui ont été validées et qui ne sont pas encore envoyées.

Elle prépare la liste des publications candidates à la diffusion, mais n'envoie pas elle-même les newsletters.

## 5. Comment lancer le projet ?

Ouvrir PowerShell dans le dossier du projet :

```powershell
cd C:\Users\HP\Downloads\V\finwatch-ai
```

Pour lancer le pipeline principal :

```powershell
python src/main.py
```

Le pipeline exécute la collecte puis l'importation des publications dans Google Sheets.

Pour lancer les tests du stockage :

```powershell
python src/test_stockage.py
```

Le test utilise une feuille simulée. Il permet de vérifier certaines fonctions sans modifier les données réelles de Google Sheets.

Pour accéder au classeur, il faut également que Python, la bibliothèque `gspread`, les identifiants et les autorisations Google Sheets soient correctement configurés.

## 6. Sécurité

Les identifiants Google Sheets se trouvent localement dans :

`secrets/finwatch-sheets.json`

Ce fichier est confidentiel et ne doit jamais être envoyé sur GitHub.

La règle suivante dans `.gitignore` permet d'exclure le dossier :

```gitignore
secrets/
```

Avant de publier du code, il faut toujours vérifier les fichiers sélectionnés avec Git.

## 7. Ce qui a déjà été réalisé

- Le stockage dans Google Sheets est implémenté.
- La détection des publications déjà enregistrées est intégrée.
- La mise à jour des champs d'analyse IA est prévue par une fonction dédiée.
- Le pipeline principal exécute la collecte et l'importation.
- Des tests isolés du stockage ont été préparés et exécutés.
- Le code du module a été publié sur GitHub.

Une exécution du pipeline a également été rapportée comme réussie, avec l'ajout d'une nouvelle publication et la détection des doublons.

## 8. Ce qu'il reste à coordonner avec l'équipe

- Confirmer le format des données transmises par le module d'analyse IA.
- Tester l'intégration entre les modules.
- Vérifier le fonctionnement complet du processus de validation et de diffusion.

**Conclusion :** le module 3 sert de point central pour conserver les publications de FINWATCH AI. Il organise les données, limite les doublons et permet aux autres modules de retrouver les informations nécessaires à la suite du traitement.