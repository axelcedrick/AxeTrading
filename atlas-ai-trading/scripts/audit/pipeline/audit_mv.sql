-- Audit phase 1 (jetable) : vue matérialisée minimale, mode déclenché (pas de streaming continu)
CREATE OR REFRESH MATERIALIZED VIEW audit_mv AS
SELECT src, count(*) AS n FROM atlas.bronze.audit_test GROUP BY src;
