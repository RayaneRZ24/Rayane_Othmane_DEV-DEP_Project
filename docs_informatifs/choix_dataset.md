# Choix du jeu de données — SmartOps

Décision du 21 octobre 2026 : **RCAEval, RE2-OB (Online Boutique)** devient le jeu de
données principal du projet. C'est le meilleur compromis identifié entre données
exploitables, évaluation du diagnostic et faisabilité pour un binôme. Ce choix ne
signifie pas que ce dataset est universellement supérieur aux autres.

## Besoin du projet

L'agent doit détecter une anomalie, examiner les logs autour de celle-ci, classer les
services probablement responsables et proposer des vérifications correctives.
Il faut donc des métriques et logs corrélables temporellement, une cause annotée,
un accès reproductible et un volume traitable localement. Les traces sont un atout
pour distinguer le service défaillant des services qui subissent ses effets.

## Comparaison

| Candidat | Atouts vérifiés dans la documentation | Limites pour notre projet | Décision |
|---|---|---|---|
| SMD / OmniAnomaly | Données de serveurs, 28 machines, 38 variables, séparation train/test, annotations d'anomalies et d'interprétation | Le jeu fourni ne contient pas les logs corrélés nécessaires à notre chaîne de diagnostic ; variables anonymisées | Bon benchmark secondaire de détection, pas notre socle |
| GAIA / MicroSS | Métriques, logs métier, traces et journal des injections ; historique plus long | Préparation temporelle et rapprochement des fichiers plus complexes ; traces absentes de la mise à jour d'août ; README annonçant Apache 2.0 alors que le fichier LICENSE téléchargé contient GPL v2 | Intéressant, mais davantage de travail de préparation et de clarification documentaire |
| OpenRCA 1.0 | 335 incidents issus de systèmes d'entreprise, environ 68 Go de télémétrie ; benchmark de diagnostic | Volume et préparation plus exigeants ; le dépôt conseille 80 Go de stockage et 32 Go de RAM pour son agent de référence | Bonne extension future, pas nécessaire pour démarrer |
| RCAEval RE2-SS | 90 cas, métriques et logs, six types de pannes | Aucune trace distribuée dans les fichiers publiés ; messages vides dans notre échantillon | Faisable, mais moins complet que RE2-OB |
| RCAEval RE2-TT | 90 cas et système plus grand, métriques/logs/traces | 340 à 376 métriques par cas ; un cas sans logs dans l'index | Complexité supplémentaire sans nécessité pour notre première version |
| **RCAEval RE2-OB** | **90 cas, logs et traces présents dans l'index pour tous les cas ; 69 à 77 métriques ; causes connues** | Pannes expérimentales, valeurs manquantes et schémas variables à traiter | **Retenu** |

Portée de la comparaison : SMD, GAIA et OpenRCA ont été étudiés à partir des sources
primaires et de leur documentation, sans télécharger leur télémétrie complète.
Pour RCAEval, l'index des 735 cas a été inspecté ; 12 cas RE2-SS/RE2-OB ont été
téléchargés et audités, puis les métriques et logs des 90 cas RE2-OB ont été audités.
Les traces ont été auditées sur six cas RE2-OB seulement, choisis pour couvrir les
six types de pannes. Cet échantillon raisonné n'est pas une garantie sur les 90 cas.

## Données retenues

- Système : Online Boutique, application de commerce électronique en microservices.
- 5 services pouvant être la cause injectée : checkoutservice, currencyservice,
  emailservice, productcatalogservice, recommendationservice. Les autres services
  observés restent des candidats possibles pour l'agent ; ne pas lui révéler cette
  liste réduite de causes injectées.
- 6 types de pannes : surcharge CPU, pression mémoire, pression sur les entrées/sorties
  disque, retard réseau, perte de paquets et épuisement de sockets.
- 3 répétitions par couple service/panne, soit 90 expériences.
- 720 lignes de métriques avant injection dans chaque cas ; 210 à 721 lignes après.
- 88 cas couvrent 24 minutes ; deux cas sont plus courts :
  `re2ob_checkoutservice_cpu_2` et `re2ob_checkoutservice_mem_2`.
- Environ 15,05 millions de lignes de logs et 34,46 millions de spans annoncés par l'index.
- Les métriques, logs et horaires d'injection des 90 cas occupent **43 202 139 octets**
  en Parquet/fichiers texte téléchargés. Les traces sont téléchargées séparément,
  actuellement pour les six cas échantillonnés. Les données décompressées en mémoire
  occupent davantage ; traiter les cas un par un.

Version figée : `afeacb11bcc94dadfd1c8f483ee4377b2b8b614e`.
La fiche du dataset Hugging Face déclare la licence MIT ; citer les auteurs et
conserver les informations de provenance. Les licences de code d'autres benchmarks
ne doivent pas être assimilées automatiquement à celles de leurs données.

## Qualité observée et conséquences

Les chiffres exhaustifs sont dans [selected_quality.csv](../reports/selected_quality.csv)
et [selected_audit.json](../reports/selected_audit.json).
L'audit comparatif détaillé est dans [sample_audit.json](../reports/sample_audit.json).

Sur les **90 cas RE2-OB**, les **15 053 223 lignes de logs** ne contiennent aucun
champ manquant ni message vide, et tous leurs timestamps sont dans les fenêtres
des métriques. Les métriques comportent **128 742 lignes**, aucun timestamp dupliqué
et aucune valeur infinie. Les comptes de lignes et heures d'injection correspondent
à l'index dans les 90 cas. Le taux de cellules métriques manquantes par incident
va de **0 à 5,145 %**, avec une médiane de **0,00397 %**.

Dans les six cas RE2-OB échantillonnés, tous les débuts de spans se trouvent dans
la fenêtre temporelle des métriques. Aucun
couple `(traceID, spanID)` n'est dupliqué et aucune durée de span n'est négative.
Cela confirme une base exploitable pour rapprocher les signaux.

Les métriques ne sont cependant pas parfaitement complètes : le cas socket
échantillonné atteint 4,04 % de cellules manquantes. Entre 4 et 20 colonnes sont
constantes par incident. Aucune colonne n'est entièrement manquante sur un cas
complet, mais certaines n'ont aucune observation avant ou après l'injection.
Leur absence ne doit
jamais être interprétée comme une valeur zéro ou comme un fonctionnement normal.
Le schéma varie entre incidents : construire un dictionnaire de variables et
conserver un indicateur d'observation.

Les logs RE2-OB comportent beaucoup de lignes identiques à la même seconde.
La précision temporelle et l'absence d'identifiant unique ne permettent pas de
conclure qu'il s'agit de doublons de collecte. Conserver les occurrences pour les
fréquences et regrouper les messages uniquement pour la présentation.

**Dans 17 incidents sur 90, aucun log ne provient directement du service injecté**,
même si des logs des autres services sont disponibles. C'est une limite de
couverture importante : les logs seuls ne suffiront pas systématiquement à
diagnostiquer la cause. Le rapprochement des métriques, des logs des services
affectés et des traces est donc utile. Le système devra pouvoir annoncer un manque
de preuves plutôt que fabriquer une explication.

Les traces comportent des parents absents pour certains spans. Un span racine peut
légitimement ne pas avoir de parent : ces valeurs ne constituent pas à elles seules
une erreur. La couverture de services est partielle dans les traces échantillonnées.
L'alias `frontendservice` dans les traces doit être rapproché de `frontend` dans
les métriques et logs. Utiliser `startTimeMillis` (millisecondes Unix), pas la colonne
`time` des traces, qui ne contient qu'une heure/minute. Les métriques et logs ont
des timestamps Unix en secondes.

Les retards et pertes réseau n'ont pas une variable directe portant le nom de la
panne. Il faut examiner latence, erreurs, logs et dépendances. Le service au CPU le
plus élevé n'est pas nécessairement la cause d'un incident réseau.

L'index complet RCAEval contient aussi deux heures d'injection hors fenêtre dans
RE1-OB, consignées dans `reports/index_time_issues.csv`. Aucun de ces cas ne fait
partie de RE2-OB. Ne pas étendre le périmètre sans refaire les contrôles.

## Limites à annoncer dans le rapport académique

1. Les signaux proviennent d'applications instrumentées et de pannes injectées.
   Ce ne sont pas 90 incidents spontanés de production.
2. L'heure d'injection fournit une référence expérimentale, pas une annotation
   exacte du début des symptômes ni de la gravité métier à chaque seconde.
3. Les fenêtres normales sont courtes. Elles ne suffisent pas à démontrer la
   robustesse face aux cycles journaliers ou à plusieurs semaines de dérive.
4. 90 incidents sont adaptés à une référence statistique et à l'évaluation d'un
   diagnostic. Ce n'est pas une justification pour entraîner un grand modèle
   génératif ni promettre une généralisation à toute infrastructure.
5. Le dataset ne fournit pas de corrections exécutées avec leur résultat. Les
   recommandations s'appuieront sur des procédures documentées et resteront des
   propositions, avec les indices qui les motivent.

## Protocole de départ

Séparer les deux tâches :

- **Détection** : taux de détection par incident, délai depuis l'injection,
  fausses alertes par heure avant injection ; préciser le regroupement des alertes
  et la durée réellement observable après injection. Le délai depuis l'injection
  n'est pas le délai depuis le premier symptôme. Ne pas présenter toutes les
  secondes post-injection comme des anomalies parfaitement annotées.
- **Diagnostic** : exactitude Top-1 et Top-3 du service responsable, résultats par
  type de panne ; distinguer le diagnostic sur incident connu du résultat de la
  chaîne complète, dans laquelle un incident peut ne pas être détecté.

Point de départ proposé : répétition 1 pour le développement (30 cas), répétition 2
pour la validation (30), répétition 3 pour le test (30). Chaque couple service/panne
apparaît dans chaque ensemble, donc ce protocole teste la répétabilité sur le même
système, pas la généralisation à des services inconnus. Les fenêtres des 90 cas
ne se chevauchent pas d'après l'index ; les répétitions ne sont toutefois pas un
découpage chronologique global. Prévoir ensuite une évaluation chronologique et/ou
sur un service tenu à l'écart si l'on veut mesurer ces capacités.

Ne pas distribuer aléatoirement les lignes d'un même incident entre ensembles.
Les fenêtres glissantes restent dans leur incident. Ajuster normalisation,
sélection de variables et seuils sur les données de développement, et choisir les
paramètres sur validation uniquement. Les contrôles de qualité effectués ici ne
constituent pas un entraînement, et aucune performance de modèle n'est encore mesurée.

L'agent recevra un identifiant opaque et les observations disponibles à l'instant
analysé. Les chemins d'origine encodent la cause et le type de panne : ils doivent
être masqués. Les annotations, `inject_time.txt` et l'index restent côté évaluateur.
Pour une simulation en ligne, ne jamais interpoler avec le futur ni utiliser
`bfill()` ; toute imputation doit être causale, limitée et accompagnée d'un masque.

Commencer avec une détection statistique robuste et un classement explicable des
services ; comparer ensuite métriques seules, métriques + logs, puis ajout des
traces. Un éventuel LLM expliquera des indices calculés, avec possibilité de
s'abstenir quand les preuves sont insuffisantes.

## Sources primaires

- [Dataset RCAEval, fiche et index](https://huggingface.co/datasets/phamquiluan/RCAEval).
- [Dépôt officiel RCAEval](https://github.com/phamquiluan/RCAEval).
- [Article RCAEval, WWW 2025](https://arxiv.org/abs/2412.17015).
- [Archives originales RCAEval sur Zenodo](https://zenodo.org/records/14590730).
- [SMD, dépôt original OmniAnomaly](https://github.com/NetManAIOps/OmniAnomaly).
- [GAIA, dépôt et documentation](https://github.com/CloudWise-OpenSource/GAIA-DataSet).
- [OpenRCA, dépôt officiel](https://github.com/microsoft/OpenRCA).
- [Article OpenRCA : provenance des données et licence, annexe A](https://openreview.net/forum?id=M4qNIzQYpd).

Documentation consultée et copies téléchargées dans `data/sources/` le 21 octobre 2026.
Les mesures locales sont calculées par les scripts du projet, pas reprises de scores
de modèles publiés.
