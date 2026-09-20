de-power-price-lakehouse/
├── README.md                     # centerpiece: problem, architecture, quickstart, decision log link
├── .gitignore
├── databricks.yml                # bundle root: targets (dev/prod), variables
├── infra/
│   └── terraform/
│       ├── versions.tf           # <- terraform {} block (your snippet, part 1)
│       ├── providers.tf          # <- provider "databricks" {} (your snippet, part 2)
│       ├── variables.tf          # databricks_profile, environments, layers
│       ├── main.tf               # catalog, schemas, volumes
│       ├── grants.tf             # GRANT/REVOKE as code
│       ├── outputs.tf            # catalog/schema/volume names for the bundle
│       └── terraform.tfvars.example
├── resources/                    # bundle resource definitions
│   ├── jobs.yml                  # extract job, weather job, orchestration job
│   ├── pipeline.yml              # declarative pipeline
│   └── dashboard.yml
├── src/
│   ├── extract/
│   │   ├── energy_charts.py      # API client + landing to Volume
│   │   └── brightsky.py          # weather client + MERGE to table
│   ├── pipeline/
│   │   ├── bronze.sql            # or .py: streaming tables (Auto Loader)
│   │   ├── silver.sql
│   │   └── gold.sql              # materialized views
│   ├── sql/
│   │   ├── reference_load.sql    # COPY INTO
│   │   └── governance.sql        # row filter, column mask
│   └── notebooks/
│       └── api_reachability_check.py
├── data/
│   └── reference/
│       └── production_types.csv
├── tests/
│   └── test_transformations.py   # pytest on pure Python functions
├── docs/
│   ├── architecture.md           # Mermaid diagram
│   ├── decisions.md              # design decision log
│   └── images/                   # screenshots: DAG, lineage, grants, dashboard
└── .github/
    └── workflows/
        ├── ci.yml                # bundle validate + pytest on PRs
        └── deploy.yml            # bundle deploy on merge