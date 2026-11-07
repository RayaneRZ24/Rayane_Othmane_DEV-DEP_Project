# SmartOps — Supervision intelligente d’infrastructures informatiques

**SMD — Server Machine Dataset est le seul dataset retenu pour le projet et ses prochaines étapes.**
La version est figée dans [config/dataset.json](config/dataset.json), les variables dans
[config/smd_features.json](config/smd_features.json), et la décision dans
[choix_dataset.md](docs_informatifs/choix_dataset.md).

## Données

28 machines, 38 variables par machine : CPU, charge, mémoire, disque et réseau.
708 405 observations d’apprentissage et 708 420 observations de test.
Les valeurs sont normalisées ; les fichiers ne fournissent ni dates absolues,
ni logs système, ni traces distribuées. Les annotations sont réservées à l’évaluation.

```powershell
uv sync --locked
uv run --no-sync python scripts/download_smd.py
uv run --no-sync python scripts/audit_smd.py
uv run --no-sync python scripts/prepare_smd.py
```

`--verify-only` vérifie les 113 fichiers sans accès réseau. Les données sont dans
`data/raw/SMD`, la provenance dans `data/sources/SMD`, les rapports dans `reports/smd_*`.
Les données sont exclues de Git. La licence est dans [third_party/SMD-LICENSE.txt](third_party/SMD-LICENSE.txt).

## Application

Le socle Next.js/React, FastAPI, PostgreSQL et Docker Compose est disponible.
La relecture SMD est intégrée : 28 machines, 38 indicateurs par machine, familles
CPU/mémoire/disque/réseau, cadence de 1 à 60 observations par seconde, pause/reprise/arrêt.
Les courbes et le tableau présentent les valeurs normalisées jusqu’au curseur confirmé.
Le registre préparé est sous `data/monitoring-smd` ; les annotations sont isolées sous
`data/evaluation-smd`, jamais monté dans le backend. La cadence est celle de présentation,
pas une fréquence physique d’origine. Les dates ne sont pas inventées.
Deux méthodes sont disponibles avant lancement : **Par indicateur** (référence robuste)
et **Indicateurs combinés** (PCA). Le détecteur choisi analyse les 38 variables et persiste
les alertes et leurs mesures justificatives. Leur précision reste faible :
il sert de référence expérimentale, pas de garantie de panne. Voir
[la référence](docs_informatifs/detection.md) et
[la comparaison PCA](docs_informatifs/comparaison_detecteurs.md).

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
```

Interface : <http://localhost:3000>. API : <http://localhost:18000/docs>.
Voir [le guide de démarrage](docs_informatifs/demarrage.md).

## Prochaines étapes

1. Consolider une validation indépendante des résultats exploratoires.
2. Réduire les fausses alertes sans ajuster les seuils sur les annotations de test.
3. Regrouper les alertes en incidents et enrichir les explications.
4. Ajouter les recommandations vérifiables.

La [conception préliminaire](docs_informatifs/conception_preliminaire.md), la
[conception détaillée](docs_informatifs/conception_detaillee.md) et le
[contrat API](docs_informatifs/contrat_api_v1.md) distinguent le socle des fonctions prévues.

## Technologies

Next.js, React, TypeScript, Tailwind CSS, shadcn/ui, ECharts, TanStack Query ;
FastAPI/Pydantic ; PostgreSQL, SQLAlchemy, Psycopg 3, Alembic et Parquet ;
Docker Compose, pytest, Playwright et GitHub Actions.
