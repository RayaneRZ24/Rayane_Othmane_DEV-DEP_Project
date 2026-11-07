# Conception préliminaire — Supervision de machines avec SMD

## Objectif et périmètre

Observer CPU, charge, mémoire, disque et réseau ; détecter les comportements anormaux,
regrouper les alertes, expliquer les signaux suspects et recommander des vérifications.
SMD est le seul dataset retenu. La première version rejouera des observations enregistrées.
Elle ne prétendra pas surveiller une infrastructure en direct. Aucun log système ou trace
n’est fourni. Une explication n’est pas une preuve de cause physique ; aucune réparation automatique.

## Cas d’utilisation prévus

Sélectionner une machine ; examiner ses indicateurs normalisés ; lancer et suspendre
la relecture ; consulter alertes, preuves, explications et recommandations ; reproduire
une évaluation hors ligne sans divulguer les labels au détecteur.

## Architecture cible

```mermaid
flowchart LR
    S[SMD] --> P[Préparation]
    P --> M[Mesures sans annotations]
    P --> E[Annotations réservées à l’évaluation]
    M --> R[Relecture par index]
    R --> D[Détection et regroupement]
    D --> X[Explications et recommandations]
    X --> B[PostgreSQL]
    B --> A[FastAPI]
    A --> U[Next.js]
    E --> V[Évaluateur hors ligne]
    D --> V
```

## Évaluation et réalisation

Conserver `train` et `test` séparés par machine. Réserver une validation chronologique
sur `train`. Rapporter résultats par machine et globalement ; délais en observations.
Le socle, l’adaptateur SMD, la relecture par index et les vues par machine sont
implémentés. Le détecteur robuste et les alertes persistantes sont disponibles ;
les incidents, le diagnostic et les recommandations restent à implémenter.
