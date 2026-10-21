# SmartOps — Contrat applicatif de l'API v1

Version 0.2 — spécification cible. Les routes métier ci-dessous ne sont pas encore implémentées.
Référence : [conception détaillée](conception_detaillee.md).

## Socle technique disponible

L'API implémente actuellement `/health`, `POST /api/v1/system/probes` et
`GET /api/v1/system/events`. Les deux dernières routes servent exclusivement à
vérifier la persistance et le transport SSE. Ce flux utilise le temps réel système,
ne traite pas RCAEval et ne propose pas la reprise d'événements historiques.
Le paramètre optionnel `samples` (1 à 10) permet de finir le flux pour les tests.
Le flux de run décrit plus bas sera une route différente, avec ses propres
identifiants persistants et le temps simulé. La documentation `/docs` fait foi
pour les routes exécutables.

## Conventions

- Préfixe : `/api/v1`, sauf le contrôle de disponibilité `/health`.
- JSON UTF-8, sauf la route d'événements en `text/event-stream` ; identifiants UUID opaques.
- Temps des observations : entiers Unix UTC en millisecondes, suffixe `_ms`.
  Temps système d'une opération utilisateur : date ISO 8601 UTC, suffixe `_at`.
- Les valeurs numériques JSON doivent être finies. Valeur inconnue : `null` avec
  un état de disponibilité ; pas de `NaN`, d'infini ou de zéro ajouté par défaut.
- Les collections sont ordonnées de façon stable et paginées, sauf liste courte
  des scénarios. `limit` vaut 100 par défaut, maximum 500.
- Une requête de consultation ne modifie jamais le curseur ni l'état du détecteur.
- Les réponses publiques n'incluent pas les labels, heures d'injection, répétitions,
  noms des dossiers originaux ou chemins du système de fichiers.

## Routes

| Méthode | Route | Entrée / sortie principale |
|---|---|---|
| GET | `/health` | État du service et version du moteur ; 200 si disponible, 503 si stockage indisponible |
| GET | `/api/v1/scenarios` | Liste des scénarios préparés : identifiant, nom neutre, bornes temporelles et signaux disponibles |
| POST | `/api/v1/runs` | Créer une exécution avec `request_id`, `scenario_id`, `speed` et `detector_config_id` |
| GET | `/api/v1/runs/{run_id}` | État confirmé, phase, curseur, couverture, paramètres et dernière erreur publique |
| GET | `/api/v1/runs/{run_id}/events` | Flux SSE de changements confirmés, sans données futures ni annotations |
| POST | `/api/v1/runs/{run_id}/commands` | `command_id` et `action` : start, pause, resume ou stop |
| GET | `/api/v1/runs/{run_id}/metrics` | `service`, `metric`, `from_ms`, `to_ms`, `limit`, `cursor` ; points observés dans le passé disponible |
| GET | `/api/v1/runs/{run_id}/logs` | `service`, `from_ms`, `to_ms`, `limit`, `cursor` ; événements disponibles, lignes répétées conservées |
| GET | `/api/v1/runs/{run_id}/incidents` | Incidents ordonnés par ouverture, filtrage facultatif par état de suivi |
| GET | `/api/v1/incidents/{incident_id}` | Alertes, dernier diagnostic, couverture et acquittement |
| GET | `/api/v1/incidents/{incident_id}/diagnoses` | Versions du diagnostic disponibles, classées par instant d'analyse |
| GET | `/api/v1/evidence/{evidence_id}` | Extrait ou points ayant motivé une hypothèse, date de disponibilité et identifiant de provenance opaque |
| POST | `/api/v1/incidents/{incident_id}/acknowledgement` | Acquittement idempotent ; ne modifie ni le suivi technique ni le diagnostic |
| GET | `/api/v1/incidents/{incident_id}/report` | Export JSON autonome : incident, preuves, diagnostics, procédures et configuration |

Les routes d'incident et de preuve retrouvent le run associé et appliquent son
curseur confirmé. Une preuve future ou non encore disponible n'est pas consultable.
Les erreurs de lecture ne renvoient pas de trace d'exception ni de chemin brut.

Le rapport d'évaluation est un fichier agrégé produit hors ligne. La première
version de l'API ne déclenche pas d'évaluation ni ne distribue d'annotations.

## Création d'une exécution

Requête d'exemple, avec identifiants illustratifs :

```json
{
  "request_id": "4e1e94e2-2908-4d34-823a-3b9ecbb61420",
  "scenario_id": "38755176-74a9-4e8c-b4ea-d41617c61be1",
  "speed": 10,
  "detector_config_id": "robust-reference-v1-development"
}
```

`speed` est un nombre positif entre 1 et 60. Une configuration doit exister dans
le registre du backend. La configuration d'exemple non validée n'est pas une
configuration utilisable pour annoncer des résultats de test.

Première création : HTTP 201. Même `request_id` et même contenu : HTTP 200 avec
le même run. Même clé et contenu différent : HTTP 409.

Réponse structurelle d'exemple :

```json
{
  "id": "9af98449-aa1d-43e3-b090-4d0e3bb312d4",
  "scenario_id": "38755176-74a9-4e8c-b4ea-d41617c61be1",
  "status": "created",
  "phase": "pending",
  "cursor_ms": null,
  "speed": 10,
  "detector_config_id": "robust-reference-v1-development",
  "engine_version": "0.1.0",
  "created_at": "2026-10-21T12:00:00Z"
}
```

La version du moteur et les dates ci-dessus sont illustratives, pas un état actuel
de l'application.

## États et commandes

| État courant | Commande ou événement | État obtenu |
|---|---|---|
| created | start, ressources disponibles | running |
| running | pause, après confirmation du pas courant | paused |
| paused | resume | running |
| created, running ou paused | stop | stopped |
| running | Fin des observations | completed |
| running | Erreur bloquante | failed |
| running ou paused | Redémarrage du backend | interrupted |

`stopped`, `completed`, `failed` et `interrupted` sont terminaux : créer une nouvelle
exécution pour recommencer. La phase analytique vaut `pending`, `initializing`
ou `monitoring` et est distincte de l'état de relecture.

Une seule exécution peut être running ou paused à la fois. Un second start est
refusé avec HTTP 409. Une commande de pause attend la frontière du pas courant :
la réponse confirme un curseur qui ne bougera plus jusqu'à resume.

Une commande comporte un `command_id` UUID. Répéter le même identifiant et la même
commande retourne son résultat enregistré ; réutiliser la clé pour une autre
action est un conflit. La réponse enregistrée décrit l'application de cette
commande ; l'interface relit ensuite le run pour connaître son état actuel.
Une nouvelle pause sur un run déjà paused et un nouvel arrêt sur un run déjà
stopped sont des opérations sans effet avec HTTP 200. Une autre transition non
prévue donne HTTP 409 ; une action inconnue donne HTTP 422.

## Consultations temporelles et pagination

`to_ms` est borné au curseur confirmé. Une demande au-delà du curseur ne retourne
pas le futur et indique la borne effective. `from_ms > to_ms` est refusé avec
HTTP 422. Avant le premier pas, les consultations sont vides avec une borne effective
nulle, plutôt qu'un aperçu du fichier complet.

Une réponse de collection comprend `items`, `effective_to_ms` et `next_cursor`.
Le token de pagination est opaque et fixe la borne temporelle de la première page
ainsi que la dernière position retournée. Si la relecture avance entre deux pages,
la collection parcourue reste la même. Le token est lié au run et aux filtres ;
le réutiliser avec d'autres filtres est refusé. À filtres et instant identiques,
l'ordre des logs est `(event_time_ms, position_source_opaque)`.

La pagination des métriques n'interpole pas les points. Une série comportant des
lacunes fournit aussi une couverture et des états `missing` ou `insufficient_data`.
Une série absente ne devient pas une série de zéros. Une demande de service ou
métrique inconnue retourne HTTP 404.

## Notifications SSE

`GET /api/v1/runs/{run_id}/events` notifie les changements de ressources via un flux
SSE. Les commandes restent des requêtes POST et les détails sont obtenus par GET.
Types d'événements : `run.updated`, `incident.updated` et `diagnosis.updated`.
Ils portent le run, les identifiants des ressources concernées et le curseur confirmé,
sans recopier les logs ni transporter de données au-delà du curseur.

Chaque événement possède un `id` croissant issu de `run_events`, écrit dans la
transaction du changement et publié après commit. Une connexion sans
`Last-Event-ID` reçoit un instantané public du run et la séquence correspondante,
puis les événements suivants. Cet instantané et la séquence sont lus de façon
cohérente pour ne pas perdre un événement entre abonnement et consultation.

Une reconnexion avec `Last-Event-ID` reprend les événements strictement suivants,
filtrés sur le même run. Les événements sont conservés pendant la vie du run.
Un identifiant inconnu ou issu d'un autre run renvoie 409 ; le client relit alors
les ressources et recommence sans cet identifiant. Un commentaire de maintien
de connexion est envoyé environ toutes les 15 secondes réelles, même en pause.

Le frontend déduplique par identifiant, regroupe les notifications de curseur pour
limiter les requêtes de courbes et invalide les entrées TanStack Query concernées.
Il consulte les détails après un événement ; l'événement n'est pas une seconde
source de vérité. Lors d'un état terminal, il effectue une dernière consultation
et ferme la connexion pour éviter une boucle de reconnexion automatique.

La disparition de la connexion n'arrête pas le run. Une consultation périodique
bornée permet un fonctionnement dégradé pendant la reconnexion. Le proxy frontend
doit relayer le flux sans cache et sans attendre sa fin ; ce comportement sera
vérifié dans les tests d'intégration.

## Contenu minimal d'un diagnostic

| Champ | Sens |
|---|---|
| id, incident_id, version | Identité et historique |
| analysis_ms | Dernier instant disponible lors de cette analyse |
| status | `hypothesis` ou `insufficient_evidence` |
| candidates | Services ordonnés, score, famille de score et indicateurs d'ex æquo |
| hypotheses | Mécanismes possibles, avec références aux preuves ; peut être vide |
| evidence_ids | Indices consultables, tous disponibles à analysis_ms |
| coverage | Métriques éligibles et disponibilité des logs/traces |
| limitations | Données absentes, limites du mécanisme ou ambiguïtés |
| recommendations | Procédures identifiées, versions, justification et vérifications |

Un score est une valeur de classement et non une probabilité. Une abstention
peut conserver des observations utiles, sans annoncer un responsable certain.
Le texte des hypothèses ne mentionne jamais la cause connue par l'évaluateur.

## Erreurs

Format applicatif à implémenter :

```json
{
  "error": {
    "code": "RUN_STATE_CONFLICT",
    "message": "Cette exécution ne peut pas être reprise dans son état actuel.",
    "request_id": "f6228651-60b3-416b-ad77-3dfce419a94e"
  }
}
```

Codes HTTP : 404 pour ressource inconnue, 409 pour transition ou clé incompatible,
422 pour paramètres invalides, 503 pour une dépendance requise indisponible.
Les gestionnaires FastAPI normaliseront aussi les erreurs de validation dans ce
format. Les détails techniques seront consignés côté backend avec le request_id.

## Première tranche à implémenter

Commencer par `/health`, les scénarios, la création/consultation des runs, les
commandes, les métriques et les incidents. Le contrat complet guide la suite ;
la documentation OpenAPI générée ne présentera que les routes réellement disponibles.
