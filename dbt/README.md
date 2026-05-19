# Optional dbt Layer

This folder is an optional Analytics Engineering scaffold for the Athena ELT layer.

The production pipeline currently creates Athena views through `scripts/create_athena_views.py`
using SQL files in `sql/views/`. If this project is extended into a dbt workflow, the same
mart logic can be managed as dbt models with tests, documentation, lineage, and exposures.

Recommended adapter:

```bash
pip install dbt-athena-community
```

Example run flow:

```bash
cd dbt
dbt debug
dbt run
dbt test
dbt docs generate
```

This scaffold is intentionally not wired into CI yet because the current Free Tier-friendly
pipeline uses GitHub Actions plus Athena SQL scripts.

