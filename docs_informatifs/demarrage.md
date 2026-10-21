# Démarrer le socle SmartOps

Cette première tranche vérifie Next.js, FastAPI, PostgreSQL et un flux SSE réel.
Elle n'effectue pas encore de détection d'anomalies sur RCAEval.

## Avec Docker Compose

Prérequis : Docker Desktop démarré avec son moteur Linux. Depuis la racine du dépôt :

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
docker compose ps
```

- Interface : <http://localhost:3000>.
- API et état de la base : <http://localhost:18000/health>.
- Documentation des routes réellement implémentées : <http://localhost:18000/docs>.

Compose attend PostgreSQL, exécute la migration Alembic, démarre le backend puis
le frontend. Le rôle `migrate` est une tâche ponctuelle : sa fin avec code 0 est normale.
La base demeure dans le volume `smartops_postgres_data`.

Les identifiants de `.env.example` sont des exemples publics pour un usage local.
Le fichier `.env` reste hors de Git. Si vous modifiez le mot de passe, adaptez
aussi `DATABASE_URL` pour le lancement hors conteneur, en encodant les caractères
réservés d'une URL. Changer une variable après création du volume ne change pas
automatiquement le mot de passe du compte PostgreSQL existant.

## Interface de supervision

1. **Service applicatif** : disponibilité issue d'une requête HTTP.
2. **Stockage** : disponibilité confirmée par le backend.
3. **Connexion live** : réception des événements au travers du proxy Next.js.
4. **Courbe** : temps des requêtes réellement mesuré depuis le navigateur,
   contrôle SQL inclus. Il ne s'agit pas de métriques issues du dataset.

Une base indisponible provoque un état dégradé, pas un faux indicateur vert.
Les noms des technologies, le dataset et le contexte académique ne figurent pas
dans l'interface. La vérification de persistance reste accessible dans les tests
et via `POST /api/v1/system/probes` dans la documentation de l'API ; aucun bouton
de test ni identifiant technique n'est présenté à l'utilisateur.

## Développement sans conteneuriser l'application

Prérequis : uv, Node.js compatible avec Next.js et Docker pour PostgreSQL.

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up -d postgres
uv sync --locked
uv run --no-sync alembic upgrade head
uv run --no-sync uvicorn smartops.api:app --host 127.0.0.1 --port 18000
```

Dans un deuxième terminal, depuis `frontend/` :

```powershell
npm ci
npm run dev
```

Le proxy utilise `http://127.0.0.1:18000` par défaut ; le conteneur reçoit son
adresse interne via `BACKEND_URL`. Le navigateur utilise toujours le chemin de
même origine `/api/backend/`. Les fichiers de dépendances verrouillés sont
`uv.lock` et `frontend/package-lock.json`.

## Vérifications

Tests unitaires, sans base :

```powershell
uv run --no-sync pytest -m "not integration" -q
```

Tests PostgreSQL, avec la base locale dédiée au projet démarrée :

```powershell
$env:TEST_DATABASE_URL = $env:DATABASE_URL
uv run --no-sync pytest -q
```

`DATABASE_URL` doit ici être exporté dans le terminal ; le fichier `.env` n'est
pas automatiquement chargé par PowerShell. Pour réutiliser la configuration du
projet sans afficher sa valeur, on peut aussi lancer :

```powershell
uv run --no-sync python -c "import os,pytest; from smartops.config import Settings; os.environ['TEST_DATABASE_URL']=Settings().database_url.get_secret_value(); raise SystemExit(pytest.main(['-q']))"
```

Les tests créent des schémas temporaires aux noms générés puis les suppriment.
Ils ne vident pas les tables existantes. Sans `TEST_DATABASE_URL`, les tests
d'intégration sont signalés comme ignorés, pas présentés comme réussis.

Vérification du frontend, depuis `frontend/` :

```powershell
npm run build
npx playwright install chromium
npm run test:e2e
```

Les tests navigateur supposent l'application démarrée sur le port 3000 avec
un backend et une base disponibles. `E2E_BASE_URL` permet de changer cette adresse.
Les tests vérifient les états et l'absence de détails internes. Une capture est enregistrée
dans `reports/socle-integration.png`.

Si le téléchargement de Chromium est indisponible mais Microsoft Edge est déjà
installé, le même test peut utiliser ce navigateur, sans ouvrir le profil personnel :

```powershell
$env:PLAYWRIGHT_CHANNEL = "msedge"
npm run test:e2e
```

Le workflow GitHub Actions exécute les tests backend avec PostgreSQL, construit
le frontend et lance les parcours navigateur. Il sera exécuté à la publication
du commit ; sa présence dans le dépôt ne constitue pas une exécution distante.

## Arrêt et diagnostic

```powershell
docker compose logs --tail 80 backend frontend migrate
docker compose stop
```

L'arrêt conserve la base et les images. Si `docker info` ne répond pas, vérifier
d'abord Docker Desktop. Si `/health` retourne 503, vérifier PostgreSQL et la tâche
de migration. Si le flux SSE reste déconnecté, vérifier la connexion au backend
et le proxy de l'interface. Les erreurs publiques ne révèlent pas la chaîne de
connexion ni les messages du pilote.
