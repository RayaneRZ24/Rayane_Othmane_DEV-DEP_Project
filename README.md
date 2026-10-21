# SmartOps — Agent de monitoring intelligent

Projet en binôme pour la matière « Développement et déploiement d'applications intelligentes ».

## Décision initiale

Le jeu de données principal est **RCAEval, sous-ensemble RE2-OB (Online Boutique)** :
90 expériences de panne, métriques, logs, traces distribuées et service responsable annoté.
La version est figée dans [config/dataset.json](config/dataset.json).

Lire [l'étude et la décision](docs_informatifs/choix_dataset.md) avant de développer l'agent.
La [conception préliminaire](docs_informatifs/conception_preliminaire.md) définit le périmètre,
les cas d'utilisation, l'architecture et les critères de réception proposés.
Les résultats bruts de l'audit sont dans `reports/`. L'application n'est pas encore développée.

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

Relire la conception préliminaire, puis détailler les contrats des modules et les choix techniques.
Implémenter ensuite une première chaîne : relecture, détection simple et rapport d'incident.
Les recommandations correctives viendront de procédures documentées : le dataset n'annote pas
la réussite d'actions de remédiation.
