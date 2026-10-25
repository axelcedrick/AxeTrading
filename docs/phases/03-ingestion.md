# Phase 3 — Ingestion (Bronze → Silver) et qualité des données

Fichier à placer dans `docs/phases/03-ingestion.md`. Lis d'abord `CLAUDE.md`, `docs/architecture.md`, `docs/workspace-audit.md` et `docs/phases/02-rapport.md`, puis exécute cette phase, et seulement celle-ci.

> **Ce fichier a été écrit AVANT l'audit.** Il repose sur les hypothèses de la section suivante. Chacune doit être confrontée aux résultats de `docs/workspace-audit.md` au démarrage. Là où l'audit contredit une hypothèse, **l'audit prime** : adapte la phase et consigne l'écart en tête du rapport de fin de phase.

## Hypothèses à confronter à l'audit

| ID | Hypothèse | Test d'audit | Si elle est fausse |
|---|---|---|---|
| H1 | Twelve Data sert les 6 instruments, dont XAU/USD, sur l'offre gratuite | C3 | Retirer l'instrument ou choisir un fournisseur alternatif pour lui, après accord de l'utilisateur |
| H2 | L'intervalle 15 min est servi ; 5 min et 1 h aussi | C4 | Adapter les intervalles du backfill |
| H3 | Le coût en crédits dépend du nombre de requêtes, pas du nombre de points par requête (jusqu'à 5 000) | C6, C8 (en-têtes de crédits) | Recalculer tout le budget d'appels ci-dessous |
| H4 | La dernière bougie renvoyée peut être **en cours de formation** | C5, C7 | Simplifier la règle de complétude, sans la supprimer |
| H5 | Les données gratuites sont en temps réel ou avec un retard borné et mesuré | C5 | Fixer le décalage de déclenchement du job sur le retard mesuré ; si le retard est trop grand ou variable, le dire à l'utilisateur car cela remet en cause l'usage intraday |
| H6 | Aucun bid/ask ni volume exploitable | C7 | Si disponibles, les ajouter à `silver.candles` / une table de cotations, sans changer le reste |
| H7 | Les horodatages sont en UTC ou dans un fuseau documenté | C7 | Convertir et tester explicitement la conversion |
| H8 | Un job serverless planifié toutes les 15 min est possible | B4, B5 | Passer à une cadence permise, ou à un déclenchement externe |
| H9 | L'accès sortant du workspace vers le fournisseur fonctionne | C2 | Bloquant : s'arrêter et en informer l'utilisateur |
| H10 | La clé est lisible depuis un job via le mécanisme de secrets validé | B11 | Appliquer l'alternative validée en phase 2 |

## Objectif

Mettre en place une ingestion fiable, idempotente et surveillée pour les 6 instruments, de la source jusqu'à `silver.candles`, avec des garde-fous prouvant qu'une donnée défectueuse ne peut pas devenir un signal exploitable. Le moteur quantitatif (phase 4) ne lira que des données déclarées valides.

## Règles de cette phase

- Les règles de `CLAUDE.md` s'appliquent, en particulier : aucun secret dans le dépôt ou les logs, aucune réussite déclarée sans exécution.
- **N'invente aucun nom de champ de l'API.** Écris le parseur à partir des réponses réelles conservées dans `tests/fixtures/` pendant l'audit.
- Tests unitaires **sans réseau** (fixtures). Les tests d'intégration contre le fournisseur ou le workspace sont séparés et marqués.
- Le budget d'appels du fournisseur est une ressource à protéger : le connecteur ne doit jamais pouvoir le dépasser (tâche 2).
- Les seuils numériques ci-dessous sont des **propositions** ; ils vivent dans la configuration, pas dans le code, et l'utilisateur les valide.

## Tâches

### 1. Connecteur fournisseur

- Implémente `MarketDataProvider` (interface de `docs/architecture.md` §5) dans `src/atlas/providers/twelvedata.py`.
- `fetch_candles` renvoie la réponse **brute** (`RawResponse`), sans normalisation. `capabilities()` et `remaining_budget()` reflètent les valeurs observées à l'audit.
- Gère : délais d'attente, nouvelles tentatives avec attente croissante pour les erreurs transitoires, réponse de limite de débit (attendre le début de la minute suivante, comportement observé en C8), erreurs d'authentification (échec immédiat, sans nouvelle tentative), réponses vides ou malformées (consignées, jamais ignorées en silence).
- La clé n'apparaît ni dans les logs, ni dans `request_params`, ni dans `bronze.raw_candles`.
- Documente le fournisseur dans `docs/providers/twelvedata.md` à partir de l'audit (couverture réelle, délais, limites, droits d'usage, champs, limites de qualité) : c'est un livrable exigé par le master prompt.

### 2. Gestionnaire de budget d'appels

- Compteur persistant (table ou fichier dans un emplacement géré par le workspace) des appels par minute et par jour (le quota quotidien se réinitialise à minuit UTC selon la documentation du fournisseur ; à confirmer à l'audit).
- Règle : le live a priorité ; le backfill n'utilise que le budget restant, avec une réserve de sécurité (proposition : arrêt à 90 % du quota quotidien).
- Si le budget est insuffisant : sauter ou reporter, consigner dans `gold.pipeline_runs`, ne jamais dépasser.
- Tests : épuisement de la minute, épuisement du jour, réinitialisation, priorité live/backfill.

### 3. Ingestion Bronze

- Écris chaque réponse brute dans `bronze.raw_candles` en **ajout seul** (jamais de mise à jour ni de suppression), avec : fournisseur, symbole, intervalle, paramètres de la requête (sans clé), horodatages de requête et de réception, statut HTTP, statut de collecte, version du connecteur, charge brute, empreinte (`payload_hash`).
- Une requête en échec est aussi enregistrée (statut `error`), pour que les trous soient diagnostiquables.

### 4. Normalisation Silver

- Parseur dans `src/atlas/ingestion/silver.py`, un adaptateur par fournisseur, à partir des fixtures.
- Convertit en UTC, aligne `bar_open_ts` / `bar_close_ts` sur les bornes d'intervalle, convertit les types numériques.
- Écrit dans `silver.candles` par `MERGE` sur la clé naturelle (`instrument_id`, `interval`, `bar_open_ts`, `provider`). Rejouer le même Bronze ne change rien.
- **Règle de complétude** : une bougie est `is_complete = true` seulement si l'heure UTC courante dépasse `bar_close_ts` d'une marge configurable (proposition : 1 minute, ajustée au délai mesuré en H5) **et** si le fournisseur ne la signale pas comme en cours. Une bougie incomplète est stockée avec `is_complete = false`, jamais écrasée par une valeur plus ancienne ; quand elle devient complète, la ligne est mise à jour par le `MERGE`.
- **Bougies 1 h dérivées des bougies 15 min** : pour économiser le budget d'appels, ne récupère pas le 1 h en direct. Construis-le par agrégation de 4 bougies 15 min (ouverture de la première, clôture de la dernière, extrêmes des quatre). Une bougie 1 h n'est complète que si ses 4 sous-bougies sont présentes et complètes ; sinon elle est marquée incomplète avec le motif. *(Écart par rapport à `docs/architecture.md` §2, qui prévoyait des appels 15 min et 1 h : à valider avec l'utilisateur ; le 1 h reste récupéré directement pour le backfill si l'audit montre que c'est peu coûteux, avec contrôle de cohérence entre les deux.)*
- Le 5 min n'est ingéré que pour le backfill et le backtest.

### 5. Contrôles de qualité et drapeaux

Chaque bougie reçoit des `quality_flags`. Distingue deux familles et documente-les dans `docs/data-quality.md` :

**Bloquants** (la bougie n'est jamais utilisable comme entrée de signal) :
- `INCOMPLETE` : bougie en cours de formation ou sous-bougies manquantes
- `OHLC_INVALID` : `high` < max(open, close, low), `low` > min(open, close, high), ou prix ≤ 0
- `FUTURE_TS` : horodatage postérieur à l'heure de réception
- `DUPLICATE_CONFLICT` : deux valeurs différentes pour la même clé naturelle (à investiguer, jamais résolu en silence)
- `STALE` : bougie la plus récente trop ancienne alors que le marché est censé être ouvert (seuil configurable ; proposition : 2 intervalles de retard)

**Informatifs** (visibles, non bloquants par défaut ; configurable) :
- `GAP` : bougie attendue absente selon le calendrier de sessions (signalement sur l'intervalle, pas création de bougie fictive)
- `SUSPECT_JUMP` : variation de clôture à clôture au-delà d'un seuil configurable (proposition : valeur extrême par rapport à la distribution récente de l'instrument), à examiner, pas à corriger automatiquement
- `LOW_ACTIVITY` : bougie à variation nulle pendant une session active

**Ne jamais** combler un trou en interpolant, ni corriger un prix sans trace. Toute correction éventuelle est un nouvel enregistrement distinct et journalisé.

### 6. Garde-fou d'accès aux données (prépare la phase 4)

- Crée la vue `silver.candles_valid` : uniquement les bougies `is_complete = true` sans drapeau bloquant.
- Crée `src/atlas/common/data_guard.py` avec `assert_usable(candles)` qui lève une erreur si une bougie incomplète, périmée ou incohérente est présente ; il sera appelé par le moteur quantitatif.
- Règle pour les phases suivantes, à inscrire dans `docs/data-quality.md` : le moteur quantitatif ne lit **que** `silver.candles_valid` via ce garde-fou.

### 7. Backfill

- Profondeur cible : à fixer après les mesures C6 de l'audit et validation de l'utilisateur. Ordre de grandeur indicatif (estimation à confirmer, non mesurée) : à 5 000 points par requête, le 15 min couvre environ 10 jours de marché par appel, le 5 min environ 3 semaines et demie, le 1 h plus de 6 mois ; un an de 15 min pour 6 instruments représente donc de l'ordre de 200 appels.
- Le backfill est reprenable (curseur persistant par instrument et intervalle), idempotent, et ne consomme que le budget restant du live (tâche 2). Il peut s'étaler sur plusieurs jours.
- Termine par un rapport de couverture : par instrument et intervalle, période obtenue, bougies attendues vs reçues, trous.

### 8. Ingestion live planifiée

- Job (cadence validée à l'audit, proposition : toutes les 15 minutes, décalé de quelques minutes après la clôture de bougie selon le retard mesuré en H5).
- À chaque exécution et pour chaque instrument actif : récupère les dernières bougies (quelques-unes, pour rattraper une exécution manquée), écris Bronze, normalise en Silver, applique les contrôles.
- Un instrument en échec n'interrompt pas les autres ; l'échec est enregistré dans `gold.pipeline_runs`.
- Ne tourne que lorsque le calendrier de sessions indique un marché ouvert, pour ne pas gaspiller de budget.
- Reprise après échec : un nouveau passage comble les bougies manquantes sans créer de doublon.

### 9. Surveillance

- Alimente `gold.data_quality_metrics` à chaque exécution : retard de la dernière bougie complète par instrument, bougies attendues vs reçues, trous, doublons, bougies rejetées par motif, requêtes en échec, budget d'appels consommé.
- Alertes pour : échec d'ingestion répété, données périmées, retard de pipeline, budget proche de l'épuisement, hausse inhabituelle des rejets. Utilise les notifications de jobs si l'audit les a montrées disponibles ; sinon, une requête de contrôle à consulter, et signale la limite à l'utilisateur.
- Requêtes SQL de supervision versionnées dans `sql/monitoring/`.

### 10. Tests (remplace les `xfail` de la phase 2)

Dans `tests/data_quality/` et `tests/unit/` — chacun doit réussir :
- Une bougie en cours de formation : `is_complete = false`, absente de `silver.candles_valid`, `assert_usable` échoue si elle est fournie.
- Une cotation périmée : drapeau `STALE`, exclue de la vue valide.
- Un OHLC incohérent, un prix ≤ 0, un horodatage futur : drapeau bloquant, exclus.
- Un doublon identique : une seule ligne ; un doublon conflictuel : `DUPLICATE_CONFLICT`, aucune résolution silencieuse.
- Rejouer deux fois le même Bronze : Silver identique (idempotence).
- Reprise après un passage interrompu : aucune bougie perdue ni dupliquée.
- Agrégation 1 h : complète avec 4 sous-bougies valides, incomplète s'il en manque une.
- Conversion de fuseau et alignement des bornes autour du changement d'heure et du week-end.
- Budget d'appels : ne dépasse jamais les limites (tâche 2).
- La clé ne figure dans aucun log ni dans Bronze (test).

## Livrables

- `src/atlas/providers/`, `src/atlas/ingestion/`, `src/atlas/common/data_guard.py`, gestionnaire de budget.
- DDL complémentaires (vue `silver.candles_valid`, éventuelle table de budget) dans `sql/ddl/`.
- Jobs et pipelines dans `pipelines/` et `databricks.yml`.
- `docs/providers/twelvedata.md`, `docs/data-quality.md`, `sql/monitoring/`.
- Rapport de couverture du backfill.
- `docs/phases/03-rapport.md` : écarts avec ce fichier, hypothèses H1–H10 confirmées ou infirmées, seuils retenus, questions ouvertes.
- `docs/STATUS.md` mis à jour.

## Critères d'acceptation

- Les hypothèses H1–H10 sont toutes marquées confirmées ou infirmées dans le rapport, avec la preuve de l'audit.
- Tous les tests de la tâche 10 passent ; plus aucun `xfail` dans `tests/data_quality/`.
- Rejouer le backfill et le job live deux fois ne crée aucun doublon (vérifié par requête).
- Le budget d'appels du fournisseur n'a jamais dépassé la limite (vérifié dans `gold.pipeline_runs`).
- Aucune clé dans le dépôt, les logs ou Bronze (recherche automatique).
- Le rapport de couverture du backfill est produit et ses trous sont expliqués (week-ends et fermetures attendus vs trous anormaux).
- **7 jours d'exécution planifiée** sans intervention manuelle. Proposition de seuil, à valider par l'utilisateur : au moins 99 % des bougies attendues pendant les sessions ouvertes sont reçues et complètes ; tout écart est expliqué.
- `silver.candles_valid` ne contient aucune bougie incomplète, périmée ou incohérente (requête de contrôle).

## Ne pas faire

- Ne pas écrire d'indicateur, de setup ni de signal (phase 4).
- Ne pas interpoler ni inventer de bougies.
- Ne pas contourner une limite du fournisseur ni ses conditions d'utilisation.
- Ne pas passer à un fournisseur payant ni ajouter un second fournisseur sans accord explicite.
- Ne pas déclarer la phase terminée avant les 7 jours d'exécution.

Termine en résumant : ce qui est fait et prouvé, les écarts avec ce fichier, les chiffres de couverture et de qualité, les limites observées du fournisseur, puis **attends la validation de l'utilisateur** avant la phase 4.
