# SmartOps — Agent de monitoring intelligent

Projet en binôme pour la matière « Développement et déploiement d'applications intelligentes ».

## Décision initiale

Le jeu de données principal est **RCAEval, sous-ensemble RE2-OB (Online Boutique)** :
90 expériences de panne, métriques, logs, traces distribuées et service responsable annoté.
La version est figée dans [config/dataset.json](config/dataset.json).

Lire [l'étude et la décision](docs_informatifs/choix_dataset.md) avant de développer l'agent.
La [conception préliminaire](docs_informatifs/conception_preliminaire.md) définit le périmètre,
les cas d'utilisation, l'architecture et les critères de réception proposés.
La [conception détaillée](docs_informatifs/conception_detaillee.md) fixe les technologies,
les modules, les règles de relecture et de détection, ainsi que le modèle de stockage.
Le [contrat API v1](docs_informatifs/contrat_api_v1.md) décrit les routes à implémenter.
La [stratégie technologique](docs_informatifs/strategie_technologique.md) précise le
rendu visuel attendu et les extensions avancées proposées.
Les résultats bruts de l'audit sont dans `reports/`. Le socle applicatif est implémenté ;
la relecture du dataset, la détection et le diagnostic métier restent à développer.

## Lancer le socle applicatif

Avec Docker Desktop démarré, depuis la racine :

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
```

Interface : <http://localhost:3000>. API : <http://localhost:18000/docs>.
L'écran affiche la disponibilité des services, la latence et la synchronisation live.
Les vérifications techniques de persistance restent accessibles dans l'API et les tests.
Les courbes montrent des temps de réponse réellement mesurés ; elles ne rejouent pas encore RCAEval.
Voir [le guide de démarrage et de test](docs_informatifs/demarrage.md).
Le [rapport de validation](reports/validation_socle.md) décrit les builds, les cinq
tests backend et les deux tests navigateur effectivement exécutés.

## Stack applicative retenue

- Frontend dédié : **Next.js, React, TypeScript, Tailwind CSS et shadcn/ui**.
- Graphiques : **Apache ECharts** ; synchronisation : **TanStack Query et SSE**.
- Backend : **FastAPI et Pydantic** ; analyse : Python.
- Stockage : **PostgreSQL**, modèles SQLAlchemy, pilote Psycopg 3 et migrations Alembic ; télémétrie brute en Parquet.
- Livraison : Docker Compose, pytest, Playwright et GitHub Actions.

L'interface doit être une console d'observabilité conçue sur mesure. Streamlit est
exclu du projet à la demande de l'utilisateur. MLflow, OpenTelemetry et un diagnostic
orchestré avec LangGraph sont des extensions planifiées ou proposées, pas des composants
déjà installés ou implémentés.

## Reproduire l'étude

Python 3.11. Depuis la racine du projet :

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-audit.txt
.venv\Scripts\python.exe scripts/inspect_dataset_sources.py
.venv\Scripts\python.exe scripts/download_audit_sample.py
.venv\Scripts\python.exe scripts/audit_datasets.py
.venv\Scripts\python.exe scripts/download_audit_sample.py --all-ob-metrics-logs
.venv\Scripts\python.exe scripts/audit_datasets.py --selected
.venv\Scripts\python.exe scripts/summarize_audit.py
.venv\Scripts\python.exe scripts/plot_audit_sample.py
```

Les deux premières étapes téléchargent des sources publiques ; aucun compte ni clé API n'est nécessaire.
Le téléchargement reprend les fichiers déjà complets. Un échec réseau est signalé ; relancer la commande.
Les téléchargements sont stockés sous `data/`, exclu de Git. Les manifestes contiennent les URL,
la révision et les empreintes SHA-256. Les empreintes assurent la traçabilité locale ; elles ne
remplacent pas une vérification d'intégrité auprès de l'éditeur.

## Fichiers utiles

- `reports/dataset_inventory.csv` : inventaire des 735 cas depuis l'index éditeur.
- `reports/sample_quality.csv` : audit de 12 cas, six Sock Shop et six Online Boutique.
- `reports/sample_audit.json` : mesures détaillées, dont la qualité des traces échantillonnées.
- `reports/selected_quality.csv` : audit des métriques/logs des 90 cas retenus.
- `reports/selected_audit.json` : détail de cet audit complet ; traces uniquement comptées depuis l'index.
- `reports/selected_summary.json` : bilan, vérification des empreintes et couverture temporelle.
- `reports/incident_examples.png` et `.pdf` : trois séries réelles avant/après injection, sans interpolation.

## Prochaine étape

Brancher les scénarios préparés sur le socle : relecture déterministe, détection simple
et persistance d'un incident. Les routes de relecture et de diagnostic sont décrites
dans le contrat cible ; elles ne sont pas encore exposées par l'API.
Les paramètres de [monitoring.example.json](config/monitoring.example.json) sont des valeurs
initiales de conception, non validées expérimentalement. Aucun résultat de modèle n'est annoncé.
Les recommandations correctives viendront de procédures documentées : le dataset n'annote pas
la réussite d'actions de remédiation.
