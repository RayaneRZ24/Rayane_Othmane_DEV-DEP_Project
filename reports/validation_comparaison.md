# Validation de la comparaison — 22 octobre 2026

La méthode PCA est implémentée et sélectionnable explicitement. Les paramètres
du protocole sont figés dans `config/comparison_protocol.json` ; son empreinte est
recopiée dans le rapport. Les labels sont lus après les prédictions des deux candidats.

18 tests Python réussis, avec PostgreSQL réel et schémas isolés. Les nouveaux tests
vérifient une rupture de corrélation sans anomalie univariée, les références constantes,
les valeurs manquantes, la stabilité par lots, la sérialisation du profil avec
réordonnancement des clés JSONB, le choix
du détecteur, son idempotence et le refus d’une méthode inconnue par l’API.

Comparaison terminée sur les 28 machines, soit 56 couples machine/méthode et
708 420 observations de test pour chaque méthode. Les résultats reproduisent
exactement les comptes de confusion de la référence précédente.

La PCA donne une précision de 17,48 %, un rappel de 42,84 %, un F1 de 24,83 % et
8,77 % de faux positifs parmi les points normaux. La référence donne respectivement
10,31 %, 59,64 %, 17,58 % et 22,50 %. Ce compromis n’est pas une amélioration
uniforme ni une validation opérationnelle. Aucun réglage supplémentaire n’a été
fait après lecture du test.

Voir [le protocole et les limites](../docs_informatifs/comparaison_detecteurs.md).
