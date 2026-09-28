# Infrastructure — Terraform

This folder provisions the stable, rarely-changing foundations of the lakehouse: schemas and landing volumes. 
## What gets created

| Resource | Purpose |
|---|---|
| `databricks_schema` (×6) | `dev_bronze`, `dev_silver`, `dev_gold`, `prod_bronze`, `prod_silver`, `prod_gold` — see [environment design](#environment-design-schema-prefix-not-catalog-per-environment) below |
| `databricks_volume` (×2, one per environment) | The landing Volume each environment's Auto Loader ingestion reads from |



## Setup and running Terraform

### Prerequisites

- [Terraform](https://developer.hashicorp.com/terraform/downloads) ≥ 1.16.4
- The [Databricks CLI](https://docs.databricks.com/dev-tools/cli/) v1.18.0, authenticated (see the root [DEVELOPMENT.md](../.devcontainer/DEVELOPMENT.md) for the `databricks auth login` step — Terraform reuses the same `~/.databrickscfg` profile)
- An existing Unity Catalog catalog on your workspace to point Terraform at (Free Edition ships with a default one — find its name in Catalog Explorer)

### Steps

```bash
cd infra/terraform

# Copy the example vars file and fill in your catalog name
cp terraform.tfvars.example terraform.tfvars
# then edit terraform.tfvars:
#   catalog_name        = "<your catalog name, from Catalog Explorer>"
#   databricks_profile  = "<your ~/.databrickscfg profile name>"

terraform init
terraform plan    # review: should show N schemas + N volumes to add, nothing to destroy
terraform apply   # type "yes" to confirm
```

### Verifying it worked

```bash
terraform output
```

This prints the schema full names and landing volume paths that the Bundle's variables need to match (`variables.yml` at the repo root). Cross-check a couple of these against Catalog Explorer in the workspace UI.

### Tearing down

```bash
terraform destroy
```

Note: `force_destroy = false` on schemas means Terraform will refuse to delete a schema that still contains tables — empty it first (or drop the tables via the Bundle/pipeline UI) if you need a clean teardown.

## State management

Terraform state (`terraform.tfstate`, `terraform.tfstate.backup`) is stored **locally only** and is git-ignored — it can contain sensitive values and this project has no remote state backend.
