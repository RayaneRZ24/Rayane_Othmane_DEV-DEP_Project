# SmartOps — Stratégie technologique et direction visuelle

21 octobre 2026. Décision de conception ; le socle d'intégration est maintenant implémenté.

## Objectif retenu

Développer une application web aboutie avec une interface dédiée, des visualisations
interactives et une architecture démontrable. L'utilisateur exclut Streamlit.
Les décisions de conception antérieures sont remplacées par celles-ci lorsqu'elles
concernent le frontend, la persistance et le rafraîchissement des résultats.

La modernité du projet sera visible dans son expérience utilisateur, la qualité
de ses contrats, son observabilité et ses résultats mesurés. L'ancienneté d'une
technologie ne suffit pas à juger sa pertinence : PostgreSQL, Python et les
méthodes statistiques restent utiles dans cette architecture.

## Socle retenu pour l'application

| Besoin | Choix | Apport concret |
|---|---|---|
| Frontend web | Next.js App Router, React, TypeScript | Pages structurées, interface interactive et contrats de données typés |
| Identité visuelle | Tailwind CSS et shadcn/ui | Composants personnalisables, système d'espacements, thèmes et états cohérents |
| Visualisation | Apache ECharts | Courbes synchronisées, zoom temporel, comparaison et annotations d'incidents |
| Données du frontend | TanStack Query | Cache isolé par run, pagination, états de chargement et actualisation ciblée |
| Actualisation | REST pour consulter/commander, SSE pour notifier | Évolution des courbes et incidents sans rechargement complet de page |
| Backend | FastAPI et Pydantic | API validée et contrat OpenAPI exploitable pour les types frontend |
| Résultats persistants | PostgreSQL, SQLAlchemy, Psycopg 3, Alembic | Connexion, transactions, JSONB, historique partagé et évolution explicite du schéma |
| Analyse | Python, NumPy, pandas, PyArrow | Calcul reproductible sur les données Parquet déjà auditées |
| Qualité et livraison | pytest, Playwright, Docker Compose, GitHub Actions | Tests moteur/navigateur et lancement reproductible |

PostgreSQL est proposé pour un service applicatif qui conserve des résultats
consultables par plusieurs sessions et dont le schéma va évoluer. Il ajoute un
service à administrer ; le volume actuel des données n'impose pas à lui seul ce
changement. Les signaux bruts restent en Parquet, sans recopier systématiquement
les millions de logs dans la base relationnelle.

Les nouvelles dépendances seront verrouillées après installation et vérification
de compatibilité. L'environnement d'audit existant est conservé pour reproduire
l'étude initiale, indépendamment du futur environnement applicatif.

## Direction visuelle à réaliser

L'objectif est une console d'observabilité professionnelle, avec une densité
d'information maîtrisée. Ces éléments définissent le brief de conception :

- Navigation latérale avec Surveillance, Incidents et Évaluation ; espace principal
  suffisamment large pour les séries temporelles.
- Thème sombre travaillé et thème clair, contrastes lisibles, typographie cohérente
  et chiffres alignés pour les mesures. Les couleurs d'état ont toujours un libellé.
- Barre temporelle persistante : curseur, vitesse et commandes de relecture,
  avec une distinction nette entre horloge simulée et date système.
- Graphiques synchronisés et sélection de plage ; marqueurs d'alerte uniquement
  sur les événements déjà observés. Zoom et filtres sans perdre le contexte du run.
- Explorateur de logs avec recherche, filtres par service et navigation vers les
  preuves ; pagination pour éviter d'afficher tout le dataset.
- Vue d'incident construite autour de la chronologie, des suspects et de leurs
  preuves, avec un panneau de détail consultable sans quitter l'analyse.
- Chargement, données absentes, perte de connexion et abstention du diagnostic
  possèdent des états visuels explicites. Les mouvements restent discrets et
  respectent la préférence de réduction des animations.
- Navigation clavier, adaptation aux tailles d'écran et contrôle des contrastes
  font partie de la réception de l'interface.

Une carte de dépendances pourra enrichir la démonstration sur les cas tracés.
Elle montrera uniquement les relations observées, avec leur couverture ; une
relation non observée ne sera pas représentée comme une dépendance certaine.

Une première page de diagnostic du socle est implémentée pour vérifier les connexions.
Les vues Surveillance et Incident devront encore faire l'objet de maquettes avant
d'être considérées comme validées.

## Outils avancés recommandés, avec leur ordre d'intégration

| Priorité | Outil ou capacité | Utilité | Condition d'intégration |
|---|---|---|---|
| Phase d'expérimentation | MLflow Tracking | Comparer paramètres, variantes de détection, mesures et artefacts | Après fonctionnement du premier détecteur et du protocole d'évaluation |
| Phase de déploiement | OpenTelemetry | Mesurer les requêtes et analyses de SmartOps, relier leurs métriques/logs/traces | Après création des services ; export vers un collecteur avec un profil Compose dédié |
| Après la référence statistique | Détecteur multivarié, par exemple Isolation Forest | Vérifier si les relations entre métriques améliorent la détection | Apprentissage sur le développement, choix sur validation et comparaison au même protocole |
| Après le diagnostic de référence | LangGraph | Décrire un parcours de diagnostic avec outils, branches et état explicite | Si le diagnostic nécessite plusieurs étapes conditionnelles ; garder une variante déterministe comparable |
| Extension IA | Recherche de procédures + LLM, éventuellement pgvector | Retrouver les procédures pertinentes et rédiger une explication avec références | Corpus vérifié, test de pertinence de recherche, budget d'exécution et abstention |

### OpenTelemetry

Instrumenter **notre application SmartOps** : durée des requêtes API, temps de
traitement, erreurs d'analyse et chaîne de diagnostic. Ce flux opérationnel utilise
le temps réel et des noms de services propres à SmartOps. Il reste distinct des
observations RCAEval rejouées, qui utilisent le temps simulé.

Une extension ultérieure pourra instrumenter une application de démonstration
et alimenter l'agent en direct. L'ajout d'OpenTelemetry à SmartOps ne transforme
pas automatiquement le dataset en une collecte en direct.

### MLflow et expérimentation

Enregistrer révision du dataset, identifiants des ensembles, paramètres, version du
code, couverture, fausses alertes, délais et classement diagnostique. Son interface
sert à comparer les expériences ; le tableau de bord Next.js reste l'application
destinée à l'utilisateur. Un suivi d'expériences ne garantit pas la qualité du modèle.

### LangGraph, LLM et procédures

Exemple de parcours possible : analyser les métriques, demander les logs pertinents,
examiner les dépendances disponibles, chercher une procédure, vérifier les références,
puis expliquer ou s'abstenir. Les outils reçoivent les mêmes limites temporelles et
identifiants opaques que l'agent de référence.

LangGraph peut représenter des étapes déterministes et des appels à un modèle.
Son adoption ne nécessite pas automatiquement plusieurs agents ni un fournisseur
LLM particulier. Le modèle, son hébergement et son éventuel coût restent à choisir.
L'extension générative ne devient pas une dépendance du premier prototype.

Une recherche vectorielle n'est pertinente que si elle améliore la recherche dans
un corpus de procédures suffisamment riche. Un petit catalogue peut commencer
avec une recherche textuelle et des filtres. Ne pas indexer tous les logs sous forme
de vecteurs sans besoin et sans évaluation du gain.

## Technologies à réserver à un besoin mesuré

Kafka, Kubernetes, une base vectorielle séparée et une architecture à nombreux
microservices ne sont pas nécessaires au traitement local des 90 incidents. Ils
pourront être réévalués pour des flux multiples, une exploitation distribuée ou un
déploiement demandé. Ils ne sont pas des critères de réussite par leur seule présence.

La référence statistique reste le point de comparaison des méthodes avancées.
Une solution plus complexe doit montrer son gain en détection ou en diagnostic,
et pas seulement augmenter le nombre de dépendances.

## Sources primaires consultées

- [Next.js App Router](https://nextjs.org/docs/app).
- [Tailwind CSS avec Next.js](https://tailwindcss.com/docs/installation/framework-guides/nextjs).
- [shadcn/ui](https://ui.shadcn.com/docs).
- [Apache ECharts](https://echarts.apache.org/en/feature.html).
- [TanStack Query](https://tanstack.com/query/latest/docs/framework/react/overview).
- [PostgreSQL et JSONB](https://www.postgresql.org/docs/current/datatype-json.html).
- [MLflow Tracking](https://mlflow.org/docs/latest/ml/tracking/).
- [OpenTelemetry](https://opentelemetry.io/docs/what-is-opentelemetry/).
- [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview).
- [Playwright](https://playwright.dev/docs/intro).

Les propriétés décrites par les éditeurs servent à établir ces propositions.
L'apport réel des outils d'analyse sera mesuré sur notre protocole.
