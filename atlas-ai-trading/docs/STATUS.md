# STATUS — ATLAS AI TRADING

_Dernière mise à jour : 2026-10-28 (fin de la phase 2, en attente de validation)_

## Phases
- **Phase 1 — Audit :** terminée et validée le 2026-10-28 (`docs/workspace-audit.md`).
- **Phase 2 — Fondations :** terminée **sous réserve** du secret (voir bloquants), en attente de validation. Rapport : `docs/phases/02-rapport.md`.
- Phase 3 : non commencée.

## Fait et vérifié (phase 2)
- Bundle `databricks.yml` (dev, test, prod) : validé ×3, déployé en `dev`.
- Catalogue `atlas_dev`, schémas `bronze`, `silver`, `gold`, 7 tables avec commentaires et contraintes. DDL idempotents : instantané avant/après identique.
- `silver.instruments` : 6 instruments, marqués « a_confirmer ».
- `src/atlas/common/` : temps (UTC), séances, configuration validée, secrets, journalisation avec masquage. 81 tests verts, 4 xfail (qualité, phase 3).
- Recherche de secrets automatique : rien trouvé. Lint ruff propre.
- Serverless : Python 3.12.3 (mesuré par le job).

## Non vérifié
- Lecture du secret depuis le job (scope `atlas` pas encore créé).
- Masquage des secrets dans les journaux du workspace (testé en local seulement).
- Cible `test` non déployée ; `prod` non déployée (normal).

## Bloquants et décisions attendues
1. Créer le scope `atlas` et y enregistrer la clé (`docs/secrets.md`), puis relancer `atlas_foundations_check`.
2. Renseigner `config/risk.yml` (12 valeurs) et valider les bornes de cohérence.
3. Valider ou corriger `config/costs.yml` (hypothèses), les valeurs de référence de `config/universe.yml` et les calendriers de séances.
4. Activer le hook avant commit (commande dans le README) si tu le souhaites.
5. Questions de licence Twelve Data (audit §6), dont la durée de conservation avant la phase 3.

## Prochaine étape
Validation de la phase 2, puis la phase 3 (ingestion) sur ta décision explicite.
