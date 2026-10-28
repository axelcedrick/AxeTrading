# Phase 2 — Rapport de fin de phase (fondations)

_Date : 2026-10-28 · Branche : `phase-2-fondations` · Cible déployée : `dev` uniquement_

## 1. Adaptations par rapport à `02-fondations.md` et à l'architecture

| # | Adaptation | Raison (fait mesuré) |
|---|---|---|
| 1 | Un catalogue par environnement : `atlas_dev`, `atlas_test`, `atlas_prod` (au lieu d'un seul `atlas`) | Audit B2 : création de catalogue possible en SQL. Validé par l'utilisateur. `schema_prefix` reste vide. |
| 2 | Catalogue créé par le DDL SQL (`001_catalog_schemas.sql`), exécuté par un job du bundle | Audit B2 : l'API REST refuse la création sans emplacement géré, alors que le SQL l'accepte |
| 3 | Le 1 h n'est **pas** demandé au fournisseur : `intervals.derived: {1h: 15min}` | Ajustement validé de l'audit (576 appels par jour au lieu de 720) |
| 4 | Variable `live_cron` = `0 1/15 * * * ?` (une minute après le quart d'heure) | Audit C5 : la bougie terminée est publiée 30 à 80 s après sa clôture |
| 5 | Drapeau `OFF_SESSION` et colonne `off_session_bars` ajoutés | Audit C7 : bougies émises le week-end |
| 6 | `bronze.raw_candles` : `CLUSTER BY (ingest_date, provider_symbol)` au lieu d'un partitionnement par `ingest_date` | Volumes de quelques Mo par jour : des partitions quotidiennes seraient minuscules |
| 7 | Colonnes ajoutées à `silver.instruments` : `reference_status`, `config_version`, `updated_ts` | Exigence « à confirmer » et traçabilité |
| 8 | Contraintes CHECK de type « cohérent OU signalé » sur `silver.candles` | Une bougie incohérente peut être écrite, mais jamais sans son drapeau (sinon tout le MERGE échouerait) |
| 9 | Échappement `\'` dans le SQL, jamais `''` | En Spark SQL, `''` concatène deux littéraux et l'apostrophe disparaît sans erreur |
| 10 | Le seed n'exécute pas de MERGE s'il n'y a aucun écart | Mesuré : un MERGE à 0 ligne crée quand même une version Delta vide (3 → 4) |
| 11 | Python 3.12 en local (géré par uv), dépendance `tzdata` | Python 3.15 local : pas de paquet binaire précompilé pour `pyyaml`. Serverless mesuré : **3.12.3**. Windows n'a pas de base de fuseaux horaires. |
| 12 | Le dépôt est désormais `atlas-ai-trading/` dans le dépôt git `AxeTrading` ; le `.git` imbriqué (vide) a été supprimé | Décision de l'utilisateur ; un seul dépôt, relié à GitHub |
| 13 | Hook avant commit écrit, **pas activé** | L'activation (`git config core.hooksPath`) modifie la configuration git de façon durable. Elle a été refusée par le système de permissions : c'est à l'utilisateur de la lancer (README). |
| 14 | Deux jobs : `atlas_setup` (DDL, puis seed) et `atlas_foundations_check` | Séparer l'écriture de la vérification ; aucun planning en phase 2 |

## 2. Fait et vérifié

| Critère d'acceptation | Résultat | Preuve |
|---|---|---|
| `bundle validate` (dev, test, prod) et `bundle deploy -t dev` | **OK** | `Validation OK!` ×3 ; `Resources: 2 created` |
| DDL exécutés deux fois sans erreur ni changement | **OK** | 1ᵉʳ passage : 19 instructions exécutées. 2ᵉ passage : 11 `CREATE IF NOT EXISTS` sans effet, 8 contraintes ignorées car existantes. L'instantané avant/après (`scripts/snapshot_catalog.py --diff`) donne **AUCUNE DIFFÉRENCE**, après la correction n° 10. |
| `silver.instruments` : 6 instruments, « à confirmer » | **OK** | `count: 6`, `reference_status: ["a_confirmer"]`, 0 écart avec le fichier |
| `atlas_foundations_check` réussit | **KO, attendu** | Tous les contrôles sont OK sauf `secret` : `atlas/twelvedata_api_key introuvable`. Le scope dédié `atlas` n'existe pas encore. `config_risk` = EN_ATTENTE (refusée car incomplète, comme voulu). |
| Recherche de secrets : rien | **OK** | `scripts/check_secrets.py` → « Aucun secret détecté » (test `test_repository_contains_no_secret`) |
| Configuration de risque absente ou invalide → erreur explicite | **OK** | `tests/unit/test_config.py` : fichier absent, champ manquant, `null`, hors bornes, type faux, champ inconnu, incohérence |
| `pytest` passe ; `tests/data_quality/` en `xfail` | **OK** | `81 passed, 4 xfailed` (xfail stricts : un succès inattendu fait échouer la suite) |
| Aucune table Gold prématurée | **OK** | Contrôle `tables` : `unexpected: {}` ; Gold = `data_quality_metrics`, `pipeline_runs`, `audit_log` |
| Lint et formatage | **OK** | `ruff format` et `ruff check` : `All checks passed!` |

Sortie du contrôle (`atlas_foundations_check`, cible dev) :
```
environment      OK         python 3.12.3, Linux aarch64, atlas 0.2.0
schemas          OK         bronze, default, gold, information_schema, silver
tables           OK         missing {}, unexpected {}
config_universe  OK         6 instruments
config_costs     OK         24 hypothèses, sources ["hypothèse"]
config_risk      EN_ATTENTE refusée car incomplète : 12 champs
secret           KO         secret atlas/twelvedata_api_key introuvable ou illisible
instruments      OK         count 6, diffs {}, reference_status ["a_confirmer"]
```

## 3. Non vérifié ou non fait

- Cible `test` : validée, **non déployée** (non demandé). Cible `prod` : validée, non déployée (interdit sans demande).
- Masquage des secrets dans les journaux **du workspace** : testé en local seulement (test unitaire). Il sera vérifié sur le job dès que le scope `atlas` existera.
- Lignage Unity Catalog : non regardé dans l'interface.
- Calendrier des séances : jours fériés non modélisés (Noël, Nouvel An).

## 4. Valeurs à fournir ou à valider par l'utilisateur

1. **Scope de secrets `atlas`** : à créer, puis y enregistrer la clé (`docs/secrets.md` §1–2). Ensuite, relancer `atlas_foundations_check`. Supprimer ensuite `atlas-audit` (§5).
2. **`config/risk.yml`** : 12 valeurs, **toutes à fournir** (aucune valeur par défaut) : devise, capital fictif, risque par trade, risque ouvert total, perte journalière max, levier max, positions simultanées max, corrélation max, spread et slippage max en % du stop, âge max d'un signal, score de qualité minimal des données.
   Les **bornes de cohérence** appliquées par le code sont aussi à valider : risque par trade ≤ 5 %, risque ouvert ≤ 20 %, perte journalière ≤ 20 %, levier ≤ 100, positions ≤ 50, âge ≤ 24 h.
3. **`config/costs.yml`** : spreads et slippages proposés (EUR/USD 1,0 à 1,5 pip, … XAU/USD 30 à 45 « pips » de 0,01 $), **tous `source: hypothèse`**. Les séances de coûts sont aussi proposées : Asie 21–07, Londres 07–12, chevauchement 12–16, New York 16–21 UTC.
4. **`config/universe.yml`** : `pip_size`, `price_decimals` et `contract_unit` de chaque instrument, avec deux points particuliers :
   - USD/JPY : `price_decimals` = 3, alors que le flux en donne 5 ;
   - XAU/USD : `pip_size` 0,01 ou 0,1 selon la convention, et `contract_unit` = 100 onces.
5. **Calendriers de séances** (`src/atlas/common/sessions.py`) :
   - Forex : du dimanche 17:00 au vendredi 17:00, heure de New York, sans pause ;
   - or : du dimanche 18:00 au vendredi 17:00, heure de New York, avec une pause quotidienne de 17:00 à 18:00 ;
   - jours fériés : à décider.

## 5. Questions ouvertes

- Le hook avant commit doit-il être activé (`git config core.hooksPath atlas-ai-trading/.githooks`, à lancer par toi) ?
- `CLAUDE.md` est maintenant dans `atlas-ai-trading/` : il faut ouvrir les prochaines sessions dans ce dossier pour qu'il soit chargé automatiquement.
- Les questions de licence Twelve Data restent ouvertes (audit §6, questions 1 à 3). La question 3, sur la durée de conservation, est à trancher avant le backfill de la phase 3.
