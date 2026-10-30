# cnamsign

Automatisation de l'émargement sur la plateforme CnamSignE à partir des codes reçus par e-mail sur Outlook Le Cnam.

## Prérequis

### 1. Boîte de réception Outlook

Dans Outlook Web ([outlook.office.com](https://outlook.office.com)) :

1. Créer un sous-dossier nommé `Emargements` (sans accent, E majuscule et s à la fin).
2. Créer une règle de boîte de réception (Paramètres > Courrier > Règles > *Ajouter une nouvelle règle*) :
   - **Nom de la règle** : `Emargements`
   - **Conditions** :
     - **De** : `No-reply IDS`
     - **L'objet contient** : `Emargement`
   - **Action** :
     - **Déplacer vers** : le dossier `Emargements`
   - **Options** : cocher *Ne plus traiter de règles*

![Configuration de la règle Outlook](docs/images/regle_outlook.png)

Si un autre nom de dossier est utilisé, il suffit de le renseigner dans la variable `OUTLOOK_FOLDER` du fichier `.env`.

### 2. Plateforme CnamSignE

Sur la plateforme CnamSignE (cnamsigne.lecnam.net) :

1. Se connecter avec vos identifiants Le Cnam et saisir votre code PIN.
2. Enregistrer au préalable votre signature manuscrite :
   - Cliquer sur votre nom en haut à droite pour ouvrir le menu utilisateur.
   - Sélectionner **Signature enregistrée**.
   - Tracer et sauvegarder votre signature.

Cette signature sera automatiquement réutilisée par le script lors de la validation (*« Utiliser la signature enregistrée »*).

## Configuration

Copier le template de configuration :

```bash
cp .env.example .env
```

Renseigner les variables dans `.env` :

```env
EMAIL=prenom.nom.auditeur@lecnam.net
PASSWORD=mon_mot_de_passe
PIN_CODE=1234
OUTLOOK_FOLDER=Emargements
```

- `EMAIL` : adresse e-mail Le Cnam (commune à Outlook et CnamSignE).
- `PASSWORD` : mot de passe du compte Le Cnam (SSO Shibboleth).
- `PIN_CODE` : code PIN secret à saisir sur le clavier virtuel pour valider l'émargement.
- `OUTLOOK_FOLDER` : nom du dossier dans lequel sont rangés les mails d'émargement.

## Tests préalables

Avant de lancer le démon en continu, des scripts situés dans `tests/` permettent de tester chaque étape indépendamment.

### 1. Tester la lecture du mail
Vérifie la connexion à Outlook Web, l'accès au dossier et l'extraction du dernier code à 6 chiffres :

```bash
docker compose run --rm cnamsign python tests/test_mail.py
```

### 2. Tester la connexion SSO
Vérifie la connexion à CnamSignE et enregistre une capture d'écran dans `screenshots/test_login_result.png` :

```bash
docker compose run --rm cnamsign python tests/test_login.py
```

### 3. Tester la signature d'émargement
Vérifie la saisie du code de session, le choix de la signature et la validation :

```bash
docker compose run --rm cnamsign python tests/test_sign.py [CODE_6_CHIFFRES]
```

Ou en local avec Python :

```bash
python tests/test_sign.py [CODE_6_CHIFFRES]
```

## Déploiement Docker

Pour construire et lancer le conteneur en tâche de fond :

```bash
docker compose up -d --build
```

Pour consulter les logs d'exécution en direct :

```bash
tail -f logs.txt
# ou via Docker :
docker compose logs -f --tail 50
```

Pour arrêter le conteneur :

```bash
docker compose down
```

Le profil navigateur (cookies, cache et tokens de session) est stocké localement dans `browser_profile/` pour éviter les ré-authentifications systématiques.
