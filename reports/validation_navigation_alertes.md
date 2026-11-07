# Validation de la navigation des alertes

Date : 2026-11-07.

## Comportement livré

- Totaux par composant et par indicateur calculés côté serveur sur toute la lecture jusqu’au curseur, indépendamment de la pagination.
- Filtre Tous / CPU / Mémoire / Disque / Réseau et remise à zéro de la pagination lors du changement de filtre.
- Distinction entre absence d’alerte sur le composant et absence d’alerte sur l’indicateur affiché.
- Navigation vers l’indicateur et la période de détection d’une alerte, avec retour aux dernières observations.
- Pour PCA, classement par indicateur dominant explicité ; les contributions ne prouvent pas une cause de panne.
- Correction du débordement du sélecteur de méthode sur mobile.

## Vérifications

- Suite Python complète : **18 tests réussis**, avec PostgreSQL réel et schémas temporaires isolés. Les assertions supplémentaires vérifient les totaux hors pagination, le filtrage, le compteur actif global et le rejet d’une ressource inconnue.
- Compilation de production Next.js et vérification TypeScript réussies, y compris dans Docker.
- Suite Playwright sur Microsoft Edge : **5 tests réussis**, exécution séquentielle contre les services Docker sur le port 3000.
- Parcours réels : lancement, pause, reprise, arrêt, méthodes individuelle et combinée, causalité des observations et preuves.
- Cas contrôlé avec réponses API simulées : alerte disque détectée à l’index 1000 alors que la lecture est à 20000 ; sélection du bon indicateur, requête sur [800, 1100], retour à 20000, filtre vide mémoire et remise à zéro de pagination.
- Vue mobile 390 × 844 : aucun débordement horizontal.

Captures : [interface](interface_smd.png), [mobile](alerts_mobile.png).

Cette évolution porte sur la consultation des alertes. Les paramètres et les scores d’évaluation des détecteurs sont conservés.
