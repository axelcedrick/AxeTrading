-- 003 — Tables Silver. Idempotent.

CREATE TABLE IF NOT EXISTS {catalog}.silver.instruments (
  instrument_id       STRING              NOT NULL COMMENT 'Identifiant interne (ex. EURUSD)',
  asset_class         STRING              NOT NULL COMMENT 'FX, COMMODITY, plus tard CRYPTO, EQUITY',
  symbol              STRING              NOT NULL COMMENT 'Symbole lisible (ex. EUR/USD)',
  base_ccy            STRING              NOT NULL COMMENT 'Devise ou actif de base (ISO 4217, XAU pour l\'or)',
  quote_ccy           STRING              NOT NULL COMMENT 'Devise de cotation (ISO 4217)',
  pip_size            DOUBLE              NOT NULL COMMENT 'Taille du pip en unité de prix',
  price_decimals      INT                 NOT NULL COMMENT 'Précision de cotation usuelle (le flux peut en donner davantage)',
  contract_unit       DOUBLE              NOT NULL COMMENT 'Unités de base par lot standard',
  session_calendar_id STRING              NOT NULL COMMENT 'Calendrier de séances (atlas.common.sessions)',
  provider_symbols    MAP<STRING, STRING> NOT NULL COMMENT 'Fournisseur -> symbole chez ce fournisseur',
  is_active           BOOLEAN             NOT NULL COMMENT 'Instrument suivi',
  reference_status    STRING              NOT NULL COMMENT 'a_confirmer tant que l\'utilisateur n\'a pas validé les valeurs de référence, puis valide',
  config_version      INT                 NOT NULL COMMENT 'Version de config/universe.yml ayant produit la ligne',
  updated_ts          TIMESTAMP           NOT NULL COMMENT 'Heure UTC de la dernière modification effective'
)
COMMENT 'Référentiel des instruments, alimenté par MERGE depuis config/universe.yml.';

CREATE TABLE IF NOT EXISTS {catalog}.silver.candles (
  instrument_id STRING        NOT NULL COMMENT 'Référence silver.instruments',
  interval      STRING        NOT NULL COMMENT '5min, 15min ou 1h',
  bar_open_ts   TIMESTAMP     NOT NULL COMMENT 'Ouverture UTC de la bougie (alignée sur l\'intervalle)',
  bar_close_ts  TIMESTAMP     NOT NULL COMMENT 'Clôture UTC (exclue) de la bougie',
  open          DOUBLE        NOT NULL COMMENT 'Prix d\'ouverture',
  high          DOUBLE        NOT NULL COMMENT 'Plus haut',
  low           DOUBLE        NOT NULL COMMENT 'Plus bas',
  close         DOUBLE        NOT NULL COMMENT 'Dernier prix',
  volume        DOUBLE                 COMMENT 'Volume ; NULL sur le Forex et l\'or (absent du flux, audit C7)',
  is_complete   BOOLEAN       NOT NULL COMMENT 'Vrai si bar_close_ts <= heure de la requête. Calculé, jamais repris du fournisseur',
  quality_flags ARRAY<STRING> NOT NULL COMMENT 'Drapeaux de qualité (ex. GAP, OHLC_INVALID, STALE, OFF_SESSION, FUTURE_TS) ; vide si aucun',
  provider      STRING        NOT NULL COMMENT 'Fournisseur d\'origine',
  ingest_ts     TIMESTAMP     NOT NULL COMMENT 'Heure UTC d\'écriture',
  bronze_ref    STRING        NOT NULL COMMENT 'Référence de la réponse brute (payload_hash de bronze.raw_candles)',
  CONSTRAINT candles_pk PRIMARY KEY (instrument_id, interval, bar_open_ts, provider)
)
CLUSTER BY (instrument_id, interval, bar_open_ts)
COMMENT 'Bougies normalisées. Clé naturelle (instrument_id, interval, bar_open_ts, provider), alimentation par MERGE. La clé primaire est informative : Unity Catalog ne l\'applique pas.';

CREATE TABLE IF NOT EXISTS {catalog}.silver.cost_assumptions (
  instrument_id    STRING NOT NULL COMMENT 'Référence silver.instruments',
  session          STRING NOT NULL COMMENT 'Séance de coûts (config/costs.yml)',
  assumed_spread   DOUBLE NOT NULL COMMENT 'Spread supposé, en unité de prix',
  assumed_slippage DOUBLE NOT NULL COMMENT 'Slippage supposé, en unité de prix',
  commission       DOUBLE NOT NULL COMMENT 'Commission supposée, en unité de prix',
  valid_from       DATE   NOT NULL COMMENT 'Date d\'effet',
  source           STRING NOT NULL COMMENT 'hypothèse ou mesuré ; rappelé dans tout résultat de backtest'
)
COMMENT 'Hypothèses de coûts d\'exécution. Alimentée à partir de la phase 5 ; vide en phase 2.';
