# Design decisions

This log captures some of the choices made in this project.

## Infrastructure

### Terraform state is local, not remote
Terraform state files (`terraform.tfstate`, `.backup`) are git-ignored and stored only on the machine that runs `terraform apply`. They can contain sensitive values, and setting up a remote backend (e.g. cloud storage + locking) is unnecessary overhead for a single-operator project.

### Terraform is run manually, never from CI
Wiring Terraform into GitHub Actions would require remote state and a service principal with broad workspace permissions — both reasonable for a team, neither justified for a Free Edition, single-user project. Terraform stays a local, manual step; only the Databricks Bundle deploy step is a candidate for future CI automation.

## Databricks

### Schema-prefixed environments in one catalog, not one catalog per environment. ### 
Databricks Free Edition's managed storage doesn't support creating catalogs via the Terraform provider. The dev and prod environments were therefore created as different schemas within the same catalog due to this limitation.

### The silver layer has Streaming Tables + `AUTO CDC`, not plain Streaming Tables. ### 
Deduplication needs some aggregation operation like `ROW_NUMBER() OVER (PARTITION BY ...)`, which is not supported for append-only structured streaming. Rather than fall back to a materialized view, silver uses a two-stage pattern: an unordered `_staged` streaming table, then an `AUTO CDC` with `SCD TYPE 1` that updates a second Streaming Table, keeping only the latest row per key. This achieves deduplication while preserving incremental updates and avoiding full refreshes.

### Energy generation data: Long format in silver, wide (pivoted) format in gold.### 
Energy generation data is ingested as a `map<string,double>` (via an Auto Loader schema hint) and kept long in silver, so a new energy production type would show up as a new row, not a broken schema. Gold then explicitly `PIVOT`s some production type rows wide, resulting in a named column per type, because a dashboard needs named columns and gold is allowed to trade flexibility for shape.