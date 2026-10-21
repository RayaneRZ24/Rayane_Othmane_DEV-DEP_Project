# Validation du socle applicatif SmartOps

Date : 21 octobre 2026. Vérifications effectuées localement, sur le code du présent jalon.

## Résultats

| Vérification | Résultat observé |
|---|---|
| Résolution des dépendances Python | Réussie ; versions enregistrées dans `uv.lock` |
| Installation frontend | Réussie ; versions enregistrées dans `frontend/package-lock.json` |
| Build de production Next.js sous Windows | Réussi, compilation et contrôle TypeScript |
| Construction du backend Linux | Réussie, environnement Python 3.13 |
| Construction du frontend Linux | Réussie, compilation de production et contrôle TypeScript |
| Migration PostgreSQL | Réussie, révision Alembic `0001` |
| Tests pytest | **5 réussis**, dont 2 avec PostgreSQL réel dans des schémas temporaires |
| Tests Playwright | **2 réussis**, avec Microsoft Edge installé et les services dans Docker |
| État Compose avant arrêt de validation | PostgreSQL, backend et frontend tous `healthy` ; migration terminée normalement |
| Capture de l'interface | `reports/socle-integration.png` |

Les tests couvrent :

- État dégradé de l'API lorsque la base est indisponible, sans divulgation d'erreur du pilote.
- Refus de présenter une écriture comme réussie en cas d'échec SQL.
- Écriture puis lecture réelle PostgreSQL et réception de deux événements SSE.
- Passage à un état dégradé après retrait de la migration dans un schéma temporaire,
  puis retour à un état disponible après réapplication.
- Parcours navigateur initial : disponibilité, bouton de persistance, confirmation
  et incrément du compteur reçu par SSE au travers du proxy Next.js. Les contrôles
  de persistance ont ensuite été retirés de l'interface utilisateur ; ils restent
  vérifiés dans les tests backend.
- Affichage sur un écran de 390 pixels sans débordement horizontal.

## Versions installées lors de la vérification

| Composant | Version |
|---|---|
| Python, environnement local uv | 3.12.13 |
| Python, image backend | 3.13.16 |
| Node.js, poste local | 24.11.1 |
| Node.js, image frontend | 24.22.1 |
| PostgreSQL | 18.6 |
| Next.js | 16.4.2 |
| React | 19.3.1 |
| Tailwind CSS | 4.3.3 |
| TanStack Query | 5.104.5 |
| Apache ECharts | 6.1.0 |
| FastAPI | 0.158.1 |
| Pydantic | 2.14.1 |
| SQLAlchemy | 2.1.6 |
| Psycopg | 3.3.6 |
| Alembic | 1.20.0 |
| pytest | 9.1.1 |
| Playwright | 1.64.1 |

Les versions applicatives sont verrouillées dans les fichiers de dépendances.
Les images Docker portent des tags de versions majeures ; elles peuvent évoluer
sur un prochain téléchargement. Les versions ci-dessus décrivent la vérification
réalisée, sans prétendre que les tags Docker sont des empreintes immuables.

## Particularités rencontrées

- Le port 8000 étant déjà utilisé par un autre programme, le port hôte de l'API
  est **18000**. Son port interne dans Compose reste 8000. Le service existant
  n'a pas été arrêté.
- Le téléchargement du navigateur Chromium fourni par Playwright a échoué sur
  le réseau. Les deux tests ont été exécutés avec `PLAYWRIGHT_CHANNEL=msedge`,
  dans un profil de test temporaire. Le test n'utilise pas le profil personnel.
- Le frontend a été testé depuis le navigateur Windows contre les conteneurs
  Linux : la migration, le pilote PostgreSQL et le proxy SSE ont donc été exercés
  au-delà de simples simulations unitaires.
- Le workflow GitHub Actions est fourni, mais n'a pas encore été exécuté sur
  GitHub pour ce jalon. Aucune réussite distante n'est revendiquée.

## Limites et suite

L'écran est un diagnostic du socle, pas encore le tableau de bord métier.
Les sondes enregistrées sont des tests techniques et les courbes sont les temps
réels de requêtes HTTP mesurés dans le navigateur. Aucune métrique RCAEval n'est
encore rejouée, aucun modèle n'est entraîné et aucune performance de détection
ou de diagnostic n'a été calculée.

La prochaine tranche sera le lecteur des scénarios préparés et l'horloge de relecture,
avant d'ajouter la détection d'anomalies.

## Révision de la présentation

L'interface a été épurée à la demande de l'utilisateur : suppression des noms du
binôme, du contexte académique, du nom et du contenu du dataset, des mentions de
développement et des outils de vérification techniques. Le schéma des technologies
et les liens de fonctionnalités à venir ont également été retirés.
La capture correspond désormais à une vue de supervision présentant les états
des services, la latence et les dates de synchronisation. Les tests navigateur
ont été adaptés pour vérifier l'absence des détails internes et l'affichage mobile.

Voir [le guide de lancement](../docs_informatifs/demarrage.md) pour reproduire les vérifications.
