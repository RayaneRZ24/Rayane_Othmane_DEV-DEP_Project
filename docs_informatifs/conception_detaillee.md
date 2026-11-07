# Conception détaillée — SMD

## Socle disponible

Next.js/React/TypeScript, Tailwind CSS, shadcn/ui, ECharts et TanStack Query ;
FastAPI/Pydantic ; PostgreSQL/SQLAlchemy/Psycopg 3 et Alembic ; Docker Compose,
pytest, Playwright et GitHub Actions. Les dépendances sont figées par les lockfiles.

## Espaces de données

| Répertoire | Rôle |
|---|---|
| `data/raw/SMD` | Partitions originales, annotations et licence ; audit et préparation seulement |
| `data/sources/SMD` | Provenance et empreintes |
| `data/monitoring-smd` | Mesures préparées sans annotations et registre des 28 machines |
| `data/evaluation-smd` | Annotations réservées à l’évaluateur |

Le backend monte seulement le monitoring en lecture seule, sans partitions annotées.

## Adaptateur SMD disponible

`scripts/prepare_smd.py` vérifie la version et les empreintes sources, lit 38 colonnes
avec `config/smd_features.json`, préserve partitions et ordre, et conserve un index
zéro. Les UUID de séries sont stables pour la révision et le schéma.
Chaque série de test est dans `metrics.parquet`, sa référence d’apprentissage séparée
est dans `reference.parquet`. Les annotations binaires et d’attribution sont écrites
exclusivement dans l’espace d’évaluation. Le registre de schéma 2 est publié en dernier.

## Relecture disponible

Un seul run actif, pause/reprise/arrêt, clés d’idempotence et SSE persisté. L’horloge
monotone avance en observations entières, conserve les fractions et exclut le temps
de pause. Le curseur `cursor_index` est persisté ; la migration Alembic 0003 le nomme
explicitement. La cadence de 1 à 60 observations par seconde est une vitesse de
présentation. Une lecture ne fait pas avancer le curseur ; les requêtes de mesures
sont plafonnées au curseur confirmé. La fenêtre par défaut contient au plus les
500 dernières observations. Un redémarrage interrompt le run.

## Détection disponible

Le détecteur `robust-mad-v1` ajuste médiane et dispersion robuste sur les 80 premiers
pour cent de la partition d’apprentissage, puis calibre les seuils sur les 20 derniers.
Aucun label ni mesure de test ne participe à cet ajustement. Les paramètres sont
versionnés dans `smartops.detection.CONFIG`, pas chargés depuis le fichier de conception.

Trois écarts consécutifs déclenchent une alerte par variable. Cinq observations
consécutives dans la plage ferment l’alerte comme retour dans la plage. Une valeur
manquante ne démontre jamais un rétablissement. Toutes les observations entre deux
curseurs sont traitées, quelle que soit la vitesse de lecture. L’observation zéro
est aussi analysée. Curseur, état du détecteur, alertes et événement SSE sont persistés
dans la même transaction. Une erreur de stockage interrompt explicitement le run.

Le profil appris, son empreinte, l’état de persistance et le dernier index analysé
sont conservés dans le run. Les preuves incluent valeur, médiane, échelle, score,
seuil, bornes et observation de détection. Un arrêt ou une fin de lecture ne clôture
pas une alerte avec un faux état de rétablissement. Les lectures antérieures sans
profil ne sont pas analysées rétroactivement.

## Incidents et diagnostic à implémenter

Le regroupement entre variables et le diagnostic de cause restent à développer.
Une alerte actuelle indique un écart à examiner, sans certifier une cause ou une
panne. Les recommandations proviendront de procédures vérifiables. La comparaison
avec PCA est réalisée sous protocole figé : voir [la comparaison](comparaison_detecteurs.md).
La migration 0005 conserve le choix de méthode dans le run.

## Invariants

Absence de labels dans le détecteur et l’API ; aucune observation future ; partitions
séparées ; index stable ; pagination cohérente ; reproductibilité ; colonnes constantes prises en charge.
