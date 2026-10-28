# ATLAS AI TRADING

Plateforme personnelle de recherche et d'aide à la décision pour le trading intraday (Forex et or), construite sur Databricks.
**Analyse, alertes et paper trading uniquement : aucun ordre réel n'est jamais transmis.**

Règles permanentes : [`CLAUDE.md`](CLAUDE.md). Architecture : [`docs/architecture.md`](docs/architecture.md). État : [`docs/STATUS.md`](docs/STATUS.md).

## Prérequis

- [uv](https://docs.astral.sh/uv/) (gère Python 3.12, aligné sur le serverless Databricks)
- Databricks CLI ≥ 1.22, profil `dbc-2ca00ccd-e312` configuré (`databricks auth login`)

## Commandes

```bash
uv sync                                  # environnement local (Python 3.12, dépendances épinglées)
uv run pytest                            # tous les tests (commande unique)
uv run ruff format . && uv run ruff check .   # formatage et lint
uv run python scripts/check_secrets.py   # recherche de secrets dans le dépôt
```

Hook avant commit (formatage, lint, secrets, tests) — à activer une fois, depuis la racine du dépôt git :

```bash
git config core.hooksPath atlas-ai-trading/.githooks
```

## Déploiement (Asset Bundle)

```bash
databricks bundle validate -t dev
databricks bundle deploy -t dev
databricks bundle run atlas_setup -t dev               # DDL + référentiel des instruments (idempotent)
databricks bundle run atlas_foundations_check -t dev   # vérification des fondations
```

Cibles : `dev` (catalogue `atlas_dev`, par défaut), `test` (`atlas_test`), `prod` (`atlas_prod`, uniquement sur décision explicite).
Secrets : voir [`docs/secrets.md`](docs/secrets.md). Droits : voir [`docs/governance.md`](docs/governance.md).

## Arborescence

```
config/        univers, risque (à renseigner par l'utilisateur), coûts (hypothèses)
sql/ddl/       scripts DDL numérotés, idempotents
src/atlas/     paquet Python (common/ : temps, séances, config, secrets, journalisation ; jobs/ : tâches)
resources/     définitions des jobs du bundle
tests/         unit/, data_quality/ (squelettes xfail jusqu'à la phase 3), fixtures/
scripts/       outils (secrets, instantané de catalogue) ; audit/ = scripts jetables de la phase 1
docs/          architecture, audit, phases, secrets, gouvernance, fournisseurs
```
