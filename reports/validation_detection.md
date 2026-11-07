# Validation de la détection — 21 octobre 2026

Le détecteur robuste et ses paramètres sont documentés dans
[detection.md](../docs_informatifs/detection.md).
La migration Alembic 0004 ajoute les profils, l’état d’analyse et les alertes.

## Vérifications backend

15 tests réussis avec PostgreSQL réel et schémas isolés. Les nouveaux contrôles
couvrent la séparation chronologique de calibration, les références constantes,
les références insuffisantes ou absentes, la persistance, la récupération, les valeurs
manquantes, l’équivalence entre lots et pas unitaires, l’absence de doublons,
les preuves bornées, la reprise de l’historique et le rollback d’une transaction
d’alerte déjà envoyée mais non validée. Un rollback laisse le curseur et l’analyse
au dernier point validé, sans alerte partiellement enregistrée.

Le frontend compile en production et le contrôle TypeScript réussit.

## Vérifications de l’interface

Docker Compose applique la migration 0004 et démarre les trois services locaux.
Les 3 tests Playwright avec Edge passent sur les données SMD réelles : apparition
d’alertes, consultation des mesures, preuves bornées au curseur, pause/reprise/arrêt,
changement de ressource et de machine, état vide simulé explicitement et rendu mobile.
Capture : [interface_smd.png](interface_smd.png).
La CI est adaptée via sa fixture d’apprentissage explicite ; son workflow distant
n’a pas été exécuté pendant ce jalon.

## Résultats expérimentaux

Évaluation figée sur les 28 machines et les 708 420 observations de test.
Les labels sont chargés après production des prédictions. Aucun ajustement des
prédictions à partir des labels, aucun changement de seuil après examen du test.

Précision micro 10,31 %, rappel 59,64 %, F1 17,58 %, faux positifs sur les points
normaux 22,50 %. Le F1 moyen par machine est 21,89 %. Cette référence est trop
sensible pour une utilisation opérationnelle et doit être améliorée ou dépassée
par une méthode comparée sous protocole figé.

Les profils d’apprentissage sont les seules entrées de calibration. Le backend
ne monte pas l’espace d’évaluation. Les recommandations et le diagnostic de cause
ne sont pas encore implémentés ; une alerte n’est pas une panne confirmée.
