-- 002 — Tables Bronze. Idempotent. Ajout seul : aucune mise à jour ni suppression applicative.
-- Adaptation : regroupement liquide (CLUSTER BY) au lieu d'un partitionnement par ingest_date,
-- les volumes attendus (quelques Mo par jour) rendant les partitions trop petites.

CREATE TABLE IF NOT EXISTS {catalog}.bronze.raw_candles (
  provider          STRING    NOT NULL COMMENT 'Fournisseur (ex. twelvedata)',
  provider_symbol   STRING    NOT NULL COMMENT 'Symbole tel que demandé au fournisseur (ex. EUR/USD)',
  interval          STRING    NOT NULL COMMENT 'Intervalle demandé (5min, 15min, 1h)',
  request_params    STRING    NOT NULL COMMENT 'Paramètres de la requête en JSON, sans clé ni secret (timezone=UTC exigé)',
  request_ts        TIMESTAMP NOT NULL COMMENT 'Heure UTC d\'envoi de la requête',
  ingest_ts         TIMESTAMP NOT NULL COMMENT 'Heure UTC d\'écriture dans Bronze',
  http_status       INT                COMMENT 'Code HTTP reçu (NULL si aucune réponse)',
  collect_status    STRING    NOT NULL COMMENT 'ok, partial ou error',
  connector_version STRING    NOT NULL COMMENT 'Version du connecteur ayant produit la ligne',
  payload           STRING             COMMENT 'Corps de réponse brut, conservé tel quel (JSON texte)',
  payload_hash      STRING             COMMENT 'SHA-256 du payload, pour la détection de doublons',
  ingest_date       DATE      NOT NULL COMMENT 'Date UTC d\'ingestion'
)
CLUSTER BY (ingest_date, provider_symbol)
COMMENT 'Réponses brutes de bougies, une ligne par requête au fournisseur. Ajout seul.';
