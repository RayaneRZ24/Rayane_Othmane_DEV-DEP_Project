# Dataset retenu : SMD — Server Machine Dataset

SMD est la seule source de données retenue pour les prochaines étapes.
Décision du 21 octobre 2026, fondée sur l’audit des fichiers complets.

## Sources

- [Dépôt officiel](https://github.com/NetManAIOps/OmniAnomaly).
- Révision : `7fb0e0acf89ea49908896bcc9f9e80fcfff6baf4`.
- [Ordre des variables communiqué par un collaborateur](https://github.com/NetManAIOps/OmniAnomaly/issues/22#issuecomment-771310719).
- Licence MIT incluse dans le dossier du dataset et conservée sous `third_party/`.

Les 113 fichiers, environ 486 Mo non compressés, sont téléchargés. Les objets Git
ont été vérifiés au téléchargement ; chaque fichier possède une empreinte SHA-256.

## Résultats de l’audit

| Critère | Résultat |
|---|---|
| Machines | 28 |
| Variables par machine | 38 |
| Observations d’apprentissage | 708 405 |
| Observations de test | 708 420 |
| Valeurs manquantes / infinies | 0 / 0 |
| Valeurs hors de [0,1] | 0 |
| Labels de test | 708 420, binaires et alignés |
| Points de test anormaux | 29 444, soit 4,156 % |
| Segments anormaux binaires | 327 |
| Colonnes constantes par fichier | De 2 à 10 |

Aucune ligne numérique n’est répétée dans un fichier. Aucune ligne de test n’est
identique à une ligne d’apprentissage de la même machine. Cela ne prouve pas
l’absence de toute fuite : l’ajustement de la normalisation originale n’est pas documenté.
Voir [smd_audit.json](../reports/smd_audit.json).

## Pertinence et limites

Les variables couvrent directement CPU, charge système, mémoire, disque et réseau.
Les partitions existent, les données sont complètes, le test est annoté et le volume
reste exploitable localement. Commencer sur trois machines puis étendre aux 28.

- Les valeurs sont normalisées entre 0 et 1. Ne pas convertir `0,8` en « CPU 80 % »
  sans paramètres physiques. Les unités détaillées restent incomplètement documentées.
- Les lignes sont ordonnées sans dates absolues. Une cadence constante est indiquée,
  sans durée vérifiée : utiliser un index d’observation.
- Les données d’apprentissage n’ont pas de labels point par point : leur normalité
  n’est pas certifiée. Préserver une validation chronologique dans l’apprentissage.
- Gérer explicitement les dispersions nulles des colonnes constantes.
- Les 327 plages d’attribution sont dans les bornes mais leur union diffère des
  labels binaires sur 52 points avec index zéro et borne finale exclue.
  Les labels binaires restent la référence pour la détection.
- Les dimensions attribuées ne prouvent pas une cause physique précise.
- Aucun log système ni trace distribuée n’est fourni. Le journal des alertes sera
  un résultat de l’agent, pas un log du dataset.

## Protocole

Préserver partitions et ordre par machine. Utiliser une fin chronologique de `train`
pour la validation, puis figer les paramètres avant le test. Ne jamais transmettre
les annotations au détecteur ou à l’API de supervision. Commencer avec `machine-1-1`,
`machine-2-1`, `machine-3-1`. Mesurer précision, rappel, faux positifs et délais en
observations sans corriger les prédictions à partir des labels.
