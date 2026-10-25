# ATLAS AI TRADING — Architecture du MVP (Forex + or)

Statut : proposition à valider. Rien ici n'a été exécuté sur le workspace : les points marqués **[À VÉRIFIER]** sont testés en phase 1 (audit) et consignés dans `docs/workspace-audit.md`.

## 1. Périmètre du MVP

- **Marchés :** Forex et or (XAU/USD). Crypto et actions viennent après, sans refonte (voir §6).
- **Univers initial (proposition, 6 instruments) :** EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CHF, XAU/USD. Extensible par configuration.
- **Unités de temps :** 15 min et 1 h en production ; 5 min pour le backfill et le backtest ; 1 min plus tard, après mesure des limites.
- **Mode :** analyse, alertes, paper trading. Aucun ordre réel.
- **Cadence :** micro-batch planifié (pas de streaming continu) — adapté à la Free Edition et à une source gratuite.

## 2. Contraintes connues

| Sujet | Constat | Conséquence |
|---|---|---|
| Fournisseur candidat : Twelve Data (offre gratuite) | 800 appels/jour, 8 par minute, 5 000 points par requête | Le backfill est peu coûteux (gros blocs) ; le live doit être économe |
| Budget d'appels live | 6 instruments × 96 bougies de 15 min = 576 appels/jour, marge de ~28 % | Interroger toutes les 15 min ; pas de live en 5 min avec l'offre gratuite |
| Fraîcheur des données gratuites | Sources contradictoires (temps réel vs différé) | **[À VÉRIFIER]** : comparer les horodatages reçus à l'heure réelle |
| Droits d'usage | L'offre gratuite est décrite comme réservée à un usage interne, sans affichage | **[À VÉRIFIER]** dans les conditions d'utilisation avant d'afficher les données dans une application partagée |
| Spread bid/ask | Probablement absent de l'offre gratuite | Spread modélisé par hypothèses configurables (§4, `cost_assumptions`), signalé comme tel |
| Volume Forex | Volume centralisé inexistant sur le Forex au comptant | Ne pas utiliser le volume comme signal sur le Forex ; il reste nullable |
| Free Edition Databricks | Serverless, quotas, Apps, réseau sortant, modèles de langage | **[À VÉRIFIER]** en phase 1 |

Fournisseurs alternatifs à évaluer en phase 1 pour le backfill historique (non vérifiés ici) : sources d'historique gratuites de type Dukascopy, Alpha Vantage, Finnhub. Aucune n'est retenue avant test.

## 3. Arborescence du dépôt

```
atlas-ai-trading/
├── CLAUDE.md
├── databricks.yml                 # Asset Bundle (dev / test / prod)
├── pyproject.toml
├── config/
│   ├── universe.yml               # instruments actifs, timeframes
│   ├── risk.yml                   # paramètres de risque utilisateur
│   └── costs.yml                  # hypothèses de spread / slippage / frais
├── src/atlas/
│   ├── providers/                 # base.py (interface), twelvedata.py, ...
│   ├── ingestion/                 # bronze.py, silver.py, quality.py
│   ├── quant/                     # indicators.py, structure.py, setups/, regimes.py
│   ├── scoring/
│   ├── backtest/                  # engine.py, execution_model.py, walkforward.py
│   ├── risk/                      # engine.py (indépendant de l'IA)
│   ├── news/                      # phase 6
│   ├── agents/                    # phase 7, lecture seule
│   └── common/                    # temps, calendriers de sessions, journalisation
├── pipelines/                     # définitions Lakeflow / jobs
├── app/                           # Databricks Apps ou Streamlit
├── tests/
│   ├── unit/
│   ├── data_quality/              # bougie incomplète, cotation périmée, incohérence
│   └── fixtures/
├── docs/
│   ├── architecture.md
│   ├── workspace-audit.md
│   ├── providers/
│   ├── phases/
│   └── STATUS.md
└── notebooks/                     # exploration uniquement
```

## 4. Modèle de données (catalogue `atlas`)

Principe : Bronze en ajout seul (append-only), Silver idempotent (clé naturelle), Gold versionné par jeu de règles. Tous les horodatages en UTC.

### Bronze

**`bronze.raw_candles`** — réponses brutes
`provider`, `provider_symbol`, `interval`, `request_params` (string), `request_ts`, `ingest_ts`, `http_status`, `collect_status` (ok / partial / error), `connector_version`, `payload` (string JSON brut), `payload_hash`, `ingest_date` (partition).

**`bronze.raw_news`** (phase 6) — même structure, avec `url`, `published_ts`.

### Silver

**`silver.instruments`**
`instrument_id`, `asset_class` (FX / COMMODITY / plus tard CRYPTO, EQUITY), `symbol`, `base_ccy`, `quote_ccy`, `pip_size`, `price_decimals`, `contract_unit`, `session_calendar_id`, `provider_symbols` (map fournisseur → symbole), `is_active`.

**`silver.candles`**
`instrument_id`, `interval`, `bar_open_ts`, `bar_close_ts`, `open`, `high`, `low`, `close`, `volume` (nullable), `is_complete`, `quality_flags` (array : ex. `GAP`, `OHLC_INVALID`, `STALE`), `provider`, `ingest_ts`, `bronze_ref`.
Clé naturelle : (`instrument_id`, `interval`, `bar_open_ts`, `provider`). Alimentation par MERGE.

**`silver.cost_assumptions`**
`instrument_id`, `session`, `assumed_spread`, `assumed_slippage`, `commission`, `valid_from`, `source` (hypothèse / mesuré).

### Gold

| Table | Contenu clé |
|---|---|
| `gold.features` | `instrument_id`, `interval`, `bar_open_ts`, `feature_set_version`, ATR, RSI, MACD, moyennes mobiles, structure (sommets/creux), `computed_ts` |
| `gold.regimes` | `instrument_id`, `interval`, `bar_open_ts`, `regime`, `rules_version` |
| `gold.setups` | `setup_id`, `instrument_id`, `interval`, `setup_type`, `direction`, `detected_ts`, `rules_version`, `features_ref`, `valid_until` |
| `gold.signals` | `signal_id`, `setup_id`, `quality_score`, `calibrated_probability` (nullable), `net_expectancy` (nullable), `uncertainty`, `data_quality_score`, `status` (candidate / rejected / expired), `rejection_reasons` |
| `gold.trade_plans` | `plan_id`, `signal_id`, `reference_price`, `entry_trigger`, `stop`, `targets`, `estimated_costs`, `position_size`, `invalidation`, `expires_ts` |
| `gold.risk_decisions` | `signal_id`, `decision` (accept / refuse), `reasons`, `risk_params_version`, `decided_ts` |
| `gold.backtest_runs` / `gold.backtest_trades` | lien MLflow (`mlflow_run_id`), période, version du code, hypothèses d'exécution, métriques ; trades individuels |
| `gold.paper_trades` | ouverture, clôture, prix simulés, coûts appliqués, lien vers `plan_id` |
| `gold.strategy_performance` | métriques par stratégie et par période |
| `gold.data_quality_metrics` | retards, trous, doublons, bougies rejetées, par instrument |
| `gold.pipeline_runs` | état et durée des jobs |
| `gold.audit_log` | action utilisateur (consulter, ignorer, watchlist, paper, suivi manuel), horodatage |

`calibrated_probability` reste `NULL` tant qu'aucune calibration validée sur données indépendantes n'existe ; l'interface affiche alors un score de classement uniquement.

## 5. Interface des fournisseurs

```python
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

@dataclass(frozen=True)
class RawResponse:
    provider: str
    provider_symbol: str
    interval: str
    request_params: str
    request_ts: datetime
    http_status: int
    payload: str            # JSON brut, conservé tel quel
    connector_version: str

class MarketDataProvider(Protocol):
    name: str

    def capabilities(self) -> dict:
        """Intervalles, historique max, limites de requêtes, champs fournis."""

    def fetch_candles(self, provider_symbol: str, interval: str,
                      start: datetime | None, end: datetime | None,
                      limit: int | None) -> RawResponse:
        """Retourne la réponse brute. Aucune normalisation ici."""

    def remaining_budget(self) -> dict:
        """Crédits / appels restants (minute et jour)."""
```

La normalisation (réponse brute → `silver.candles`) vit dans `ingestion/`, avec un adaptateur par fournisseur. Le moteur quantitatif ne lit que `silver` : changer de fournisseur n'affecte pas `quant/`.

## 6. Extension prévue (crypto, actions)

Ajouter une classe d'actifs = une ligne `asset_class` dans `silver.instruments`, un adaptateur fournisseur, un calendrier de sessions et des hypothèses de coûts. Aucune table ni moteur à refondre. Les calendriers de sessions (Forex 24h/5j, or avec pauses, actions avec ouvertures, crypto 24h/7j) sont la principale spécificité à anticiper dans `common/`.

## 7. Critères d'acceptation (phases 1 à 3)

**Phase 1 — Audit**
- `docs/workspace-audit.md` rempli par des tests réels : accès au catalogue, création d'un schéma, job serverless exécuté, appel réseau sortant vers le fournisseur, disponibilité de Databricks Apps, secrets, accès aux modèles de langage.
- Test de fraîcheur des données gratuites (horodatage reçu vs heure réelle) et lecture des conditions d'utilisation.

**Phase 2 — Fondations**
- Catalogue `atlas` et schémas `bronze`/`silver`/`gold` créés par le bundle.
- Clé fournisseur stockée dans un secret ; absente du code et des logs (vérifié par une recherche dans le dépôt).

**Phase 3 — Ingestion**
- Backfill de 6 instruments sur le 15 min et le 1 h.
- Relancer deux fois le même job ne crée aucun doublon (test).
- Tests de qualité : une bougie incomplète, une cotation périmée ou un OHLC invalide ne produit aucun signal.
- Métriques de retard et de trous visibles dans `gold.data_quality_metrics`.
- 7 jours d'exécution planifiée sans intervention.

## 8. Coûts à suivre

- Databricks Free Edition : pas de facturation, mais des quotas à mesurer.
- Données : offre gratuite, avec les limites du §2. Le passage à un plan payant n'est envisagé que si le live en 5 min ou davantage d'instruments devient nécessaire ; prix à consulter à ce moment-là.
- IA : appels réservés aux seules configurations candidates ; coût par appel tracé dans MLflow.

## 9. Décisions à valider

1. L'univers de 6 instruments te convient-il (ou veux-tu d'autres paires) ?
2. Live en 15 min uniquement, avec 5 min réservé au backfill et au backtest : acceptable pour un usage d'aide à la décision ?
3. Spread modélisé par hypothèses tant qu'aucune source bid/ask n'est disponible : acceptable pour les premiers backtests, à condition de le signaler dans les résultats ?
