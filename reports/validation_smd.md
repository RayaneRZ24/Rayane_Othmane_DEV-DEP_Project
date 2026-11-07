# Validation de l’intégration SMD — 21 octobre 2026

## Données et préparation

SMD est le seul dataset du projet. Ses 113 fichiers sources ont été vérifiés par
empreintes. `prepare_smd.py` prépare les 28 machines et conserve séparément
708 405 observations d’apprentissage et 708 420 observations de test.
Les 29 444 points anormaux de référence sont conservés dans l’espace d’évaluation,
absent du montage Docker du backend.

Le contrôle des fichiers préparés vérifie les schémas et l’ordre des index, les
comptages, l’égalité des séries CPU avec les sources pour les 28 machines et les
deux partitions, ainsi que l’absence de colonnes d’annotations dans les mesures.
Résultat : [smd_preparation.json](smd_preparation.json).

## API et interface

La migration Alembic 0003 est appliquée dans Docker. Le stockage et l’API utilisent
`cursor_index` ; les points sont identifiés par `sample_index`.
Le lecteur applique des bornes confirmées et une pagination signée. Les dates et
unités physiques ne sont pas inventées. La cadence est exprimée en observations
présentées par seconde, de 1 à 60.

L’interface propose les machines, les 38 variables regroupées par CPU/mémoire/disque/réseau,
les courbes normalisées, les dernières observations et les commandes de lecture.
Capture locale sur les données réelles : [interface_smd.png](interface_smd.png).

## Vérifications exécutées

- Tests Python : **10 réussis**, avec PostgreSQL réel dans des schémas isolés.
  Ils vérifient notamment la préparation, la stabilité des identifiants, la séparation
  des partitions et des labels, l’invariance des mesures quand les labels changent,
  le refus de colonnes d’annotations, les bornes, l’idempotence, la pause, la reprise,
  la pagination, le SSE, la fin de série et le redémarrage.
- Construction de production Next.js et contrôle TypeScript : réussis.
- Construction et lancement Docker Compose : réussis.
- Tests Playwright avec Edge sur les données réelles : **3 réussis**. Parcours
  lancement/pause/reprise/arrêt, changement de ressource et de machine ; état vide
  vérifié par simulation explicite des seules réponses HTTP dans le test ; rendu mobile.
- Aucun label de test n’est présenté dans l’interface ou dans les réponses de supervision.

La CI utilise une petite fixture synthétique explicitement créée pour les tests ;
elle ne remplace jamais les données de production et n’évalue aucun modèle.
Le workflow GitHub n’a pas été exécuté à distance pendant ce jalon.

## Limites

Le jalon SMD décrit ci-dessus a été complété par la détection robuste. Voir
[validation_detection.md](validation_detection.md) pour les tests et résultats actuels.
Les incidents et le diagnostic de cause restent à développer. SMD ne fournit ni dates absolues, ni logs système, ni traces distribuées.
Le moteur utilise un seul processus propriétaire ; un redémarrage interrompt une
lecture active et invalide les jetons de pagination.
