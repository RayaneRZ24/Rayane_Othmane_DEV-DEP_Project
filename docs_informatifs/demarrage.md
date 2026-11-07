# Démarrage et vérification

SMD est le seul dataset, figé dans `config/dataset.json`.

```powershell
uv sync --locked
uv run --no-sync python scripts/download_smd.py
uv run --no-sync python scripts/download_smd.py --verify-only
uv run --no-sync python scripts/audit_smd.py
uv run --no-sync python scripts/prepare_smd.py
```

Les données restent sous `data/raw/SMD`. L’audit produit `reports/smd_*`. La préparation
vérifie les empreintes et publie les 28 machines sous `data/monitoring-smd`. Les
annotations restent sous `data/evaluation-smd`, hors du volume backend.

Avec Docker Desktop démarré :

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
docker compose up --build -d
```

Interface : <http://localhost:3000>. API : <http://localhost:18000/docs>.
PostgreSQL local : port 15432. Le backend monte seulement `data/monitoring-smd`, en
lecture seule. Si le registre est vide, aucune session ne peut être démarrée et
l’interface affiche un état vide sans série de substitution.

`uv run --no-sync pytest -q` lance les tests Python. Les tests PostgreSQL exigent
`TEST_DATABASE_URL` et créent des schémas isolés. Ne pas afficher ni enregistrer les secrets.
La CI prépare une petite fixture synthétique dans `data/monitoring-test` pour les
parcours du moteur générique. Cette fixture n’est pas SMD et ne sert pas à entraîner
ou évaluer un modèle. La production ne charge aucune fixture automatiquement.

## Évaluer le détecteur

```powershell
uv run --no-sync python scripts/evaluate_detector.py
```

Cette commande produit les prédictions avant de lire les annotations, puis écrit
`reports/detection_evaluation.json` et `.csv`. Elle ne change aucun seuil. Les profils
sont ajustés uniquement sur les références d’apprentissage préparées.

Comparer les deux candidats figés :
`uv run --no-sync python scripts/compare_detectors.py`.
Le script conserve le protocole et écrit `reports/detector_comparison.*`.
