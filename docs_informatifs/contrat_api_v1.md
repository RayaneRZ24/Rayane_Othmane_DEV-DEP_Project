# Contrat API v1 — SMD

`/docs` décrit les routes exécutables. Les mesures utilisent des index zéro, jamais
des dates artificielles. La vitesse est exprimée en observations par seconde réelle.

| Méthode | Route | Fonction |
|---|---|---|
| GET | `/health` | Disponibilité API et stockage |
| POST | `/api/v1/system/probes` | Vérification de persistance |
| GET | `/api/v1/system/events` | Vérification SSE du socle |
| GET | `/api/v1/scenarios` | Machines préparées, bornes, variables et unités normalisées |
| POST | `/api/v1/runs` | request_id, scenario_id, speed entre 1 et 60, detector_name optionnel |
| GET | `/api/v1/runs` | 50 derniers runs disponibles |
| GET | `/api/v1/runs/{id}` | État, machine_id, cursor_index, start_index, end_index |
| POST | `/api/v1/runs/{id}/commands` | command_id, action start/pause/resume/stop |
| GET | `/api/v1/runs/{id}/events` | SSE, reprise avec Last-Event-ID |
| GET | `/api/v1/runs/{id}/metrics` | feature, from_index, to_index, limit, cursor |
| GET | `/api/v1/runs/{id}/alerts` | Alertes et preuves, offset et limit (1 à 500) |

Une collection de mesures contient `items`, `effective_to_index`, `next_cursor`.
Chaque point contient `sample_index`, `value` et `observed`. La limite par défaut
et maximale est 500 ; sans borne initiale, les 500 dernières observations disponibles
sont sélectionnées. `feature` doit appartenir au dictionnaire public de la machine.
Les bornes négatives sont rejetées. Une borne finale future est plafonnée au curseur.
Avant lancement, la lecture renvoie une collection vide avec borne effective nulle.

Les réponses de supervision n’exposent ni labels, ni attributions de référence,
ni chemins locaux. SMD ne contient pas de logs système ; aucune route de logs
n’est exposée. Les routes d’incidents et d’explications seront ajoutées avec leurs modules.

Les UUID rendent créations et commandes idempotentes ; même clé et contenu différent :
409. Une seule lecture active, pause incluse. Les consultations ne font pas avancer
le curseur. Les jetons de pagination sont signés, liés à la série et aux filtres,
et fixent les bornes de lecture ; ils sont invalidés au redémarrage. Une exécution
active est interrompue au redémarrage. Les erreurs publiques n’exposent pas de secrets.

## Analyse et alertes

Le run expose `analyzed_index` et `detector_version` (nuls avant lancement ou pour
une lecture sans analyse). Un lancement exige une référence d’apprentissage complète ;
à défaut il renvoie 503 sans apprendre sur le test.

La route d’alertes retourne `items`, `total`, `active_count`, `cursor_index`,
`analyzed_index`, `detector_version`, `resource_counts` et `feature_counts`.
Le filtre optionnel `resource=cpu|memory|disk|network` s’applique à `items` et `total`.
`active_count` reste le nombre global d’alertes actives de la lecture.
`resource_counts` donne `{total, active}` pour chacun des quatre composants ;
`feature_counts` donne le total par indicateur (une clé absente vaut zéro).
Ces compteurs couvrent toute la lecture jusqu’au curseur, indépendamment du filtre
et de la page. Une alerte PCA est attribuée à son indicateur dominant, sans
compter plusieurs fois ses contributions. Une ressource inconnue renvoie 422.
Les résultats sont classés par détection
décroissante ; la pagination offset/limit affiche une liste live, à figer en pause
pour une navigation stable. Une preuve ne dépasse jamais le curseur confirmé.
Les états sont `active`, `recovered`, `stopped`, `completed` et `interrupted`.
Seul `recovered` signifie que cinq observations consécutives sont revenues dans la plage.
Les preuves contiennent les valeurs et statistiques de référence, jamais des labels.

## Choix de méthode

`detector_name` vaut `robust-mad-v1` par défaut ou `pca-joint-v1` pour la méthode
combinée. Le choix est conservé dans le run et entre dans la clé de contenu
idempotent. Une valeur inconnue est rejetée (422). Il ne peut pas changer pendant
un run : créer une nouvelle lecture après arrêt. Le run expose ce choix et la
version de profil effectivement ajustée. Les preuves PCA contiennent `method`,
les scores combinés, leurs seuils et les trois contributions principales. La
variable dominante sert à la navigation ; la plage individuelle est descriptive.


## Navigation des alertes

L’interface distingue le total d’alertes de l’indicateur affiché et celui de son
composant. Le filtre de la liste est indépendant du composant du graphique ;
changer ce filtre remet la pagination à zéro. « Afficher sur le graphique »
sélectionne l’indicateur et la fenêtre de 200 observations avant / 100 après
la détection, limitée aux observations déjà lues. Le repère indique la détection
sélectionnée. Le retour aux dernières observations rétablit la fenêtre courante.
Les autres repères correspondent uniquement aux alertes de la page courante ;
les compteurs ne sont pas limités à cette page.
