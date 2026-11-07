# Comparaison figée : référence robuste et PCA

Le 22 octobre 2026, deux candidats ont été comparés sur les mêmes partitions SMD.
Le protocole et les paramètres sont enregistrés dans
[comparison_protocol.json](../config/comparison_protocol.json), avant les prédictions
et la lecture des labels par le script. Aucun essai de seuil supplémentaire n’a
été réalisé après examen des résultats. La référence reste le choix par défaut ;
la méthode combinée peut être choisie explicitement pour une nouvelle lecture.

## Méthode multivariée

`pca-joint-v1` utilise les mêmes 80 premiers pour cent de `train` pour l’ajustement
et les 20 derniers pour la calibration. La médiane et la dispersion robuste de
la référence mettent les variables à une échelle comparable. Le modèle apprend
la moyenne et les axes principaux de leur covariance, en NumPy float64.

Le rang vise 90 % de variance expliquée, avec au plus `dimensions − 1` axes pour
conserver un espace résiduel. Une référence entièrement constante a un rang zéro.
Les valeurs propres retenues sont régularisées par le maximum de `0,001 × valeur
propre maximale` et `1e-6`.

Deux scores sont calculés pour chaque observation :

- la moyenne des résidus de reconstruction au carré, divisés par l’échelle
  résiduelle apprise (plancher 0,1 dans l’espace standardisé) ;
- la distance dans les axes retenus, pondérée par les valeurs propres régularisées.

Les seuils sont le quantile 99,5 % de calibration, avec planchers respectifs de
36 et `rang + 6 × sqrt(2 × max(rang, 1))`. Le score combiné est le maximum des
deux rapports score/seuil. Trois observations consécutives supérieures à 1 ouvrent
une alerte ; cinq observations consécutives sous le seuil terminent l’écart.
Une valeur manquante ne prouve pas un rétablissement. Aucun ajustement sur le test.

Une seule alerte combinée peut être active par run. Les trois contributions
principales à la composante déclenchante sont enregistrées à la détection. La
variable dominante identifie l’alerte et permet d’accéder à sa courbe ; elle n’est
pas une cause physique confirmée. Les contributions résiduelles sont les résidus
standardisés au carré ; celles de distance sont les valeurs absolues des termes
par variable de la forme quadratique. Ce sont des indices explicatifs, pas des
probabilités ni des effets causaux. La plage individuelle affichée est descriptive
et ne constitue pas la règle de décision du modèle combiné.

## Résultats complets

708 420 observations de test, 28 machines ; mêmes partitions, persistance et
récupération. Les labels sont chargés après les prédictions des deux méthodes.
Pas de correction des prédictions à partir des intervalles annotés.

| Mesure point par point | Par indicateur | Indicateurs combinés |
|---|---|---|
| Précision micro | 10,31 % | 17,48 % |
| Rappel micro | 59,64 % | 42,84 % |
| F1 micro | 17,58 % | 24,83 % |
| F1 moyen par machine | 21,89 % | 30,35 % |
| Points normaux signalés à tort | 22,50 % | 8,77 % |
| Objets d’alerte | 5 297 | 490 |

La PCA réduit les faux positifs et augmente le F1 global, mais diminue le rappel.
Elle n’est pas meilleure sur toutes les machines et sa précision reste faible.
Les nombres d’objets d’alerte ne sont pas directement comparables : la référence
émet par variable, la PCA émet une alerte globale. Les métriques point par point
utilisent dans les deux cas l’union des alertes actives, ce qui permet la comparaison.
Les durées enregistrées incluent apprentissage et prédiction dans une exécution
locale non isolée ; elles ne constituent pas un benchmark de latence en production.

Cette étude est exploratoire : le test SMD avait déjà été examiné pour la référence.
Les résultats ne justifient ni une sélection automatique du modèle sur chaque machine,
ni un réglage de seuil guidé par les labels. Une conclusion de généralisation
nécessitera une validation indépendante. Aucune des deux méthodes n’est annoncée
comme fiable pour une utilisation opérationnelle.

Rapports : [JSON](../reports/detector_comparison.json),
[CSV](../reports/detector_comparison.csv).

## Utilisation

Dans l’interface, choisir **Par indicateur** ou **Indicateurs combinés** avant
de lancer une lecture. Le choix est bloqué pendant une lecture active ou en pause.
Il est conservé dans PostgreSQL, avec le profil ajusté et son empreinte.
Les graphiques, commandes et preuves gardent le même axe d’observation.

Reproduire : `uv run --no-sync python scripts/compare_detectors.py`.
Un protocole différent exige une nouvelle étude, sans écraser le protocole figé.
