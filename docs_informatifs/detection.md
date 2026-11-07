# Premier détecteur : référence robuste par machine

Le détecteur `robust-mad-v1` analyse les 38 variables de SMD dans l’ordre pendant
la relecture. Il ne représente pas encore un diagnostic de cause ni un modèle
multivarié. Les alertes signifient « écart à examiner », pas « panne confirmée ».

## Apprentissage sans annotations de test

Pour chaque machine, la partition d’apprentissage préparée est divisée chronologiquement :
80 % pour ajuster la référence, 20 % pour calibrer les seuils. Les deux portions
restent à l’intérieur de `train`. Les labels et attributions ne sont jamais montés
dans le backend. Si la référence manque ou est insuffisante, le lancement est refusé.

Pour une variable, on calcule sur la première portion :

- `m = médiane(x)` ;
- `s = max(1,4826 × MAD, IQR / 1,349, 0,001)` ;
- `score = |x − m| / s`.

Le plancher gère les variables constantes dans l’espace normalisé, sans division
par zéro. Sur la fin de l’apprentissage, le seuil est le maximum de 6 et du
quantile 99,5 % des scores. Ce quantile empirique n’est pas une garantie de taux de
fausses alertes sur le test, et l’apprentissage n’est pas certifié entièrement sain.
Ces paramètres ont été fixés avant cette première évaluation, sans réglage sur le test.

Le profil, ses paramètres, les effectifs, l’empreinte de la référence et une empreinte
du profil sont persistés pour chaque run. Aucune adaptation de la normale n’est
effectuée pendant la relecture du test.

## Déclenchement et suivi

Trois écarts strictement supérieurs au seuil et consécutifs déclenchent une alerte
par variable. Son début est le premier écart, sa détection le troisième. Les preuves
conservent la valeur à la détection, la médiane, l’échelle, le score, le seuil et la
plage attendue, ainsi que l’index observé.

L’alerte reste active jusqu’à cinq observations consécutives dans la plage.
Les valeurs manquantes interrompent la persistance mais ne prouvent jamais un retour
à la normale. La pause fige l’analyse ; la reprise poursuit son état. Un nouveau
run repart avec un état vide. Toutes les observations sont analysées, même si
l’interface ne montre qu’une variable ou les 500 dernières observations.

L’arrêt, la fin de série et l’interruption clôturent le suivi avec leur état propre,
sans prétendre qu’un rétablissement a été observé. Le curseur, l’état d’analyse,
les alertes et l’événement sont validés dans une même transaction PostgreSQL.

## Affichage

La console affiche les alertes actives, leur historique paginé, les mesures
justificatives et un accès à l’indicateur concerné. Les détections de la page
d’alertes courante sont repérées dans la fenêtre visible du graphique.
Les scores ne sont pas présentés comme une probabilité de panne. Les unités
restent normalisées ; aucun pourcentage physique ou horodatage n’est inventé.

## Première évaluation complète

Commande : `uv run --no-sync python scripts/evaluate_detector.py`.
Les prédictions sont produites sans accès aux labels. Les annotations sont lues
ensuite uniquement par le script d’évaluation, hors du backend.

Sur 708 420 observations de test réparties sur 28 machines :

| Mesure point par point | Résultat |
|---|---|
| Précision micro | 10,31 % |
| Rappel micro | 59,64 % |
| F1 micro | 17,58 % |
| F1 moyen par machine | 21,89 % |
| Part des points normaux signalés à tort | 22,50 % |
| Alertes par variable sur toutes les séries | 5 297 |

Un point est prédit anormal si au moins une alerte est active à cet index. Les
prédictions ne sont pas étendues ou corrigées à partir des intervalles annotés.
Les mesures ci-dessus sont des métriques de points, pas une précision calculée
sur les objets d’alerte. Les valeurs agrégées masquent des différences importantes
entre machines : les résultats par machine sont fournis dans les rapports.

**Cette référence produit trop de faux positifs.** Elle permet de vérifier la
chaîne et de comparer une méthode suivante, mais ne démontre pas une fiabilité
opérationnelle. Les prochaines variantes devront être définies et sélectionnées
avec un protocole de développement distinct ; ces labels de test ne serviront
pas à choisir des seuils après lecture des résultats.

Résultats : [JSON](../reports/detection_evaluation.json),
[CSV](../reports/detection_evaluation.csv).

La comparaison avec PCA est désormais disponible dans
[comparaison_detecteurs.md](comparaison_detecteurs.md). La référence demeure
le choix par défaut ; les deux méthodes sont sélectionnables explicitement.
