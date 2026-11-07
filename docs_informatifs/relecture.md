# Relecture SMD disponible

Préparer avec `uv run --no-sync python scripts/prepare_smd.py`, puis lancer Docker Compose.
L’interface propose les 28 machines et leurs 38 variables, regroupées en CPU, mémoire,
disque et réseau. La cadence règle le nombre d’observations présentées par seconde réelle.
Les commandes sont lancer, pause, reprendre et arrêter. Une seule lecture peut être active.

Les courbes ont un axe d’observation entier commençant à zéro et un axe de valeurs
normalisées de 0 à 1. La fenêtre couvre au plus 500 observations. Le tableau présente
les huit dernières valeurs de la variable sélectionnée. Aucun pourcentage physique,
aucune date ou log système n’est ajouté. Le détecteur robuste analyse les 38 variables, indépendamment de la courbe affichée.
Les alertes et leurs mesures justificatives sont consultables sous les graphiques.

Les alertes actives sont fermées comme « lecture arrêtée », « fin de lecture » ou
« lecture interrompue » lorsque la lecture se termine ; ces états ne signifient
pas que la machine est revenue dans sa plage. Voir [la détection](detection.md).

Les labels restent dans `data/evaluation-smd`. Le backend monte seulement
`data/monitoring-smd`, qui contient les métriques de test et leurs références
séparées d’apprentissage. Le lecteur courant charge seulement les métriques du test.
Les requêtes ne dépassent pas le curseur confirmé. La pagination fixe les bornes et
signe son jeton ; les jetons sont invalidés au redémarrage. Le SSE reprend avec
`Last-Event-ID`, et une consultation périodique de secours maintient l’état de l’interface.

Le curseur et les événements sont persistés atomiquement dans PostgreSQL. Les clés
UUID rendent les commandes idempotentes. Un redémarrage interrompt explicitement
une lecture active ; le moteur ne reprend pas une horloge interrompue implicitement.
