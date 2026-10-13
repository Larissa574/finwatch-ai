# FINWATCH AI — Installation inscription et automatisation

## Page publique (Google Apps Script)

1. Ouvrir https://script.google.com et créer un projet.
2. Copier `apps_script/Code.gs` dans le fichier `Code.gs` et le HTML de `apps_script/Index.html` dans un fichier Apps Script nommé `Index`.
3. Dans les propriétés du script, définir :
   - `SHEET_ID` : ID du classeur FINWATCH_AI_BDD ;
   - `FINWATCH_HMAC_SECRET` : secret aléatoire long, privé.
4. Déployer une application web : exécution comme propriétaire du script, accès public.
5. Copier l'URL HTTPS du déploiement se terminant en `/exec` dans le secret GitHub `FINWATCH_WEBAPP_URL`.

Le formulaire n'envoie pas d'email de confirmation. Le consentement par case cochée est obligatoire, mais ne vérifie pas la propriété de l'adresse : protéger le formulaire contre les abus avant un lancement public large.

## GitHub Actions

Configurer ces *secrets* dans Settings > Secrets and variables > Actions :
- `GOOGLE_SHEET_ID`
- `GOOGLE_CREDENTIALS_JSON` (JSON du compte de service)
- `IA_API_KEY`
- `SMTP_USER`
- `SMTP_PASSWORD` (mot de passe d'application)
- `FINWATCH_WEBAPP_URL`
- `FINWATCH_HMAC_SECRET` (même valeur que Apps Script)

Configurer ces *variables* :
- `GEMINI_MODEL` : modèle actuellement disponible pour votre compte ;
- `FINWATCH_AUTORISER_ENVOI` : `NON` par défaut.

La collecte et l'analyse sont planifiées quotidiennement à 06:00 UTC, sans envoyer de bulletin.
La diffusion est planifiée le vendredi à 08:00 UTC et reste en mode simulation tant que `FINWATCH_AUTORISER_ENVOI` n'est pas `OUI`.

## Données et sécurité

Le script initialise les onglets `Abonnes` et `Journal envois` lorsque nécessaire.
Une publication doit être `VALIDE`, dotée d'un validateur et d'une date, et être encore `NON_ENVOYE`.
La newsletter contient un lien de désinscription signé unique à chaque adresse.
La liste de diffusion est recalculée avant chaque envoi individuel.

**Prudence** : le lien se désinscrit à l'ouverture (GET), ce qui peut être déclenché par des systèmes de prévisualisation ou de filtrage des emails. Avant diffusion publique, prévoir une page de confirmation avec un bouton POST pour éviter les désinscriptions involontaires. Le formulaire doit aussi être protégé contre les abus. Les campagnes enregistrent les transmissions SMTP, pas l'arrivée garantie dans la boîte de réception.

Le journal suit chaque adresse et une empreinte des IDs des publications. Il ne remplace pas une base transactionnelle pour les gros volumes. Les publications restent `NON_ENVOYE` ; le journal par campagne assure la déduplication au niveau des abonnés actuels.

## Tests sûrs

```powershell
git pull origin main
python -m pytest tests -v
python src/diffusion_automatique.py
```

N'utiliser `--send` qu'après avoir confirmé le consentement des destinataires, la configuration SMTP et le bon fonctionnement des désinscriptions.
