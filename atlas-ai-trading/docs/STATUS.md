# STATUS — ATLAS AI TRADING

_Dernière mise à jour : 2026-10-28 (phase 1 validée)_

## Phase en cours
**Phase 1 — Audit : terminée et validée par l'utilisateur le 2026-10-28**, avec les ajustements de `docs/workspace-audit.md` §4. La phase 2 n'est pas commencée.

## Fait et vérifié (tests réels, preuves dans `docs/workspace-audit.md`)
- Dépôt inspecté. `.gitignore` créé. Aucun secret dans le dépôt.
- Workspace Free Edition : authentification, catalogue `atlas` (en SQL), schémas et tables Delta, job serverless, planification toutes les 15 min (2 exécutions), Lakeflow, Asset Bundle, Databricks Apps, MLflow, Foundation Model APIs, secrets lus depuis un job.
- Twelve Data Basic joignable depuis le serverless. Les 6 instruments sont servis, **XAU/USD compris**, en 5 min, 15 min et 1 h. Retard d'environ 30 à 80 s sur le 1 min. 5 000 points par appel. Historique EUR/USD 15 min depuis le 2020-01-30. 429 au 9ᵉ appel de la minute.
- Tous les objets de test ont été supprimés. Le scope `atlas-audit` (clé) est conservé.
- 39 appels fournisseur sur 40.

## Non vérifié
- Profondeur d'historique 1 h et 5 min, et pour XAU/USD (seul EUR/USD 15 min a été mesuré).
- Fraîcheur pendant les séances Londres et New York (mesurée seulement entre 21:23 et 21:32 UTC).
- Durée de conservation autorisée par la documentation Twelve Data.
- Quotas chiffrés de la Free Edition et débits des modèles de langage (non publiés).
- Version Python du serverless (environnement 3), par rapport à Python 3.15 en local.

## Bloquants et décisions attendues
- Validation de la phase 1 et des ajustements d'architecture (`docs/workspace-audit.md` §4).
- Licence Twelve Data : affichage dans l'app (« non-display » sur Basic) et couverture de XAU/USD. Bloquant pour la phase 8 seulement.
- Emplacement du code : dossier `atlas-trading/` à renommer en `atlas-ai-trading/` (renommage refusé par le système, dossier probablement ouvert ailleurs).

## Prochaine étape
Phase 2 — Fondations, après ta validation explicite.
