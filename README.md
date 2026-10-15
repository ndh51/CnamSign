# cnamsign

Automatisation de l'émargement sur la plateforme CnamSignE à partir des codes reçus par e-mail sur Outlook Le Cnam.

## Prérequis Outlook

Dans Outlook Web (outlook.office.com) :

1. Créer un sous-dossier nommé `Emargements` (sans accent, E majuscule et s à la fin).
2. Créer une règle de boîte de réception :
   - Condition : l'objet contient `émarger` ou `code de session`
   - Action : déplacer le message vers le dossier `Emargements`

Si un autre nom de dossier est utilisé, il suffit de le renseigner dans la variable `OUTLOOK_FOLDER` du fichier `.env`.

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

Avant de lancer le démon en continu, deux scripts permettent de tester chaque étape indépendamment.

### 1. Tester la lecture du mail
Vérifie la connexion à Outlook Web, l'accès au dossier et l'extraction du dernier code à 6 chiffres :

```bash
docker compose run --rm cnamsign python test_mail.py
```

### 2. Tester la connexion SSO
Vérifie la connexion à CnamSignE et enregistre une capture d'écran dans `screenshots/test_login_result.png` :

```bash
docker compose run --rm cnamsign python test_login.py
```

### 3. Tester la signature d'émargement
Vérifie la saisie du code de session, le choix de la signature et la validation :

```bash
docker compose run --rm cnamsign python test_sign.py [CODE_6_CHIFFRES]
```

Ou en local avec Python :

```bash
python test_sign.py [CODE_6_CHIFFRES]
```

## Déploiement Docker

Pour construire et lancer le conteneur en tâche de fond :

```bash
docker compose up -d --build
```

Pour consulter les logs d'exécution :

```bash
docker compose logs -f
```

Pour arrêter le conteneur :

```bash
docker compose down
```

Le profil navigateur (cookies, cache et tokens de session) est stocké localement dans `browser_profile/` pour éviter les ré-authentifications systématiques.
