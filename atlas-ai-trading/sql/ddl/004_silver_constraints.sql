-- 004 — Contraintes CHECK de Silver (appliquées par Delta à chaque écriture).
-- Le lanceur n'ajoute une contrainte que si elle n'existe pas encore (idempotence) ; ne pas renommer.
--
-- Choix : une bougie incohérente n'est pas interdite d'écriture, mais elle doit alors porter le
-- drapeau correspondant. La contrainte garantit qu'aucune bougie incohérente n'est NON signalée.
-- Non applicables par la plateforme (vérifiés en phase 3 par les contrôles de qualité) :
-- unicité de la clé naturelle, alignement de bar_open_ts, horodatage futur, trous, péremption.

ALTER TABLE {catalog}.silver.candles ADD CONSTRAINT candles_interval_known
CHECK (interval IN ('5min', '15min', '1h'));

ALTER TABLE {catalog}.silver.candles ADD CONSTRAINT candles_close_after_open
CHECK (bar_close_ts > bar_open_ts);

ALTER TABLE {catalog}.silver.candles ADD CONSTRAINT candles_ohlc_consistent_or_flagged
CHECK (
  array_contains(quality_flags, 'OHLC_INVALID')
  OR (open > 0 AND high > 0 AND low > 0 AND close > 0
      AND high >= low AND high >= open AND high >= close AND low <= open AND low <= close)
);

ALTER TABLE {catalog}.silver.candles ADD CONSTRAINT candles_volume_non_negative
CHECK (volume IS NULL OR volume >= 0);

ALTER TABLE {catalog}.silver.instruments ADD CONSTRAINT instruments_reference_status
CHECK (reference_status IN ('a_confirmer', 'valide'));

ALTER TABLE {catalog}.silver.instruments ADD CONSTRAINT instruments_positive_sizes
CHECK (pip_size > 0 AND contract_unit > 0 AND price_decimals >= 0);

ALTER TABLE {catalog}.silver.cost_assumptions ADD CONSTRAINT costs_source_labelled
CHECK (source IN ('hypothèse', 'mesuré'));

ALTER TABLE {catalog}.silver.cost_assumptions ADD CONSTRAINT costs_non_negative
CHECK (assumed_spread >= 0 AND assumed_slippage >= 0 AND commission >= 0);
