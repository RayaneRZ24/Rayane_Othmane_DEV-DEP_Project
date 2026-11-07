# Technologies et interface

Le projet utilise exclusivement SMD. La console cible est organisée par machines et ressources.

| Besoin | Technologie |
|---|---|
| Interface | Next.js, React, TypeScript |
| Style | Tailwind CSS et shadcn/ui |
| Graphiques | Apache ECharts |
| Cache et synchronisation | TanStack Query et SSE |
| API | FastAPI et Pydantic |
| Analyse | pandas, NumPy et PyArrow |
| Stockage | PostgreSQL, SQLAlchemy, Psycopg 3, Alembic et Parquet |
| Déploiement | Docker Compose |
| Tests et CI | pytest, Playwright et GitHub Actions |

Les versions sont figées dans les lockfiles. ECharts s’initialise côté navigateur
et libère ses ressources au démontage. Un seul processus backend possède la relecture.

L’interface affichera machines, ressources, courbes, alertes et preuves. Les valeurs
seront normalisées et l’axe utilisera l’index. Les états vides resteront lisibles.
Ne pas afficher noms d’étudiants, détails scolaires, chemins, description du dataset
ou liste des technologies dans le parcours opérateur. Une disponibilité technique
ne suffit pas à déclarer une machine saine.

MLflow, OpenTelemetry et une orchestration explicite du diagnostic sont des extensions
envisagées, non implémentées. Leur intérêt devra être mesuré par rapport à une référence.
