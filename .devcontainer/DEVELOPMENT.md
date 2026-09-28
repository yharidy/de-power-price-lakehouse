# Development guide

This is the practical, "how do I actually run this" doc. 
## 1. Local environment

This repo ships a dev container (`.devcontainer/`) so the toolchain (Python, [uv](https://docs.astral.sh/uv/), the Databricks CLI, Terraform) is identical for anyone opening the project.


**Open it:**
1. Open the repo folder in VS Code.
2. When prompted, "Reopen in Container"
3. The container builds once; subsequent opens are fast.



## 2. Terraform (infrastructure)

Full walkthrough: **[infra/README.md](../infra/README.md)**. Summary:

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars   # fill in catalog_name
terraform init
terraform plan
terraform apply
```
After running those commands, you should see the schemas and volumes on your Databricks workspace.

## 3. Databricks: authenticating and deploying the bundle

### Authenticate the CLI (one-time per machine)

```bash
databricks auth login --host https://<your-workspace-url> --profile <profile-name>
```

This writes a profile to `~/.databrickscfg`, which both the Databricks CLI and Terraform's `databricks` provider read.

### Validate before deploying

```bash
databricks bundle validate -t dev
```

### Deploy

```bash
databricks bundle deploy -t dev
```

Rebuilds the wheel (`uv build --wheel`, configured in `databricks.yml`'s `artifacts` block) and uploads everything — jobs, pipelines, the dashboard — to the workspace.

### Run the daily pipeline on demand

```bash
databricks bundle run daily_pipeline -t dev
```

You should now see some JSON files containing the API responses in your volumes, as well as the bronze, silver and gold tables.

### Trigger a manual backfill

```bash
databricks bundle run backfill -t dev --params start_date=2026-01-01,end_date=2026-02-01
```

This only lands raw JSON into the bronze landing Volume — it deliberately does **not** run ingestion or the silver/gold pipelines itself. Auto Loader's checkpoint-based ingestion (inside `daily_pipeline`) picks up *all* unprocessed files the next time it runs.

### Deploying to production

`prod` mode requires an explicit `workspace.root_path` (set in `databricks.yml`) so a production deployment can't accidentally collide with another user's dev deployment path. Overwrite the value set there, with your own root path.

```bash
databricks bundle deploy -t prod
databricks bundle run daily_pipeline -t prod
```



## 4. Running the tests

```bash
uv run pytest tests/
```

## 5. CI

GitHub Actions runs `uv sync` + `uv run pytest` on every push to any branch. This is intentionally minimal — a correctness gate on the Python extraction/ingestion logic, not a deployment pipeline. 
