-- 001 — Catalogue et schémas d'un environnement. Idempotent.
-- {catalog} est remplacé par le lanceur (atlas.jobs.ddl) selon la cible du bundle : atlas_dev, atlas_test, atlas_prod.
-- Audit B2 : la création de catalogue fonctionne en SQL (stockage par défaut), pas par l'API REST.

CREATE CATALOG IF NOT EXISTS {catalog}
COMMENT 'ATLAS AI TRADING — environnement {catalog}. Analyse et paper trading uniquement, aucun ordre réel.';

CREATE SCHEMA IF NOT EXISTS {catalog}.bronze
COMMENT 'Réponses brutes des fournisseurs et métadonnées de collecte, en ajout seul.';

CREATE SCHEMA IF NOT EXISTS {catalog}.silver
COMMENT 'Données normalisées, idempotentes (clé naturelle, MERGE).';

CREATE SCHEMA IF NOT EXISTS {catalog}.gold
COMMENT 'Données analytiques, versionnées par jeu de règles.';
