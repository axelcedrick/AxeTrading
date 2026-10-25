# Phase 2 — Fondations

Fichier à placer dans `docs/phases/02-fondations.md`. Lis d'abord `CLAUDE.md`, `docs/architecture.md` et `docs/workspace-audit.md`, puis exécute cette phase, et seulement celle-ci.

## Objectif

Poser le socle technique sur lequel les phases suivantes s'appuient : catalogue et schémas, environnements, secrets, configuration, squelette du dépôt, outillage de test, déploiement par Asset Bundle. **Aucune ingestion ni calcul quantitatif dans cette phase.**

## Prérequis (à vérifier avant de commencer)

1. `docs/workspace-audit.md` existe et son verdict a été **validé explicitement par l'utilisateur**. Sinon, arrête-toi et demande.
2. Relis la section « Écarts avec l'architecture » de l'audit. Si une hypothèse a été démentie (catalogue non créable, secrets indisponibles, Apps absentes, cadence limitée), **adapte la phase en conséquence et liste chaque adaptation en tête du rapport de fin de phase**. Ne suis pas ce fichier à la lettre contre les faits mesurés.
3. Confirme avec l'utilisateur : nom du catalogue (ou du schéma racine si la création de catalogue est impossible), profil du CLI, liste des 6 instruments.

## Règles de cette phase

- Mêmes règles que la phase 1 : aucun secret dans le dépôt, les logs ou les sorties ; chaque affirmation de réussite est appuyée par une commande exécutée ; consigne les échecs au lieu de les contourner.
- Tout ce qui est créé dans le workspace l'est **par le bundle ou par des scripts versionnés dans le dépôt**, jamais à la main par l'interface, afin que l'environnement soit reproductible.
- Les scripts SQL sont **idempotents** (`CREATE ... IF NOT EXISTS`, `MERGE`) : les lancer deux fois ne change rien.
- Pas de valeur de risque ou de coût inventée en silence (voir tâche 5).

## Tâches

### 1. Environnements

Sépare `dev`, `test` et `prod` selon ce que l'audit a établi :
- Si plusieurs catalogues sont possibles : un catalogue par environnement (`atlas_dev`, `atlas_test`, `atlas_prod`).
- Sinon : un seul catalogue avec un préfixe ou suffixe de schéma par environnement (`dev_bronze`, etc.).

Déclare les trois cibles dans `databricks.yml` (variables : catalogue, préfixe de schéma, cadence des jobs, profil). `dev` est la cible par défaut. `prod` n'est déployée que sur demande explicite de l'utilisateur.

### 2. Catalogue, schémas et tables

Crée `bronze`, `silver`, `gold` dans chaque environnement, via des scripts SQL versionnés (`sql/ddl/`, numérotés : `001_schemas.sql`, `002_bronze.sql`, etc.).

Tables à créer **maintenant**, avec les colonnes de `docs/architecture.md` §4 :
- `bronze.raw_candles`
- `silver.instruments`, `silver.candles`, `silver.cost_assumptions`
- `gold.data_quality_metrics`, `gold.pipeline_runs`, `gold.audit_log`

Les autres tables Gold (`features`, `setups`, `signals`, etc.) sont créées dans leurs phases respectives, pas avant.

Ajoute des commentaires de table et de colonne. Pour `silver.candles`, définis les contraintes utiles que la plateforme permet (non nullité des prix, `is_complete`), et note celles qui ne sont pas appliquées par la plateforme : elles seront alors vérifiées par les contrôles de qualité de la phase 3.

### 3. Données de référence

- Écris `config/universe.yml` : les 6 instruments, leurs symboles fournisseur, leurs intervalles actifs (15 min et 1 h en production, 5 min pour backfill et backtest).
- Écris un script idempotent qui alimente `silver.instruments` depuis ce fichier (`MERGE`).
- Pour `pip_size`, `price_decimals`, `contract_unit`, `base_ccy`, `quote_ccy` : propose les valeurs, mais **marque-les « à confirmer »** dans le fichier et demande à l'utilisateur de les valider. Ne les présente pas comme vérifiées.
- Définis un `session_calendar_id` par classe d'actifs (Forex, or) dans `src/atlas/common/sessions.py` avec des fonctions testées : « le marché est-il ouvert à cet instant UTC ? », « la bougie de ce `bar_open_ts` est-elle attendue ? ». Appuie-toi sur ce que l'audit a constaté (week-ends, pauses, trous).

### 4. Secrets

- Utilise le mécanisme retenu à l'audit (test B11). Si les secrets Databricks sont disponibles : une portée dédiée, la clé du fournisseur créée par l'utilisateur (tu ne la vois jamais). Sinon : applique l'alternative validée avec l'utilisateur et documente son niveau de protection réel et ses limites.
- Écris `src/atlas/common/secrets.py` : une seule fonction d'accès, qui échoue clairement si le secret est absent et ne journalise jamais sa valeur.
- Ajoute un test qui échoue si une chaîne ressemblant à une clé apparaît dans le dépôt (recherche automatique), et branche-le dans l'outillage local (tâche 7).
- Écris `docs/secrets.md` : procédure de configuration pas à pas pour l'utilisateur, procédure de rotation.

### 5. Configuration de risque et de coûts

- `config/risk.yml` : structure complète des paramètres (risque max par trade, exposition totale, perte journalière max, levier max, corrélation max, spread max, péremption maximale d'un signal, etc.) **sans valeurs par défaut implicites**. Les valeurs sont **fournies par l'utilisateur** ; tant qu'elles sont absentes, le chargeur de configuration lève une erreur explicite (cohérent avec « le moteur refuse toute opération quand le risque ne peut pas être calculé »).
- `config/costs.yml` : hypothèses de spread, slippage et commission par instrument et par session. Propose des valeurs de départ prudentes, **étiquetées `source: hypothèse`**, et demande à l'utilisateur de les valider ou de les remplacer. Elles seront rappelées dans tout résultat de backtest.
- `src/atlas/common/config.py` : chargement validé (schéma strict, types, bornes). Une valeur hors bornes ou manquante est une erreur, jamais un repli silencieux. Tests unitaires pour chaque cas d'erreur.

### 6. Squelette du dépôt et journalisation

- Crée l'arborescence de `docs/architecture.md` §3 (dossiers et `__init__.py`, sans logique métier).
- `pyproject.toml` : dépendances minimales, versions épinglées.
- `src/atlas/common/logging.py` : journalisation structurée, avec un filtre qui masque toute valeur issue des secrets.
- `src/atlas/common/time.py` : utilitaires UTC (conversion, alignement sur les bornes de bougies 15 min et 1 h), testés, avec cas limites (changement d'heure, minuit, week-end).

### 7. Outillage qualité

- Tests : `pytest`, avec une commande unique documentée dans le `README`.
- Formatage et lint : choisis un outil, configure-le, exécute-le.
- Hook local avant commit : lint, tests rapides, recherche de secrets.
- `tests/data_quality/` : crée les fichiers de tests **marqués comme à implémenter** (squelettes avec `xfail` explicite et message) pour : bougie incomplète, cotation périmée, OHLC incohérent, doublon. Ils seront remplis en phase 3. Ne les marque pas comme réussis.

### 8. Déploiement et vérification

- `databricks bundle validate` puis `databricks bundle deploy` vers `dev`.
- Exécute les scripts DDL et le script d'alimentation de `silver.instruments`, **deux fois**, et vérifie que le second passage ne change rien (nombre de lignes, schéma).
- Écris un job de vérification (`atlas_foundations_check`) qui contrôle : existence des schémas et tables, lecture de la configuration, accès au secret (sans l'afficher), alimentation des instruments. Lance-le ; il doit réussir.
- Gouvernance : documente dans `docs/governance.md` qui peut lire et écrire quoi (moindre privilège), selon ce que l'audit a montré possible sur la Free Edition ; note ce qui n'est pas applicable.

## Livrables

- `databricks.yml` avec 3 cibles ; `sql/ddl/` ; `config/*.yml` ; `src/atlas/common/` ; squelette complet ; `tests/` ; `docs/secrets.md`, `docs/governance.md`.
- `docs/phases/02-rapport.md` : adaptations par rapport à ce fichier, décisions prises, questions ouvertes, valeurs en attente de l'utilisateur (risque, coûts, pip sizes).
- `docs/STATUS.md` mis à jour.

## Critères d'acceptation

- `bundle validate` et `bundle deploy` vers `dev` réussissent.
- Les scripts DDL s'exécutent deux fois de suite sans erreur ni changement.
- `silver.instruments` contient les 6 instruments, valeurs marquées « à confirmer » tant que l'utilisateur ne les a pas validées.
- Le job `atlas_foundations_check` réussit dans le workspace.
- La recherche automatique de secrets ne trouve rien dans le dépôt ; aucun log ne contient de valeur secrète.
- Charger une configuration de risque absente ou invalide échoue avec un message explicite (test).
- `pytest` passe ; les tests de `tests/data_quality/` sont explicitement `xfail`, pas verts.
- Aucune table Gold prématurée n'a été créée.

## Ne pas faire

- Ne pas écrire de connecteur fournisseur ni d'appel au fournisseur de données.
- Ne pas écrire d'indicateur ni de logique de signal.
- Ne pas inventer de valeurs de risque, de coût ou de paramètres d'instrument sans les étiqueter et les soumettre à l'utilisateur.
- Ne pas déployer en `prod`.
- Ne pas passer à la phase 3 sans validation explicite.

Termine en résumant : ce qui est fait et vérifié, ce qui diffère de ce fichier et pourquoi, les valeurs que l'utilisateur doit fournir, puis **attends sa validation**.
