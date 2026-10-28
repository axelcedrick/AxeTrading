-- 005 — Tables Gold de la phase 2 uniquement. Idempotent.
-- Les autres tables Gold (features, setups, signals, trade_plans, risk_decisions, backtest_*,
-- paper_trades, strategy_performance, regimes) sont créées dans leurs phases respectives.

CREATE TABLE IF NOT EXISTS {catalog}.gold.data_quality_metrics (
  instrument_id      STRING    NOT NULL COMMENT 'Référence silver.instruments',
  interval           STRING    NOT NULL COMMENT '5min, 15min ou 1h',
  window_start       TIMESTAMP NOT NULL COMMENT 'Début UTC de la fenêtre mesurée',
  window_end         TIMESTAMP NOT NULL COMMENT 'Fin UTC (exclue) de la fenêtre mesurée',
  expected_bars      INT       NOT NULL COMMENT 'Bougies attendues selon le calendrier de séances',
  received_bars      INT       NOT NULL COMMENT 'Bougies reçues',
  missing_bars       INT       NOT NULL COMMENT 'Bougies attendues non reçues (trous)',
  duplicate_bars     INT       NOT NULL COMMENT 'Doublons détectés',
  rejected_bars      INT       NOT NULL COMMENT 'Bougies rejetées ou signalées incohérentes',
  incomplete_bars    INT       NOT NULL COMMENT 'Bougies en cours de formation à la collecte',
  off_session_bars   INT       NOT NULL COMMENT 'Bougies reçues hors séance (ex. week-end, audit C7)',
  max_lag_s          DOUBLE             COMMENT 'Retard max entre clôture de bougie et disponibilité, en secondes',
  p95_lag_s          DOUBLE             COMMENT 'Retard au 95e centile, en secondes',
  computed_ts        TIMESTAMP NOT NULL COMMENT 'Heure UTC du calcul',
  rules_version      STRING    NOT NULL COMMENT 'Version des règles de qualité'
)
COMMENT 'Métriques de qualité des données par instrument, intervalle et fenêtre.';

CREATE TABLE IF NOT EXISTS {catalog}.gold.pipeline_runs (
  run_id        STRING    NOT NULL COMMENT 'Identifiant d\'exécution Databricks',
  job_name      STRING    NOT NULL COMMENT 'Nom du job',
  task_key      STRING    NOT NULL COMMENT 'Tâche',
  target_env    STRING    NOT NULL COMMENT 'dev, test ou prod',
  code_version  STRING    NOT NULL COMMENT 'Version du paquet atlas',
  started_ts    TIMESTAMP NOT NULL COMMENT 'Début UTC',
  ended_ts      TIMESTAMP          COMMENT 'Fin UTC',
  status        STRING    NOT NULL COMMENT 'running, success ou failed',
  duration_s    DOUBLE             COMMENT 'Durée en secondes',
  rows_written  BIGINT             COMMENT 'Lignes écrites',
  error_message STRING             COMMENT 'Message d\'erreur, sans secret'
)
COMMENT 'Journal des exécutions de jobs ATLAS.';

CREATE TABLE IF NOT EXISTS {catalog}.gold.audit_log (
  event_id    STRING    NOT NULL COMMENT 'Identifiant unique de l\'événement',
  event_ts    TIMESTAMP NOT NULL COMMENT 'Heure UTC',
  user_name   STRING    NOT NULL COMMENT 'Utilisateur',
  action      STRING    NOT NULL COMMENT 'consulter, ignorer, watchlist, paper, suivi_manuel',
  object_type STRING    NOT NULL COMMENT 'Type d\'objet (signal, plan, instrument…)',
  object_id   STRING    NOT NULL COMMENT 'Identifiant de l\'objet',
  details     STRING             COMMENT 'Détails en JSON'
)
COMMENT 'Actions de l\'utilisateur dans l\'application. Ajout seul.';
